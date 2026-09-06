# Air Quality + Weather Correlation Pipeline

A small, portfolio-scale data engineering project that ingests air quality and weather data, transforms it through a medallion architecture (bronze → silver → gold), and surfaces hourly air-quality/weather correlations on a dashboard.

Built to be fully reproducible on a free-tier stack — no cloud bill, no credit card required.

## Why this project

Most portfolio data pipelines are either toy ETL scripts or copied "Netflix-scale" tutorials nobody fully understands. This project is deliberately small enough to build and explain end-to-end, while still touching every tool a real data engineering role expects: an orchestrator, a transformation layer with tests, a proper storage architecture, and CI/CD.

## Architecture

```
OpenAQ API ─┐                                    ┌─→ Streamlit dashboard
             ├─→ Bronze (raw JSON) → Silver (dbt) → Gold (dbt) ─┘
Open-Meteo ──┘         │                  │             │
                    Dagster orchestrates all of the above
                    GitHub Actions runs it on a schedule + tests every PR
```

- **Bronze** — raw API responses, dumped as-is, date-partitioned. Never transformed. Acts as a replay source if downstream logic needs to change.
- **Silver** — cleaned, typed, deduplicated tables built with dbt on top of DuckDB. Nested JSON is flattened, timestamps normalized to UTC, and known bad values are filtered.
- **Gold** — aggregated, business-ready marts (hourly air quality joined with weather, per city) that the dashboard queries directly.

Full architecture decisions and rationale: [`docs/architecture.md`](docs/architecture.md).

## Stack

| Layer | Tool | Cost |
|---|---|---|
| Ingestion | Python (`requests`) | Free |
| Storage / warehouse | DuckDB | Free |
| Transformation | dbt-core + dbt-duckdb | Free |
| Orchestration | Dagster | Free |
| Data quality | dbt tests | Free |
| Dashboard | Streamlit Community Cloud | Free |
| CI/CD | GitHub Actions | Free |
| IaC | Terraform | Free |

## Data sources

- [OpenAQ API v3](https://explore.openaq.org) — air quality measurements (PM2.5, PM10, NO2, O3, etc). Requires a free API key.
- [Open-Meteo](https://open-meteo.com) — weather data (temperature, humidity, wind, precipitation). No API key required.

Cities tracked: Lahore, Delhi, Los Angeles.

## Project structure

```
aq-pipeline/
├── ingestion/          # Bronze layer: fetch and dump raw JSON
├── dbt_project/         # Silver + gold transformations
│   ├── models/staging/   # Silver: cleaned, typed models
│   └── models/marts/     # Gold: aggregated marts
├── dagster_project/     # Orchestration
├── dashboard/           # Streamlit app
├── tests/               # Python unit tests
├── terraform/           # IaC
├── .github/workflows/   # CI/CD
├── data/                # Local bronze/silver/gold storage (gitignored)
└── docs/architecture.md # Full design decisions
```

## Setup

```bash
git clone <your-repo-url>
cd aq-pipeline
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Get a free OpenAQ API key at [explore.openaq.org](https://explore.openaq.org/register), then:

```bash
export OPENAQ_API_KEY=your_key_here
```

## Running the pipeline

**1. Ingest bronze data**
```bash
python ingestion/fetch_weather.py
python ingestion/fetch_openaq.py
```

**2. Set up dbt** (one-time)
```bash
mkdir -p ~/.dbt
cp dbt_project/profiles.yml ~/.dbt/profiles.yml
cd dbt_project
dbt deps      # installs dbt_utils
dbt debug     # confirms connection
```

**3. Build and test silver + gold**
```bash
dbt run --select staging
dbt test --select staging
dbt run --select marts
dbt test --select marts
```

**4. Launch the dashboard**
```bash
streamlit run dashboard/app.py
```

## Data quality notes

Real API data rarely matches documentation exactly. Two issues found and handled while building the silver layer:

- **OpenAQ uses `-999.0` as a "no reading" sentinel value**, not `null`. Left unfiltered, this would have silently corrupted every downstream average. Handled with an explicit `where value >= 0` filter in `stg_openaq`.
- **OpenAQ's response structure separates sensor metadata from readings** — a station's `location.sensors[]` array holds pollutant/unit info, while `measurements.results[]` only references a sensor by ID. Reconstructing a reading's pollutant type requires an explicit join between the two, which isn't obvious from the docs alone.

## Status

- [x] Bronze ingestion (weather + air quality)
- [x] Silver models (cleaned, deduplicated, tested)
- [ ] Gold marts
- [ ] Dagster orchestration
- [ ] Streamlit dashboard
- [ ] CI/CD
- [ ] Terraform IaC

## License

MIT
