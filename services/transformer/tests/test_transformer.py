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
    assert float(row["total_spend"]) == 5.00


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


def test_campaign_metrics_no_events_produces_no_rows(conn):
    # Seed no events for test_camp — transformation should produce no rows
    run_transformations(conn)
    with conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) as cnt FROM transformed.campaign_metrics WHERE campaign_id = 'test_camp'"
        )
        row = cur.fetchone()
    assert row["cnt"] == 0
