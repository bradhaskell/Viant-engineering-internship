def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


import psycopg2
import sys, os
import importlib.util as _ilu

# Load transformer main by absolute path to avoid colliding with api's 'main' in sys.modules
_transformer_path = os.path.join(os.path.dirname(__file__), "../../transformer/main.py")
_spec = _ilu.spec_from_file_location("transformer_main", _transformer_path)
_transformer_main = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_transformer_main)
run_campaign_metrics = _transformer_main.run_campaign_metrics
run_hourly_stats = _transformer_main.run_hourly_stats


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
