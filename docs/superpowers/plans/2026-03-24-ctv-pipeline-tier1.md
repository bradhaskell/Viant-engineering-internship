# CTV Ad Analytics Pipeline — Tier 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a working CTV ad analytics pipeline with a synthetic event generator, SQL transformer, FastAPI, and Streamlit dashboard — all running locally via `docker-compose up`.

**Architecture:** Five Docker Compose services share a PostgreSQL 15 database. `generator` continuously inserts synthetic CTV ad events into `raw.events`. `transformer` runs SQL aggregations every 30 seconds to populate `transformed.campaign_metrics` and `transformed.hourly_stats`. `api` (FastAPI) serves those metrics over HTTP. `dashboard` (Streamlit) visualizes them by calling the API.

**Tech Stack:** Python 3.11, FastAPI 0.110, uvicorn, psycopg2-binary, Faker, Streamlit 1.32, Plotly, PostgreSQL 15, Docker Compose v2

**Note on scope:** This plan covers Tier 1 only. Tier 2 (Kafka) and Tier 3 (BigQuery + Airflow) plans will be written separately after Tier 1 passes all success criteria.

**Spec reference:** `docs/superpowers/specs/2026-03-24-ctv-ad-pipeline-design.md`

---

## File Map

| File | Responsibility |
|---|---|
| `docker-compose.yml` | Wires all 5 services, sets env vars, defines health checks |
| `.env.example` | Documents required environment variables |
| `.gitignore` | Excludes `.env`, `__pycache__`, `*.pyc`, `ml_model.pkl` |
| `db/init.sql` | Creates `raw` and `transformed` schemas and all Tier 1 tables |
| `services/generator/main.py` | `generate_event()` + insert loop (1 event/second) |
| `services/generator/requirements.txt` | psycopg2-binary, Faker |
| `services/generator/Dockerfile` | Python 3.11-slim, runs main.py |
| `services/generator/tests/test_generator.py` | Unit tests for event shape and field values |
| `services/transformer/main.py` | Runs SQL aggregations on a 30s loop |
| `services/transformer/queries/campaign_metrics.sql` | UPSERT into transformed.campaign_metrics |
| `services/transformer/queries/hourly_stats.sql` | UPSERT into transformed.hourly_stats |
| `services/transformer/requirements.txt` | psycopg2-binary |
| `services/transformer/Dockerfile` | Python 3.11-slim, runs main.py |
| `services/transformer/tests/test_transformer.py` | Integration tests: insert events → run SQL → verify counts |
| `services/api/main.py` | FastAPI app: includes router, mounts /health |
| `services/api/db.py` | `get_db()` FastAPI dependency (psycopg2 connection) |
| `services/api/routers/campaigns.py` | GET /campaigns, GET /campaigns/{id}, GET /campaigns/{id}/hourly |
| `services/api/requirements.txt` | fastapi, uvicorn, psycopg2-binary, python-dotenv |
| `services/api/Dockerfile` | Python 3.11-slim, runs uvicorn |
| `services/api/tests/conftest.py` | pytest fixtures: test DB setup/teardown, seeded data, TestClient |
| `services/api/tests/test_api.py` | Tests all 4 API endpoints |
| `services/dashboard/app.py` | Streamlit: campaign selector, KPI cards, charts |
| `services/dashboard/requirements.txt` | streamlit, requests, plotly, pandas |
| `services/dashboard/Dockerfile` | Python 3.11-slim, runs streamlit |

---

## Task 1: Project Scaffolding

**Files:**
- Create: `docker-compose.yml` (stub — final content in Task 8)
- Create: `.env.example`
- Create: `.gitignore`

- [ ] **Step 1: Create `.gitignore`**

```
.env
__pycache__/
*.pyc
*.pyo
.pytest_cache/
services/api/models/ml_model.pkl
*.egg-info/
.DS_Store
```

- [ ] **Step 2: Create `.env.example`**

```
# PostgreSQL
DB_HOST=postgres
DB_PORT=5432
DB_NAME=ctv
DB_USER=ctv
DB_PASSWORD=ctv_password

# Generator
GENERATOR_INTERVAL_SECONDS=1

# Transformer
TRANSFORMER_INTERVAL_SECONDS=30

# API
API_PORT=8000

# Dashboard
DASHBOARD_PORT=8501
```

- [ ] **Step 3: Copy `.env.example` to `.env`**

```bash
cp .env.example .env
```

- [ ] **Step 4: Create directory structure**

```bash
mkdir -p services/generator/tests \
         services/transformer/queries \
         services/transformer/tests \
         services/api/routers \
         services/api/tests \
         services/dashboard \
         db/migrations \
         .github/workflows
```

- [ ] **Step 5: Add `__init__.py` files for Python packages**

```bash
touch services/generator/__init__.py \
      services/transformer/__init__.py \
      services/api/__init__.py \
      services/api/routers/__init__.py
```

- [ ] **Step 6: Commit**

```bash
git add .gitignore .env.example services/ db/ .github/
git commit -m "chore: scaffold project structure"
```

---

## Task 2: Database Schema

**Files:**
- Create: `db/init.sql`

- [ ] **Step 1: Write failing test that verifies schema exists**

Create `services/api/tests/test_schema.py`:

```python
import os
import pytest
import psycopg2
from psycopg2.extras import RealDictCursor

DB_URL = os.getenv("TEST_DATABASE_URL", "postgresql://ctv:ctv_password@localhost:5432/ctv")

@pytest.fixture(scope="module")
def conn():
    c = psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)
    yield c
    c.close()

def test_raw_events_table_exists(conn):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'raw' AND table_name = 'events'
            ORDER BY ordinal_position
        """)
        cols = [r["column_name"] for r in cur.fetchall()]
    assert "event_id" in cols
    assert "device_id" in cols
    assert "content_type" in cols
    assert "bid_price" in cols

def test_campaign_metrics_table_exists(conn):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'transformed' AND table_name = 'campaign_metrics'
        """)
        cols = [r["column_name"] for r in cur.fetchall()]
    assert "ctr" in cols
    assert "unique_devices" in cols
    assert "ctv_impressions" in cols

def test_hourly_stats_table_exists(conn):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'transformed' AND table_name = 'hourly_stats'
        """)
        cols = [r["column_name"] for r in cur.fetchall()]
    assert "hour" in cols
    assert "spend" in cols
```

- [ ] **Step 2: Start a local Postgres to run against (requires Docker)**

```bash
docker run -d --name ctv-test-db \
  -e POSTGRES_DB=ctv \
  -e POSTGRES_USER=ctv \
  -e POSTGRES_PASSWORD=ctv_password \
  -p 5432:5432 \
  postgres:15
```

- [ ] **Step 3: Run test — expect FAIL (tables don't exist yet)**

```bash
TEST_DATABASE_URL=postgresql://ctv:ctv_password@localhost:5432/ctv \
  pytest services/api/tests/test_schema.py -v
```

Expected: `FAILED — relation "raw.events" does not exist`

- [ ] **Step 4: Write `db/init.sql`**

```sql
-- Schemas
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS transformed;

-- raw.events: one row per ad event
CREATE TABLE IF NOT EXISTS raw.events (
    event_id      UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp     TIMESTAMPTZ   NOT NULL,
    event_type    VARCHAR(20)   NOT NULL CHECK (event_type IN ('impression', 'click', 'bid')),
    campaign_id   VARCHAR(50)   NOT NULL,
    advertiser_id VARCHAR(50)   NOT NULL,
    publisher_id  VARCHAR(50)   NOT NULL,
    content_type  VARCHAR(20)   NOT NULL CHECK (content_type IN ('ctv', 'mobile', 'desktop')),
    device_id     VARCHAR(100)  NOT NULL,
    device_type   VARCHAR(50)   NOT NULL,
    bid_price     NUMERIC(10,4) NOT NULL,
    geo_region    VARCHAR(50)   NOT NULL,
    created_at    TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_events_campaign_date
    ON raw.events (campaign_id, DATE(timestamp));
CREATE INDEX IF NOT EXISTS idx_events_timestamp
    ON raw.events (timestamp);

-- transformed.campaign_metrics: daily rollup per campaign
CREATE TABLE IF NOT EXISTS transformed.campaign_metrics (
    campaign_id     VARCHAR(50)   NOT NULL,
    date            DATE          NOT NULL,
    impressions     INTEGER       NOT NULL DEFAULT 0,
    clicks          INTEGER       NOT NULL DEFAULT 0,
    ctr             NUMERIC(8,4)  NOT NULL DEFAULT 0,
    total_spend     NUMERIC(12,4) NOT NULL DEFAULT 0,
    avg_bid_price   NUMERIC(10,4) NOT NULL DEFAULT 0,
    unique_devices  INTEGER       NOT NULL DEFAULT 0,
    ctv_impressions INTEGER       NOT NULL DEFAULT 0,
    updated_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    PRIMARY KEY (campaign_id, date)
);

-- transformed.hourly_stats: hourly time series per campaign
CREATE TABLE IF NOT EXISTS transformed.hourly_stats (
    campaign_id VARCHAR(50)   NOT NULL,
    hour        TIMESTAMPTZ   NOT NULL,
    impressions INTEGER       NOT NULL DEFAULT 0,
    clicks      INTEGER       NOT NULL DEFAULT 0,
    spend       NUMERIC(12,4) NOT NULL DEFAULT 0,
    PRIMARY KEY (campaign_id, hour)
);
```

- [ ] **Step 5: Apply schema to test DB**

```bash
psql postgresql://ctv:ctv_password@localhost:5432/ctv -f db/init.sql
```

- [ ] **Step 6: Run tests — expect PASS**

```bash
TEST_DATABASE_URL=postgresql://ctv:ctv_password@localhost:5432/ctv \
  pytest services/api/tests/test_schema.py -v
```

Expected: `3 passed`

- [ ] **Step 7: Commit**

```bash
git add db/init.sql services/api/tests/test_schema.py
git commit -m "feat: add database schema for raw and transformed layers"
```

---

## Task 3: Generator Service

**Files:**
- Create: `services/generator/main.py`
- Create: `services/generator/requirements.txt`
- Create: `services/generator/tests/test_generator.py`

- [ ] **Step 1: Write failing unit tests**

Create `services/generator/tests/test_generator.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from main import generate_event

REQUIRED_FIELDS = [
    "timestamp", "event_type", "campaign_id", "advertiser_id",
    "publisher_id", "content_type", "device_id", "device_type",
    "bid_price", "geo_region",
]

def test_generate_event_has_all_fields():
    event = generate_event()
    for field in REQUIRED_FIELDS:
        assert field in event, f"Missing field: {field}"

def test_event_type_is_valid():
    valid = {"impression", "click", "bid"}
    for _ in range(50):
        assert generate_event()["event_type"] in valid

def test_content_type_is_valid():
    valid = {"ctv", "mobile", "desktop"}
    for _ in range(50):
        assert generate_event()["content_type"] in valid

def test_ctv_is_majority_content_type():
    events = [generate_event() for _ in range(200)]
    ctv_count = sum(1 for e in events if e["content_type"] == "ctv")
    assert ctv_count > 100, "CTV should be ~60% of events"

def test_bid_price_in_range():
    for _ in range(50):
        price = generate_event()["bid_price"]
        assert 0.50 <= price <= 8.00, f"bid_price out of range: {price}"

def test_device_id_is_unique():
    ids = [generate_event()["device_id"] for _ in range(20)]
    # device_ids are randomly assigned from a pool — not all unique, but format correct
    assert all(id_.startswith("dev_") for id_ in ids)
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
pytest services/generator/tests/test_generator.py -v
```

Expected: `ImportError: cannot import name 'generate_event' from 'main'`

- [ ] **Step 3: Write `services/generator/main.py`**

```python
import os
import uuid
import random
import time
import logging
from datetime import datetime, timezone

import psycopg2

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

# Pool of device IDs to simulate repeat viewers (realistic for CTV)
DEVICE_POOL = [f"dev_{uuid.uuid4()}" for _ in range(500)]
CAMPAIGNS = [f"camp_{i:03d}" for i in range(1, 6)]
ADVERTISERS = [f"adv_{i:03d}" for i in range(1, 4)]
PUBLISHERS = [f"pub_{i:03d}" for i in range(1, 11)]
GEO_REGIONS = ["west", "northeast", "southeast", "midwest", "southwest"]
DEVICE_TYPES = ["smart_tv", "roku", "fire_tv", "desktop"]


def generate_event() -> dict:
    """Return a dict representing one synthetic CTV ad event."""
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": random.choices(
            ["impression", "click", "bid"], weights=[0.70, 0.05, 0.25]
        )[0],
        "campaign_id": random.choice(CAMPAIGNS),
        "advertiser_id": random.choice(ADVERTISERS),
        "publisher_id": random.choice(PUBLISHERS),
        "content_type": random.choices(
            ["ctv", "mobile", "desktop"], weights=[0.60, 0.25, 0.15]
        )[0],
        "device_id": random.choice(DEVICE_POOL),
        "device_type": random.choice(DEVICE_TYPES),
        "bid_price": round(random.uniform(0.50, 8.00), 4),
        "geo_region": random.choice(GEO_REGIONS),
    }


def insert_event(conn, event: dict) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO raw.events
                (timestamp, event_type, campaign_id, advertiser_id, publisher_id,
                 content_type, device_id, device_type, bid_price, geo_region)
            VALUES
                (%(timestamp)s, %(event_type)s, %(campaign_id)s, %(advertiser_id)s,
                 %(publisher_id)s, %(content_type)s, %(device_id)s, %(device_type)s,
                 %(bid_price)s, %(geo_region)s)
            """,
            event,
        )
    conn.commit()


def main():
    interval = float(os.getenv("GENERATOR_INTERVAL_SECONDS", "1"))
    conn = psycopg2.connect(
        host=os.environ["DB_HOST"],
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
    )
    logger.info("Generator started. Inserting 1 event every %.1fs", interval)
    count = 0
    while True:
        event = generate_event()
        insert_event(conn, event)
        count += 1
        if count % 100 == 0:
            logger.info("Inserted %d events", count)
        time.sleep(interval)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Write `services/generator/requirements.txt`**

```
psycopg2-binary==2.9.9
Faker==24.0.0
```

(Faker is installed but not used directly — `generate_event` uses stdlib `random` for speed. Keep it in requirements as it may be used for name/ID generation later.)

- [ ] **Step 5: Run tests — expect PASS**

```bash
pytest services/generator/tests/test_generator.py -v
```

Expected: `6 passed`

- [ ] **Step 6: Commit**

```bash
git add services/generator/
git commit -m "feat: add generator service with synthetic CTV event generation"
```

---

## Task 4: Transformer Service

**Files:**
- Create: `services/transformer/queries/campaign_metrics.sql`
- Create: `services/transformer/queries/hourly_stats.sql`
- Create: `services/transformer/main.py`
- Create: `services/transformer/requirements.txt`
- Create: `services/transformer/tests/test_transformer.py`

- [ ] **Step 1: Write failing integration tests**

Create `services/transformer/tests/test_transformer.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timezone

DB_URL = os.getenv("TEST_DATABASE_URL", "postgresql://ctv:ctv_password@localhost:5432/ctv")


@pytest.fixture(scope="module")
def conn():
    c = psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)
    yield c
    c.close()


@pytest.fixture(autouse=True)
def clean_tables(conn):
    """Wipe test data before each test."""
    with conn.cursor() as cur:
        cur.execute("DELETE FROM transformed.campaign_metrics")
        cur.execute("DELETE FROM transformed.hourly_stats")
        cur.execute("DELETE FROM raw.events WHERE campaign_id = 'test_camp'")
    conn.commit()


def seed_events(conn, events):
    with conn.cursor() as cur:
        for e in events:
            cur.execute(
                """INSERT INTO raw.events
                   (timestamp, event_type, campaign_id, advertiser_id, publisher_id,
                    content_type, device_id, device_type, bid_price, geo_region)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (e["timestamp"], e["event_type"], e["campaign_id"], e["advertiser_id"],
                 e["publisher_id"], e["content_type"], e["device_id"], e["device_type"],
                 e["bid_price"], e["geo_region"]),
            )
    conn.commit()


def run_transformations(conn):
    from main import run_campaign_metrics, run_hourly_stats
    run_campaign_metrics(conn)
    run_hourly_stats(conn)


def test_campaign_metrics_counts_impressions(conn):
    seed_events(conn, [
        {"timestamp": "2026-03-01T10:00:00+00:00", "event_type": "impression",
         "campaign_id": "test_camp", "advertiser_id": "adv_001", "publisher_id": "pub_001",
         "content_type": "ctv", "device_id": "dev_aaa", "device_type": "roku",
         "bid_price": 2.00, "geo_region": "west"},
        {"timestamp": "2026-03-01T10:05:00+00:00", "event_type": "click",
         "campaign_id": "test_camp", "advertiser_id": "adv_001", "publisher_id": "pub_001",
         "content_type": "ctv", "device_id": "dev_bbb", "device_type": "roku",
         "bid_price": 3.00, "geo_region": "west"},
    ])
    run_transformations(conn)
    with conn.cursor() as cur:
        cur.execute(
            "SELECT * FROM transformed.campaign_metrics WHERE campaign_id = 'test_camp'"
        )
        row = cur.fetchone()
    assert row is not None
    assert row["impressions"] == 1
    assert row["clicks"] == 1
    assert row["total_spend"] == 5.00


def test_campaign_metrics_ctr_calculation(conn):
    seed_events(conn, [
        {"timestamp": "2026-03-01T10:00:00+00:00", "event_type": "impression",
         "campaign_id": "test_camp", "advertiser_id": "adv_001", "publisher_id": "pub_001",
         "content_type": "mobile", "device_id": "dev_ccc", "device_type": "desktop",
         "bid_price": 1.00, "geo_region": "west"},
        {"timestamp": "2026-03-01T10:01:00+00:00", "event_type": "impression",
         "campaign_id": "test_camp", "advertiser_id": "adv_001", "publisher_id": "pub_001",
         "content_type": "mobile", "device_id": "dev_ddd", "device_type": "desktop",
         "bid_price": 1.00, "geo_region": "west"},
        {"timestamp": "2026-03-01T10:02:00+00:00", "event_type": "click",
         "campaign_id": "test_camp", "advertiser_id": "adv_001", "publisher_id": "pub_001",
         "content_type": "mobile", "device_id": "dev_eee", "device_type": "desktop",
         "bid_price": 1.00, "geo_region": "west"},
    ])
    run_transformations(conn)
    with conn.cursor() as cur:
        cur.execute(
            "SELECT ctr FROM transformed.campaign_metrics WHERE campaign_id = 'test_camp'"
        )
        row = cur.fetchone()
    # 1 click / 2 impressions = 0.5
    assert float(row["ctr"]) == 0.5


def test_campaign_metrics_unique_devices(conn):
    seed_events(conn, [
        {"timestamp": "2026-03-01T10:00:00+00:00", "event_type": "impression",
         "campaign_id": "test_camp", "advertiser_id": "adv_001", "publisher_id": "pub_001",
         "content_type": "ctv", "device_id": "dev_x1", "device_type": "roku",
         "bid_price": 2.00, "geo_region": "west"},
        # Same device_id — should count as 1 unique
        {"timestamp": "2026-03-01T10:01:00+00:00", "event_type": "impression",
         "campaign_id": "test_camp", "advertiser_id": "adv_001", "publisher_id": "pub_001",
         "content_type": "ctv", "device_id": "dev_x1", "device_type": "roku",
         "bid_price": 2.00, "geo_region": "west"},
        {"timestamp": "2026-03-01T10:02:00+00:00", "event_type": "impression",
         "campaign_id": "test_camp", "advertiser_id": "adv_001", "publisher_id": "pub_001",
         "content_type": "ctv", "device_id": "dev_x2", "device_type": "smart_tv",
         "bid_price": 2.00, "geo_region": "west"},
    ])
    run_transformations(conn)
    with conn.cursor() as cur:
        cur.execute(
            "SELECT unique_devices FROM transformed.campaign_metrics WHERE campaign_id = 'test_camp'"
        )
        row = cur.fetchone()
    assert row["unique_devices"] == 2


def test_hourly_stats_bucketed_correctly(conn):
    seed_events(conn, [
        {"timestamp": "2026-03-01T10:05:00+00:00", "event_type": "impression",
         "campaign_id": "test_camp", "advertiser_id": "adv_001", "publisher_id": "pub_001",
         "content_type": "ctv", "device_id": "dev_h1", "device_type": "roku",
         "bid_price": 2.00, "geo_region": "west"},
        # Same campaign but different hour bucket
        {"timestamp": "2026-03-01T11:05:00+00:00", "event_type": "impression",
         "campaign_id": "test_camp", "advertiser_id": "adv_001", "publisher_id": "pub_001",
         "content_type": "ctv", "device_id": "dev_h2", "device_type": "roku",
         "bid_price": 3.00, "geo_region": "west"},
    ])
    run_transformations(conn)
    with conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) as cnt FROM transformed.hourly_stats WHERE campaign_id = 'test_camp'"
        )
        row = cur.fetchone()
    assert row["cnt"] == 2
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
TEST_DATABASE_URL=postgresql://ctv:ctv_password@localhost:5432/ctv \
  pytest services/transformer/tests/test_transformer.py -v
```

Expected: `ImportError: cannot import name 'run_campaign_metrics'`

- [ ] **Step 3: Write `services/transformer/queries/campaign_metrics.sql`**

```sql
INSERT INTO transformed.campaign_metrics (
    campaign_id, date, impressions, clicks, ctr,
    total_spend, avg_bid_price, unique_devices, ctv_impressions, updated_at
)
SELECT
    campaign_id,
    DATE(timestamp)                                                                 AS date,
    COUNT(*) FILTER (WHERE event_type = 'impression')                               AS impressions,
    COUNT(*) FILTER (WHERE event_type = 'click')                                    AS clicks,
    ROUND(
        COUNT(*) FILTER (WHERE event_type = 'click')::NUMERIC /
        NULLIF(COUNT(*) FILTER (WHERE event_type = 'impression'), 0),
        4
    )                                                                               AS ctr,
    ROUND(SUM(bid_price), 4)                                                        AS total_spend,
    ROUND(AVG(bid_price), 4)                                                        AS avg_bid_price,
    COUNT(DISTINCT device_id)                                                       AS unique_devices,
    COUNT(*) FILTER (WHERE event_type = 'impression' AND content_type = 'ctv')      AS ctv_impressions,
    NOW()                                                                           AS updated_at
FROM raw.events
GROUP BY campaign_id, DATE(timestamp)
ON CONFLICT (campaign_id, date) DO UPDATE SET
    impressions     = EXCLUDED.impressions,
    clicks          = EXCLUDED.clicks,
    ctr             = EXCLUDED.ctr,
    total_spend     = EXCLUDED.total_spend,
    avg_bid_price   = EXCLUDED.avg_bid_price,
    unique_devices  = EXCLUDED.unique_devices,
    ctv_impressions = EXCLUDED.ctv_impressions,
    updated_at      = EXCLUDED.updated_at;
```

- [ ] **Step 4: Write `services/transformer/queries/hourly_stats.sql`**

```sql
INSERT INTO transformed.hourly_stats (campaign_id, hour, impressions, clicks, spend)
SELECT
    campaign_id,
    DATE_TRUNC('hour', timestamp)                             AS hour,
    COUNT(*) FILTER (WHERE event_type = 'impression')         AS impressions,
    COUNT(*) FILTER (WHERE event_type = 'click')              AS clicks,
    ROUND(SUM(bid_price), 4)                                  AS spend
FROM raw.events
GROUP BY campaign_id, DATE_TRUNC('hour', timestamp)
ON CONFLICT (campaign_id, hour) DO UPDATE SET
    impressions = EXCLUDED.impressions,
    clicks      = EXCLUDED.clicks,
    spend       = EXCLUDED.spend;
```

- [ ] **Step 5: Write `services/transformer/main.py`**

```python
import os
import time
import logging
from pathlib import Path

import psycopg2

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

QUERIES_DIR = Path(__file__).parent / "queries"


def load_sql(filename: str) -> str:
    return (QUERIES_DIR / filename).read_text()


def run_campaign_metrics(conn) -> None:
    sql = load_sql("campaign_metrics.sql")
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()


def run_hourly_stats(conn) -> None:
    sql = load_sql("hourly_stats.sql")
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()


def main():
    interval = float(os.getenv("TRANSFORMER_INTERVAL_SECONDS", "30"))
    conn = psycopg2.connect(
        host=os.environ["DB_HOST"],
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
    )
    logger.info("Transformer started. Running every %.0fs", interval)
    while True:
        try:
            run_campaign_metrics(conn)
            run_hourly_stats(conn)
            logger.info("Transformations complete")
        except Exception as e:
            logger.error("Transform error: %s", e)
            conn.rollback()
        time.sleep(interval)


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Write `services/transformer/requirements.txt`**

```
psycopg2-binary==2.9.9
```

- [ ] **Step 7: Run tests — expect PASS**

```bash
TEST_DATABASE_URL=postgresql://ctv:ctv_password@localhost:5432/ctv \
  pytest services/transformer/tests/test_transformer.py -v
```

Expected: `4 passed`

- [ ] **Step 8: Commit**

```bash
git add services/transformer/
git commit -m "feat: add transformer service with SQL aggregation queries"
```

---

## Task 5: API — Health + DB Connection

**Files:**
- Create: `services/api/db.py`
- Create: `services/api/main.py`
- Create: `services/api/requirements.txt`
- Create: `services/api/tests/conftest.py`
- Create: `services/api/tests/test_api.py` (health test only for now)

- [ ] **Step 1: Write failing test for /health**

Create `services/api/tests/conftest.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

import pytest
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi.testclient import TestClient

DB_URL = os.getenv("TEST_DATABASE_URL", "postgresql://ctv:ctv_password@localhost:5432/ctv")


@pytest.fixture(scope="session")
def test_conn():
    conn = psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)
    yield conn
    conn.close()


@pytest.fixture(scope="session")
def client(test_conn):
    """TestClient with DB dependency overridden to use the test database."""
    from api.main import app
    from api.db import get_db

    def override_get_db():
        yield test_conn

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def clean_tables(test_conn):
    with test_conn.cursor() as cur:
        cur.execute("DELETE FROM transformed.campaign_metrics")
        cur.execute("DELETE FROM transformed.hourly_stats")
        cur.execute("DELETE FROM raw.events")
    test_conn.commit()
```

Create `services/api/tests/test_api.py` with just the health test first:

```python
def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
cd services/api && \
TEST_DATABASE_URL=postgresql://ctv:ctv_password@localhost:5432/ctv \
  pytest tests/test_api.py::test_health -v
```

Expected: `ImportError: No module named 'api'`

- [ ] **Step 3: Write `services/api/db.py`**

```python
import os
import psycopg2
from psycopg2.extras import RealDictCursor


def get_db():
    """FastAPI dependency — yields a psycopg2 RealDictCursor connection."""
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME", "ctv"),
        user=os.getenv("DB_USER", "ctv"),
        password=os.getenv("DB_PASSWORD", "ctv_password"),
        cursor_factory=RealDictCursor,
    )
    try:
        yield conn
    finally:
        conn.close()
```

- [ ] **Step 4: Write `services/api/main.py`**

```python
from fastapi import FastAPI
from .routers import campaigns

app = FastAPI(title="CTV Ad Analytics API", version="1.0.0")
app.include_router(campaigns.router)


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}
```

- [ ] **Step 5: Write `services/api/requirements.txt`**

```
fastapi==0.110.0
uvicorn[standard]==0.27.0
psycopg2-binary==2.9.9
python-dotenv==1.0.0
httpx==0.27.0
pytest==8.0.0
```

- [ ] **Step 6: Run test — expect PASS**

```bash
cd services/api && \
TEST_DATABASE_URL=postgresql://ctv:ctv_password@localhost:5432/ctv \
  pytest tests/test_api.py::test_health -v
```

Expected: `1 passed`

- [ ] **Step 7: Commit**

```bash
git add services/api/
git commit -m "feat: add FastAPI skeleton with /health endpoint and DB dependency"
```

---

## Task 6: API — Campaigns Router

**Files:**
- Create: `services/api/routers/campaigns.py`
- Modify: `services/api/tests/test_api.py` (add campaigns tests)

- [ ] **Step 1: Add failing tests for all campaign endpoints**

Append to `services/api/tests/test_api.py`:

```python
import psycopg2

DB_URL = "postgresql://ctv:ctv_password@localhost:5432/ctv"


def seed_campaign(conn, campaign_id: str = "camp_001"):
    """Insert known events for a campaign so endpoints return data."""
    events = [
        ("2026-03-01T10:00:00+00:00", "impression", campaign_id, "adv_001", "pub_001",
         "ctv", "dev_a1", "roku", 2.50, "west"),
        ("2026-03-01T10:05:00+00:00", "impression", campaign_id, "adv_001", "pub_001",
         "ctv", "dev_a2", "smart_tv", 3.00, "west"),
        ("2026-03-01T10:10:00+00:00", "click",      campaign_id, "adv_001", "pub_001",
         "ctv", "dev_a3", "roku",     2.00, "west"),
        ("2026-03-01T11:00:00+00:00", "impression", campaign_id, "adv_001", "pub_002",
         "mobile", "dev_a1", "desktop", 1.50, "northeast"),
    ]
    with conn.cursor() as cur:
        for e in events:
            cur.execute(
                """INSERT INTO raw.events
                   (timestamp,event_type,campaign_id,advertiser_id,publisher_id,
                    content_type,device_id,device_type,bid_price,geo_region)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                e,
            )
    conn.commit()
    # Run transformer to populate aggregated tables
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../transformer"))
    from main import run_campaign_metrics, run_hourly_stats
    run_campaign_metrics(conn)
    run_hourly_stats(conn)


def test_list_campaigns_returns_list(client, test_conn):
    seed_campaign(test_conn)
    response = client.get("/campaigns")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["campaign_id"] == "camp_001"


def test_get_campaign_returns_metrics(client, test_conn):
    seed_campaign(test_conn)
    response = client.get("/campaigns/camp_001")
    assert response.status_code == 200
    data = response.json()
    assert data["campaign_id"] == "camp_001"
    assert data["impressions"] == 3
    assert data["clicks"] == 1
    assert float(data["ctr"]) == round(1 / 3, 4)
    assert data["ctv_impressions"] == 2


def test_get_campaign_not_found(client):
    response = client.get("/campaigns/does_not_exist")
    assert response.status_code == 404


def test_get_campaign_hourly(client, test_conn):
    seed_campaign(test_conn)
    response = client.get("/campaigns/camp_001/hourly")
    assert response.status_code == 200
    data = response.json()
    # Events span 2 hours (10:xx and 11:xx)
    assert len(data) == 2
    assert "hour" in data[0]
    assert "impressions" in data[0]


def test_get_campaign_hourly_not_found(client):
    response = client.get("/campaigns/does_not_exist/hourly")
    assert response.status_code == 404
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
cd services/api && \
TEST_DATABASE_URL=postgresql://ctv:ctv_password@localhost:5432/ctv \
  pytest tests/test_api.py -v -k "not test_health"
```

Expected: failures due to missing router

- [ ] **Step 3: Write `services/api/routers/campaigns.py`**

```python
from fastapi import APIRouter, Depends, HTTPException
from ..db import get_db

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


@router.get("")
def list_campaigns(conn=Depends(get_db)):
    """List all campaigns with summary metrics."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT
                campaign_id,
                SUM(impressions)                                           AS total_impressions,
                SUM(clicks)                                                AS total_clicks,
                ROUND(
                    SUM(clicks)::NUMERIC / NULLIF(SUM(impressions), 0), 4
                )                                                          AS overall_ctr,
                ROUND(SUM(total_spend), 2)                                 AS total_spend
            FROM transformed.campaign_metrics
            GROUP BY campaign_id
            ORDER BY campaign_id
        """)
        return cur.fetchall()


@router.get("/{campaign_id}")
def get_campaign(campaign_id: str, conn=Depends(get_db)):
    """Full metrics for a single campaign across all dates."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT
                campaign_id,
                MIN(date)                                                      AS start_date,
                MAX(date)                                                      AS end_date,
                SUM(impressions)                                               AS impressions,
                SUM(clicks)                                                    AS clicks,
                ROUND(
                    SUM(clicks)::NUMERIC / NULLIF(SUM(impressions), 0), 4
                )                                                              AS ctr,
                ROUND(SUM(total_spend), 2)                                     AS total_spend,
                ROUND(AVG(avg_bid_price), 4)                                   AS avg_bid_price,
                SUM(unique_devices)                                            AS unique_devices,
                SUM(ctv_impressions)                                           AS ctv_impressions
            FROM transformed.campaign_metrics
            WHERE campaign_id = %s
            GROUP BY campaign_id
        """, (campaign_id,))
        row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Campaign '{campaign_id}' not found")
    return row


@router.get("/{campaign_id}/hourly")
def get_campaign_hourly(campaign_id: str, conn=Depends(get_db)):
    """Hourly time-series data for a campaign."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT hour, impressions, clicks, spend
            FROM transformed.hourly_stats
            WHERE campaign_id = %s
            ORDER BY hour
        """, (campaign_id,))
        rows = cur.fetchall()
    if not rows:
        raise HTTPException(status_code=404, detail=f"No hourly data for '{campaign_id}'")
    return rows
```

- [ ] **Step 4: Run all API tests — expect all PASS**

```bash
cd services/api && \
TEST_DATABASE_URL=postgresql://ctv:ctv_password@localhost:5432/ctv \
  pytest tests/test_api.py -v
```

Expected: `6 passed`

- [ ] **Step 5: Commit**

```bash
git add services/api/routers/campaigns.py services/api/tests/test_api.py
git commit -m "feat: add campaigns API router with GET /campaigns, /{id}, /{id}/hourly"
```

---

## Task 7: Dashboard Service

**Files:**
- Create: `services/dashboard/app.py`
- Create: `services/dashboard/requirements.txt`

Note: Streamlit apps are not unit-tested with pytest — the test is launching it and visually verifying. This task has a manual smoke-test step instead of automated tests.

- [ ] **Step 1: Write `services/dashboard/requirements.txt`**

```
streamlit==1.32.0
requests==2.31.0
plotly==5.19.0
pandas==2.2.0
```

- [ ] **Step 2: Write `services/dashboard/app.py`**

```python
import os
import requests
import pandas as pd
import plotly.express as px
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(page_title="CTV Ad Analytics", layout="wide")
st.title("CTV Ad Analytics Dashboard")


@st.cache_data(ttl=30)
def fetch_campaigns():
    resp = requests.get(f"{API_URL}/campaigns", timeout=5)
    resp.raise_for_status()
    return resp.json()


@st.cache_data(ttl=30)
def fetch_campaign(campaign_id: str):
    resp = requests.get(f"{API_URL}/campaigns/{campaign_id}", timeout=5)
    resp.raise_for_status()
    return resp.json()


@st.cache_data(ttl=30)
def fetch_hourly(campaign_id: str):
    resp = requests.get(f"{API_URL}/campaigns/{campaign_id}/hourly", timeout=5)
    resp.raise_for_status()
    return resp.json()


# --- Sidebar: campaign selector ---
try:
    campaigns = fetch_campaigns()
except Exception as e:
    st.error(f"Cannot reach API at {API_URL}: {e}")
    st.stop()

if not campaigns:
    st.warning("No campaign data yet. The generator may still be seeding data.")
    st.stop()

campaign_ids = [c["campaign_id"] for c in campaigns]
selected = st.sidebar.selectbox("Select Campaign", campaign_ids)

auto_refresh = st.sidebar.checkbox("Auto-refresh (30s)", value=False)
if auto_refresh:
    st.cache_data.clear()

# --- KPI Cards ---
metrics = fetch_campaign(selected)
ctv_pct = (
    round(metrics["ctv_impressions"] / metrics["impressions"] * 100, 1)
    if metrics["impressions"]
    else 0
)

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Impressions",  f"{metrics['impressions']:,}")
col2.metric("Clicks",       f"{metrics['clicks']:,}")
col3.metric("CTR",          f"{float(metrics['ctr']) * 100:.2f}%")
col4.metric("Total Spend",  f"${float(metrics['total_spend']):,.2f}")
col5.metric("CTV %",        f"{ctv_pct}%")

# --- Hourly Impressions Line Chart ---
st.subheader("Hourly Impressions")
try:
    hourly = fetch_hourly(selected)
    df = pd.DataFrame(hourly)
    df["hour"] = pd.to_datetime(df["hour"])
    fig = px.line(df, x="hour", y="impressions", title=f"{selected} — Hourly Impressions")
    st.plotly_chart(fig, use_container_width=True)
except Exception:
    st.info("No hourly data available yet.")

# --- CTV vs Non-CTV Donut Chart ---
st.subheader("CTV vs. Non-CTV Impressions")
ctv = metrics.get("ctv_impressions", 0)
non_ctv = metrics.get("impressions", 0) - ctv
if ctv + non_ctv > 0:
    fig2 = px.pie(
        names=["CTV", "Non-CTV"],
        values=[ctv, non_ctv],
        hole=0.5,
        title="Content Type Breakdown",
    )
    st.plotly_chart(fig2, use_container_width=True)
```

- [ ] **Step 3: Smoke-test the dashboard locally (requires API running)**

If the API from Task 6 is running locally (e.g., `uvicorn services.api.main:app --port 8000`):

```bash
cd services/dashboard
pip install -r requirements.txt
API_URL=http://localhost:8000 streamlit run app.py
```

Expected: browser opens at `http://localhost:8501`, shows dashboard with campaign selector and charts.

- [ ] **Step 4: Commit**

```bash
git add services/dashboard/
git commit -m "feat: add Streamlit dashboard with KPI cards, hourly chart, and CTV donut"
```

---

## Task 8: Docker Compose + Dockerfiles

**Files:**
- Create: `services/generator/Dockerfile`
- Create: `services/transformer/Dockerfile`
- Create: `services/api/Dockerfile`
- Create: `services/dashboard/Dockerfile`
- Create: `docker-compose.yml`

- [ ] **Step 1: Write `services/generator/Dockerfile`**

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "main.py"]
```

- [ ] **Step 2: Write `services/transformer/Dockerfile`**

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "main.py"]
```

- [ ] **Step 3: Write `services/api/Dockerfile`**

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 4: Write `services/dashboard/Dockerfile`**

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

- [ ] **Step 5: Write `docker-compose.yml`**

```yaml
version: "3.9"

services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: ctv
      POSTGRES_USER: ctv
      POSTGRES_PASSWORD: ctv_password
    volumes:
      - ./db/init.sql:/docker-entrypoint-initdb.d/init.sql:ro
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ctv -d ctv"]
      interval: 5s
      timeout: 5s
      retries: 10
    ports:
      - "5432:5432"

  generator:
    build: ./services/generator
    environment:
      DB_HOST: postgres
      DB_PORT: 5432
      DB_NAME: ctv
      DB_USER: ctv
      DB_PASSWORD: ctv_password
      GENERATOR_INTERVAL_SECONDS: 1
    depends_on:
      postgres:
        condition: service_healthy
    restart: unless-stopped

  transformer:
    build: ./services/transformer
    environment:
      DB_HOST: postgres
      DB_PORT: 5432
      DB_NAME: ctv
      DB_USER: ctv
      DB_PASSWORD: ctv_password
      TRANSFORMER_INTERVAL_SECONDS: 30
    depends_on:
      postgres:
        condition: service_healthy
    restart: unless-stopped

  api:
    build: ./services/api
    environment:
      DB_HOST: postgres
      DB_PORT: 5432
      DB_NAME: ctv
      DB_USER: ctv
      DB_PASSWORD: ctv_password
    depends_on:
      postgres:
        condition: service_healthy
    ports:
      - "8000:8000"
    healthcheck:
      test: ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  dashboard:
    build: ./services/dashboard
    environment:
      API_URL: http://api:8000
    depends_on:
      api:
        condition: service_healthy
    ports:
      - "8501:8501"
    restart: unless-stopped

volumes:
  postgres_data:
```

- [ ] **Step 6: Build and start all services**

```bash
docker-compose up --build
```

Expected output (after ~60s for builds):
- `postgres` healthy
- `generator` logs: `Inserted 100 events`
- `transformer` logs: `Transformations complete`
- `api` logs: `Uvicorn running on http://0.0.0.0:8000`
- `dashboard` logs: `You can now view your Streamlit app`

- [ ] **Step 7: Verify API is reachable**

```bash
curl http://localhost:8000/health
```

Expected: `{"status":"ok"}`

```bash
curl http://localhost:8000/campaigns
```

Expected: JSON array of campaigns (may be empty if transformer hasn't run yet — wait 30s)

- [ ] **Step 8: Verify dashboard opens**

Open `http://localhost:8501` in a browser. You should see the dashboard with a campaign dropdown, KPI cards, and charts.

- [ ] **Step 9: Commit**

```bash
git add services/generator/Dockerfile \
        services/transformer/Dockerfile \
        services/api/Dockerfile \
        services/dashboard/Dockerfile \
        docker-compose.yml
git commit -m "feat: add Dockerfiles and docker-compose for all Tier 1 services"
```

---

## Task 9: End-to-End Verification + README

**Files:**
- Create: `README.md`
- Stop test Postgres container from Task 2

- [ ] **Step 1: Stop the test Postgres container**

```bash
docker stop ctv-test-db && docker rm ctv-test-db
```

- [ ] **Step 2: Run all unit and integration tests against the Compose DB**

The Compose stack exposes Postgres on port 5432. With the stack running:

```bash
TEST_DATABASE_URL=postgresql://ctv:ctv_password@localhost:5432/ctv \
  pytest services/ -v --ignore=services/dashboard
```

Expected: all tests pass

- [ ] **Step 3: Verify Tier 1 success criteria**

Check each item manually:

```bash
# 1. All 5 services running
docker-compose ps

# 2. Generator inserting events
docker-compose logs generator | tail -5

# 3. Transformer aggregating
docker-compose logs transformer | tail -5

# 4. All 4 API endpoints return 200
curl -s http://localhost:8000/health
curl -s http://localhost:8000/campaigns
curl -s http://localhost:8000/campaigns/camp_001
curl -s http://localhost:8000/campaigns/camp_001/hourly

# 5. Dashboard visible at http://localhost:8501
```

- [ ] **Step 4: Write `README.md`**

```markdown
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
```

- [ ] **Step 5: Final commit**

```bash
git add README.md
git commit -m "docs: add README with architecture, stack alignment, and run instructions"
```

---

## Tier 1 Complete

All success criteria from the spec should now be satisfied:

- [ ] `docker-compose up` starts all 5 services with no manual steps
- [ ] Generator produces synthetic CTV events continuously into PostgreSQL
- [ ] Transformer aggregates raw events into `campaign_metrics` and `hourly_stats`
- [ ] All four API endpoints return correct JSON
- [ ] Dashboard displays live campaign data pulled from the API

Next step: write and follow `docs/superpowers/plans/2026-03-24-ctv-pipeline-tier2.md` (Kafka streaming).
