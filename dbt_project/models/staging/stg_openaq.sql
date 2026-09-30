-- models/staging/stg_openaq.sql

with raw as (
    select * from {{ source('bronze', 'openaq_raw') }}
),

by_city as (
    select fetched_at, 'Lahore' as city, cities.Lahore as stations from raw
    union all
    select fetched_at, 'Delhi' as city, cities.Delhi as stations from raw
    union all
    select fetched_at, 'Los Angeles' as city, cities."Los Angeles" as stations from raw
),

-- one row per station
stations_exploded as (
    select fetched_at, city, unnest(stations) as station from by_city
),

-- sensors: id -> pollutant name/units, one row per sensor a station has
sensors_exploded as (
    select
        city,
        station.location.id   as station_id,
        station.location.name as station_name,
        unnest(station.location.sensors) as sensor
    from stations_exploded
),

sensor_lookup as (
    select
        station_id,
        sensor.id             as sensor_id,
        sensor.parameter.name as pollutant,
        sensor.parameter.units as unit
    from sensors_exploded
),

-- readings: one row per measurement, still only tagged with sensorsId
readings_exploded as (
    select
        fetched_at,
        city,
        station.location.id as station_id,
        unnest(station.measurements.results) as reading
    from stations_exploded
),

readings as (
    select
        fetched_at,
        city,
        station_id,
        reading.sensorsId                    as sensor_id,
        reading.value                        as value,
        cast(reading.datetime.utc as timestamp) as measured_at_utc
    from readings_exploded
)

select
    r.city,
    r.station_id,
    sl.pollutant,
    r.value,
    sl.unit,
    r.measured_at_utc
from readings r
inner join sensor_lookup sl
    on r.station_id = sl.station_id and r.sensor_id = sl.sensor_id
where r.value is not null
    and r.value >= 0            -- drops the -999 sentinel and any other negative sentinels
qualify row_number() over (
    partition by r.station_id, r.sensor_id, r.measured_at_utc order by r.fetched_at desc
) = 1  -- dedupe: keep the reading from the most recent ingestion run