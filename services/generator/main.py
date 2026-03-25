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


def _connect() -> "psycopg2.connection":
    """Connect to PostgreSQL, retrying until successful."""
    required = ["DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD"]
    missing = [v for v in required if not os.getenv(v)]
    if missing:
        raise EnvironmentError(f"Missing required environment variables: {missing}")

    while True:
        try:
            conn = psycopg2.connect(
                host=os.environ["DB_HOST"],
                port=int(os.getenv("DB_PORT", "5432")),
                dbname=os.environ["DB_NAME"],
                user=os.environ["DB_USER"],
                password=os.environ["DB_PASSWORD"],
            )
            logger.info("Connected to database")
            return conn
        except psycopg2.OperationalError as e:
            logger.error("DB connection failed: %s — retrying in 5s", e)
            time.sleep(5)


def main():
    try:
        interval_str = os.getenv("GENERATOR_INTERVAL_SECONDS", "1")
        try:
            interval = float(interval_str)
            if interval <= 0:
                raise ValueError("Interval must be positive")
        except ValueError:
            logger.warning("Invalid GENERATOR_INTERVAL_SECONDS=%r, using 1.0", interval_str)
            interval = 1.0

        conn = _connect()
        logger.info("Generator started. Inserting 1 event every %.1fs", interval)
        count = 0
        try:
            while True:
                try:
                    event = generate_event()
                    insert_event(conn, event)
                    count += 1
                    if count % 100 == 0:
                        logger.info("Inserted %d events", count)
                except psycopg2.DatabaseError as e:
                    logger.error("Insert failed: %s — reconnecting", e)
                    conn.rollback()
                    conn.close()
                    conn = _connect()
                time.sleep(interval)
        finally:
            conn.close()
    except EnvironmentError as e:
        logger.critical(str(e))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
