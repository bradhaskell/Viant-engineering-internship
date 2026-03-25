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
