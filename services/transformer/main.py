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


def run_campaign_metrics(conn: psycopg2.extensions.connection) -> None:
    sql = load_sql("campaign_metrics.sql")
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()


def run_hourly_stats(conn: psycopg2.extensions.connection) -> None:
    sql = load_sql("hourly_stats.sql")
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()


def _connect() -> psycopg2.extensions.connection:
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
        interval_str = os.getenv("TRANSFORMER_INTERVAL_SECONDS", "30")
        try:
            interval = float(interval_str)
            if interval <= 0:
                raise ValueError("Interval must be positive")
        except ValueError:
            logger.warning("Invalid TRANSFORMER_INTERVAL_SECONDS=%r, using 30.0", interval_str)
            interval = 30.0

        conn = _connect()
        logger.info("Transformer started. Running every %.0fs", interval)
        try:
            while True:
                try:
                    run_campaign_metrics(conn)
                    run_hourly_stats(conn)
                    logger.info("Transformations complete")
                except psycopg2.DatabaseError as e:
                    logger.error("Transform error: %s — reconnecting", e)
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
