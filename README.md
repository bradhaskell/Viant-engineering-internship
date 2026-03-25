# CTV Ad Analytics Pipeline

A modular data engineering pipeline simulating a CTV (Connected TV) programmatic advertising platform — built to demonstrate backend engineering skills aligned with Viant Technology's stack.

## Architecture

```
[generator] → PostgreSQL (raw.events)
                    ↓
             [transformer] → campaign_metrics, hourly_stats
                    ↓
               [FastAPI]  →  GET /campaigns, /{id}, /{id}/hourly
                    ↓
              [Streamlit]  →  KPI cards, hourly chart, CTV donut
```

Five Docker Compose services. Each has a single responsibility and communicates through PostgreSQL.

## Stack alignment with Viant Technology

| This project | Viant's stack |
|---|---|
| PostgreSQL | Cloud SQL / Aurora / PostgreSQL |
| Python event generator | Kafka producer (Tier 2) |
| SQL transformer | Dataflow / dbt transforms |
| FastAPI REST API | Internal reporting APIs |
| Streamlit dashboard | Potens.io reporting platform |
| Docker Compose | Docker / Kubernetes |
| GCP Cloud Run (Tier 1 cloud) | GCP Cloud Run / GKE |

## How to run

### Prerequisites
- Docker Desktop
- Docker Compose v2

### Start the pipeline

```bash
cp .env.example .env
docker-compose up --build
```

- API: http://localhost:8000
- Dashboard: http://localhost:8501
- API docs: http://localhost:8000/docs

### Run tests

```bash
# Requires the Compose stack to be running (for the Postgres DB)
TEST_DATABASE_URL=postgresql://ctv:ctv_password@localhost:5432/ctv \
  pytest services/ -v --ignore=services/dashboard
```

## Tiers

| Tier | What it adds | Status |
|---|---|---|
| **1 — Core pipeline** | Generator, transformer, FastAPI, Streamlit, Docker Compose, GCP | ✅ Complete |
| **2 — Kafka streaming** | Apache Kafka event queue, Pydantic validation, publisher metrics | 🔜 Planned |
| **3 — BigQuery + Airflow** | BigQuery warehouse, Airflow orchestration, CTR prediction, GKE | 🔜 Planned |
