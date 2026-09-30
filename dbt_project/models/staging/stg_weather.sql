-- models/staging/stg_weather.sql

with raw as (
    select * from {{ source('bronze', 'weather_raw') }}
),

-- pull each city's nested object out into its own row
by_city as (
    select fetched_at, 'Lahore' as city, cities.Lahore as city_data from raw
    union all
    select fetched_at, 'Delhi' as city, cities.Delhi as city_data from raw
    union all
    select fetched_at, 'Los Angeles' as city, cities."Los Angeles" as city_data from raw
),

-- Open-Meteo returns parallel arrays: hourly.time[i], hourly.temperature_2m[i], etc.
-- all belong to the same hour. UNNEST with the same index expands them together.
exploded as (
    select
        fetched_at,
        city,
        unnest(city_data.hourly.time)                as observed_at_raw,
        unnest(city_data.hourly.temperature_2m)       as temperature_c,
        unnest(city_data.hourly.relative_humidity_2m) as humidity_pct,
        unnest(city_data.hourly.wind_speed_10m)       as wind_speed_kmh,
        unnest(city_data.hourly.precipitation)        as precipitation_mm
    from by_city
)

select
    city,
    cast(observed_at_raw as timestamp) as observed_at_utc,  -- already UTC, we requested it that way in ingestion
    temperature_c,
    humidity_pct,
    wind_speed_kmh,
    precipitation_mm
from exploded
where observed_at_raw is not null
qualify row_number() over (
    partition by city, observed_at_raw order by fetched_at desc
) = 1  -- dedupe: if the same hour appears in two overlapping ingestion runs, keep the latest fetch (freshest forecast/actuals)