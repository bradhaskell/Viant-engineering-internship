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
| unique_devices | INTEGER | `COUNT(DISTINCT device_type \|\| publisher_id)` in PostgreSQL; `APPROX_COUNT_DISTINCT` in BigQuery |
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

### Tier 2 Addition: Publisher Metrics + Ingestion Tracking

**`transformed.publisher_metrics`** (daily rollup per campaign + publisher, supports `GET /campaigns/{campaign_id}/publishers`)
| Column | Type | Notes |
|---|---|---|
| campaign_id | VARCHAR | |
| publisher_id | VARCHAR | |
| date | DATE | |
| impressions | INTEGER | |
| clicks | INTEGER | |
| ctr | NUMERIC | clicks / impressions |
| spend | NUMERIC | |
| PRIMARY KEY | (campaign_id, publisher_id, date) | |

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
| `viant_raw` | `events` | Raw events promoted from PostgreSQL staging |
| `viant_analytics` | `campaign_metrics`, `hourly_stats`, `publisher_metrics`, `advertiser_summary` | SQL-transformed reporting tables |

**`viant_analytics.advertiser_summary`** (daily rollup across all campaigns per advertiser)
| Column | Type | Notes |
|---|---|---|
| advertiser_id | STRING | |
| date | DATE | |
| total_campaigns | INTEGER | COUNT DISTINCT campaign_id |
| total_impressions | INTEGER | |
| total_clicks | INTEGER | |
| overall_ctr | NUMERIC | total_clicks / total_impressions |
| total_spend | NUMERIC | |
| PRIMARY KEY | (advertiser_id, date) | |

Used by the `GET /advertisers/{advertiser_id}/campaigns` endpoint to provide an advertiser-level rollup alongside per-campaign detail.

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

**`POST /events`** — manually inject a single synthetic ad event for testing purposes. Bypasses Kafka and writes directly to `raw.events`. Useful for demoing live data flowing through the pipeline during an interview without running the full generator. Returns the created event_id.

Request body matches the `raw.events` schema (all fields except `event_id` and `created_at`, which are auto-generated). Response: `{"event_id": "<uuid>", "status": "inserted"}`.

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

Model: scikit-learn **GradientBoostingClassifier**, trained on synthetic `raw.events` data. Features: `content_type`, `device_type`, `geo_region`, `bid_price`, `hour_of_day`. Target: binary click indicator (1 if `event_type == 'click'`, else 0). Uses `.feature_importances_` for the dashboard feature importance chart.

The model is trained by `services/api/models/train.py`, a standalone script that reads from PostgreSQL, trains the model, and serializes it to `ml_model.pkl`. The script is run once manually (or as a Tier 3 Airflow DAG step) before API startup. The API loads the `.pkl` at startup via `joblib.load()`.

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

**Kafka topic configuration:**
| Setting | Value |
|---|---|
| Topic name | `ctv_ad_events` |
| Partitions | 3 |
| Replication factor | 1 (single-broker dev setup) |
| Retention | 7 days |
| Consumer group ID | `ctv-ingestion-group` |

These values are set via environment variables in `docker-compose.kafka.yml` and consumed by both the generator (producer) and ingestion (consumer) services.

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
│   │   │   ├── hourly_stats.sql
│   │   │   └── publisher_metrics.sql   # Tier 2
│   │   └── requirements.txt
│   ├── api/
│   │   ├── Dockerfile
│   │   ├── main.py
│   │   ├── routers/
│   │   │   ├── campaigns.py
│   │   │   ├── advertisers.py
│   │   │   └── predict.py          # Tier 3
│   │   ├── models/
│   │   │   ├── train.py            # Tier 3 — trains GradientBoostingClassifier, outputs ml_model.pkl
│   │   │   └── ml_model.pkl        # Tier 3 — generated by train.py, loaded at API startup
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
