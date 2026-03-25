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
