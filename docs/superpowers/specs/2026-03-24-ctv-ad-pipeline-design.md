# CTV Ad Analytics Pipeline — Design Spec

**Date:** 2026-03-24
**Project:** ctv-ad-pipeline
**Target role:** Engineering Internship – Summer 2026, Viant Technology
**Author:** Bradley Haskell

---

## Overview

A modular, containerized data engineering pipeline that simulates a CTV (Connected TV) programmatic advertising platform. Raw ad events (impressions, clicks, bids) flow through the pipeline, get transformed into campaign performance metrics, and are served via a REST API and Streamlit dashboard.

The project is designed in three buildable tiers — each fully functional on its own, each adding depth aligned with Viant's actual tech stack.

---

## Target Audience

Engineering internship interviewers at Viant Technology. The project should demonstrate:
- Backend software engineering (not just data analysis)
- Understanding of ad tech data pipelines
- Proficiency in Python, SQL, REST APIs, and containerization
- Familiarity with GCP services (Viant's analytics cloud)

---

## Three-Tier Architecture

### Tier 1 — Beginner: Core Pipeline
*Skills demonstrated: Python, SQL, FastAPI, PostgreSQL, Docker Compose, GCP Cloud Run*

```
[generator] → PostgreSQL (raw.events)
                    ↓
             [transformer] → transformed.campaign_metrics
                             transformed.hourly_stats
                    ↓
               [FastAPI]
                    ↓
              [Streamlit]
```

Five Docker Compose services: `postgres`, `generator`, `transformer`, `api`, `dashboard`.

---

### Tier 2 — Intermediate: Kafka Streaming
*Adds: Apache Kafka, event-driven ingestion, Pydantic schema validation*

```
[generator] → Kafka topic: ctv_ad_events → [ingestion consumer] → PostgreSQL
                                                                        ↓
                                                               [transformer]
                                                                        ↓
                                                                   [FastAPI]
                                                                        ↓
                                                                  [Streamlit]
```

Generator publishes to a Kafka topic. A dedicated ingestion service consumes events, validates them with Pydantic, and writes to PostgreSQL. Mirrors Viant's confirmed Kafka-based event pipeline.

---

### Tier 3 — Advanced: BigQuery + Airflow
*Adds: Google BigQuery, Apache Airflow, GKE, Terraform*

```
[generator] → Kafka → [ingestion] → PostgreSQL (staging)
                                          ↓
                              [Airflow DAG orchestrates:]
                                   ├── transform job → BigQuery (viant_analytics dataset)
                                   └── export job   → GCS (raw archive)
                                          ↓
                                      [FastAPI] ← queries BigQuery
                                          ↓
                                     [Streamlit]
```

Airflow replaces the standalone transformer. Aggregated data lands in BigQuery — matching Viant's Potens.io analytics platform. Cloud deployment upgrades to GKE with Terraform for infrastructure as code.

---

## Data Model

### Tier 1: PostgreSQL Schemas

**`raw.events`**
| Column | Type | Notes |
|---|---|---|
| event_id | UUID PK | |
| timestamp | TIMESTAMPTZ | Event time |
| event_type | VARCHAR | `impression`, `click`, `bid` |
| campaign_id | VARCHAR | |
| advertiser_id | VARCHAR | |
| publisher_id | VARCHAR | |
| content_type | VARCHAR | `ctv`, `mobile`, `desktop` |
| device_type | VARCHAR | `smart_tv`, `roku`, `fire_tv`, `desktop` |
| bid_price | NUMERIC(10,4) | CPM in USD |
| geo_region | VARCHAR | US region |
| created_at | TIMESTAMPTZ | Insertion time |

**`transformed.campaign_metrics`** (daily rollup)
| Column | Type | Notes |
|---|---|---|
| campaign_id | VARCHAR | |
| date | DATE | |
| impressions | INTEGER | |
| clicks | INTEGER | |
| ctr | NUMERIC | clicks / impressions |
| total_spend | NUMERIC | Sum of bid prices |
| avg_bid_price | NUMERIC | |
| unique_devices | INTEGER | |
| ctv_impressions | INTEGER | CTV-specific subset |
| updated_at | TIMESTAMPTZ | |

**`transformed.hourly_stats`** (hourly time series)
| Column | Type | Notes |
|---|---|---|
| campaign_id | VARCHAR | |
| hour | TIMESTAMPTZ | |
| impressions | INTEGER | |
| clicks | INTEGER | |
| spend | NUMERIC | |

### Tier 2 Addition: Ingestion Tracking

**`raw.ingestion_log`**
| Column | Type | Notes |
|---|---|---|
| id | SERIAL PK | |
| kafka_offset | BIGINT | |
| kafka_partition | INTEGER | |
| event_id | UUID FK | References raw.events |
| processed_at | TIMESTAMPTZ | |
| status | VARCHAR | `success`, `failed`, `skipped` |
| error_message | TEXT | |

### Tier 3 Addition: BigQuery Datasets

| Dataset | Tables | Purpose |
|---|---|---|
| `viant_raw` | `events` | Raw events promoted from PostgreSQL |
| `viant_analytics` | `campaign_metrics`, `hourly_stats`, `advertiser_summary` | SQL-transformed reporting tables |

---

## API Design

Built with **FastAPI**. Dashboard is the only consumer — no direct DB access from the frontend.

### Tier 1: Core Read Endpoints

```
GET  /health
GET  /campaigns
GET  /campaigns/{campaign_id}
GET  /campaigns/{campaign_id}/hourly
```

### Tier 2 Additions

```
GET  /campaigns?start_date=&end_date=&content_type=&limit=&offset=
GET  /advertisers/{advertiser_id}/campaigns
POST /events
GET  /campaigns/{campaign_id}/publishers
```

### Tier 3 Addition: CTR Prediction

```
POST /predict/ctr
```

Request:
```json
{
  "content_type": "ctv",
  "device_type": "roku",
  "geo_region": "west",
  "bid_price": 3.50,
  "hour_of_day": 20
}
```

Response:
```json
{
  "predicted_ctr": 0.024,
  "confidence": 0.81,
  "model_version": "v1.2"
}
```

Model: scikit-learn logistic regression or gradient boosting, trained on synthetic `raw.events` data, loaded at API startup.

---

## Dashboard Design

Built with **Streamlit**, consuming only the FastAPI layer.

### Tier 1: Campaign Analytics View
- Campaign selector dropdown
- KPI cards: Impressions, Clicks, CTR, Total Spend, CTV %
- Hourly impressions line chart
- CTV vs. non-CTV donut chart

### Tier 2 Additions
- Date range picker
- Multi-campaign comparison chart
- Publisher breakdown table (sortable)
- Auto-refresh toggle (polls API every 30s)

### Tier 3 Addition: CTR Prediction Panel
- Input form: content type, device, region, bid price, hour of day
- Live prediction result with confidence bar
- Feature importance chart

---

## Infrastructure

### Tier 1: Docker Compose + GCP

**Local `docker-compose.yml` services:** `postgres`, `generator`, `transformer`, `api`, `dashboard`

**Cloud (GCP):**
| Component | GCP Service |
|---|---|
| API | Cloud Run |
| Dashboard | Cloud Run |
| Database | Cloud SQL (PostgreSQL 15) |
| Container registry | Artifact Registry |
| CI/CD | GitHub Actions → Artifact Registry → Cloud Run |

### Tier 2: Add Kafka

- Bitnami Kafka image added to Docker Compose (single-broker, KRaft mode — no Zookeeper)
- `ingestion` consumer service added
- Cloud option: swap local Kafka for **GCP Pub/Sub** (Viant's cloud-native equivalent)

### Tier 3: Airflow + BigQuery + Kubernetes

**Local:** Airflow added to Docker Compose. DAG runs transformer → BigQuery load on schedule.

**Cloud:**
| Component | GCP Service |
|---|---|
| Orchestration | Cloud Composer (managed Airflow) |
| Warehouse | BigQuery |
| Raw archive | Cloud Storage (GCS) |
| Container orchestration | GKE (Kubernetes) |
| Infrastructure as code | Terraform |

---

## Tech Stack Summary

| Layer | Tier 1 | Tier 2 | Tier 3 |
|---|---|---|---|
| Language | Python 3.11 | Python 3.11 | Python 3.11 |
| Event stream | Direct DB insert | Apache Kafka | Apache Kafka |
| Database | PostgreSQL 15 | PostgreSQL 15 | PostgreSQL (staging) + BigQuery |
| Orchestration | Python script | Python script | Apache Airflow |
| API | FastAPI | FastAPI | FastAPI |
| Dashboard | Streamlit | Streamlit | Streamlit |
| Validation | — | Pydantic | Pydantic |
| ML | — | — | scikit-learn |
| Local infra | Docker Compose | Docker Compose | Docker Compose |
| Cloud | Cloud Run + Cloud SQL | Cloud Run + Cloud SQL | GKE + BigQuery + Cloud Composer |
| IaC | — | — | Terraform |
| CI/CD | GitHub Actions | GitHub Actions | GitHub Actions |

---

## Project Structure

```
ctv-ad-pipeline/
├── docker-compose.yml
├── docker-compose.kafka.yml        # Tier 2 override
├── docker-compose.airflow.yml      # Tier 3 override
├── services/
│   ├── generator/
│   │   ├── Dockerfile
│   │   ├── main.py
│   │   └── requirements.txt
│   ├── ingestion/                  # Tier 2
│   │   ├── Dockerfile
│   │   ├── consumer.py
│   │   ├── models.py               # Pydantic schemas
│   │   └── requirements.txt
│   ├── transformer/
│   │   ├── Dockerfile
│   │   ├── main.py
│   │   ├── queries/
│   │   │   ├── campaign_metrics.sql
│   │   │   └── hourly_stats.sql
│   │   └── requirements.txt
│   ├── api/
│   │   ├── Dockerfile
│   │   ├── main.py
│   │   ├── routers/
│   │   │   ├── campaigns.py
│   │   │   ├── advertisers.py
│   │   │   └── predict.py          # Tier 3
│   │   ├── models/
│   │   │   └── ml_model.pkl        # Tier 3
│   │   └── requirements.txt
│   └── dashboard/
│       ├── Dockerfile
│       ├── app.py
│       └── requirements.txt
├── db/
│   └── init.sql                    # Schema creation
├── dags/                           # Tier 3 — Airflow DAGs
│   └── ctv_pipeline_dag.py
├── terraform/                      # Tier 3
│   ├── main.tf
│   ├── variables.tf
│   └── outputs.tf
├── .github/
│   └── workflows/
│       └── deploy.yml
└── README.md
```

---

## Success Criteria

- `docker-compose up` starts the full pipeline locally with no manual steps
- Generator produces synthetic CTV events continuously
- Transformer aggregates raw events into campaign metrics
- API returns correct JSON for all endpoints
- Dashboard displays live campaign data pulled from the API
- All services deployed to GCP and accessible via public URLs
- README explains the architecture, how to run it, and maps it to Viant's stack
