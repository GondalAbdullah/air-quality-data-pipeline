# Air Quality + Weather Pipeline — Architecture & Design Decisions

## 1. Problem statement

Ingest air quality and weather data for a handful of cities, transform it through a medallion architecture, and surface hourly correlations (does weather predict pollution spikes?) on a public dashboard. Optimize for: near-zero infrastructure cost, full local reproducibility, and every layer being individually demoable in an interview.

## 2. System architecture decisions

| Decision area | Choice | Alternatives considered | Why this one |
|---|---|---|---|
| Ingestion language | Python + `requests` | Airbyte, Fivetran | Full control, zero cost, teaches raw HTTP/API handling instead of hiding it behind a connector |
| Bronze storage | Local filesystem JSON, date-partitioned | S3, Cloudflare R2 | Zero cost, zero setup; swappable for object storage later without changing ingestion logic (just change the write path) |
| Warehouse / query engine | DuckDB | Postgres, BigQuery sandbox | Embedded (no server to run), free, fast for this data volume, still SQL-standard so skills transfer |
| Transformation | dbt-core | Plain Python/pandas scripts, Spark | Industry standard for the silver/gold layer; gives you tests, docs, and lineage graphs for free — the single highest-leverage tool for "looks professional" |
| Orchestration | Dagster | Airflow, Prefect, cron | Asset-based model maps directly onto medallion layers; strong local dev UI; native dbt integration (see prior discussion) |
| Data quality | dbt tests (`not_null`, `unique`, `accepted_values`, custom) | Great Expectations | Lighter weight, lives next to the models it tests, no separate framework to learn |
| CI/CD | GitHub Actions | GitLab CI, Jenkins | Free minutes, zero setup, universally recognized |
| IaC | Terraform | Pulumi, manual console clicks | Even a tiny `.tf` file provisioning a bucket/dataset demonstrates the skill; industry default |
| Dashboard | Streamlit Community Cloud | Metabase, Looker Studio, a custom React app | Free hosting, pure Python (no separate frontend stack to learn), fast to build |
| Containerization | Docker Compose | None, manual venv only | Makes the whole stack "clone and run" reproducible for anyone reviewing your portfolio |

## 3. Data architecture (medallion layers)

**Bronze — raw, immutable, replayable**
- Format: raw JSON exactly as returned by the API
- Partitioning: `data/bronze/{source}/{YYYY-MM-DD}/{source}_{timestamp}.json`
- Contract: never transformed, never deleted, never overwritten. This is your source of truth if anything downstream breaks.

**Silver — cleaned, conformed, queryable**
- Format: typed Parquet tables, modeled as dbt `staging` models on top of DuckDB
- Responsibilities: flatten nested JSON, normalize timezones to UTC, standardize units (e.g. µg/m³ everywhere), deduplicate, enforce schema (nulls, types)
- One staging model per bronze source (`stg_openaq`, `stg_weather`)

**Gold — business-ready, aggregated**
- Format: dbt `marts` models — the tables your dashboard actually queries
- Example marts: `fct_hourly_air_quality_weather` (joined, hourly grain, one row per city per hour), `dim_cities`
- Rule of thumb: if the dashboard needs a `GROUP BY` at query time, it should already be pre-aggregated in gold instead

## 4. Application architecture

**Design principles applied:**
- **Idempotency** — re-running an ingestion or dbt run for the same day should produce the same result, not duplicate rows (handled via partition overwrite + dbt's incremental/merge strategies)
- **Separation of concerns** — ingestion scripts only fetch and write raw data; they contain zero business logic. All transformation logic lives in dbt SQL, not scattered across Python
- **Config over hardcoding** — city list, date ranges, and API endpoints are declared once at the top of each module, not repeated inline
- **Fail fast** — `raise_for_status()` and dbt tests both stop the pipeline on bad data rather than silently propagating it downstream

**Secrets management:** API keys live in a local `.env` file (gitignored) for dev, and in GitHub Actions Secrets for CI. Never hardcoded, never committed.

## 5. File structure

```
aq-pipeline/
├── ingestion/                  # Bronze layer producers — fetch and dump raw JSON only
│   ├── fetch_openaq.py
│   └── fetch_weather.py
├── dbt_project/                # Silver + Gold transformations
│   ├── models/
│   │   ├── staging/             # Silver: one model per bronze source
│   │   │   ├── stg_openaq.sql
│   │   │   └── stg_weather.sql
│   │   └── marts/                # Gold: business-ready aggregates
│   │       └── fct_hourly_air_quality_weather.sql
│   ├── tests/                    # Custom dbt data tests
│   ├── dbt_project.yml
│   └── profiles.yml              # DuckDB connection config (gitignored if it has secrets)
├── dagster_project/             # Orchestration: assets + schedules
│   ├── assets.py                 # bronze/silver/gold as Dagster software-defined assets
│   ├── definitions.py
│   └── schedules.py
├── dashboard/                   # Streamlit app reading from gold
│   └── app.py
├── tests/                        # Python unit tests for ingestion logic
│   └── test_ingestion.py
├── terraform/                    # IaC for any cloud resources (bucket, BigQuery dataset, etc.)
│   └── main.tf
├── .github/workflows/
│   ├── ci.yml                    # Lint + dbt test on every PR
│   └── pipeline.yml              # Scheduled run of ingestion + dbt
├── data/                         # Local bronze/silver/gold storage (gitignored, except .gitkeep)
│   ├── bronze/
│   ├── silver/
│   └── gold/
├── docs/
│   └── architecture.md           # This document
├── docker-compose.yml
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

## 6. Deployment model

- **Local dev**: Docker Compose spins up nothing exotic (DuckDB is embedded) — mainly useful for pinning the Python version and running Dagster's webserver
- **Scheduled runs**: GitHub Actions cron triggers ingestion + dbt run + tests daily, commits/pushes updated gold Parquet (or writes to a small hosted DuckDB/Postgres if you want the dashboard always fresh)
- **Dashboard**: Streamlit Community Cloud pulls from the repo's gold data or a lightweight hosted DB, redeploys automatically on push

## 7. Open decisions (revisit later)

- Whether to add BigQuery as an alternative gold-layer warehouse (deferred — see stack discussion)
- Whether bronze storage moves from local filesystem to Cloudflare R2 once we want the GitHub Actions run to persist data between runs (Actions runners are ephemeral, so this becomes necessary once we're not just running locally)