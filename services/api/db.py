import os
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import HTTPException


def get_db():
    required = ["DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD"]
    missing = [v for v in required if not os.getenv(v)]
    if missing:
        raise RuntimeError(f"Missing required env vars: {', '.join(missing)}")

    try:
        conn = psycopg2.connect(
            host=os.environ["DB_HOST"],
            port=int(os.getenv("DB_PORT", "5432")),
            dbname=os.environ["DB_NAME"],
            user=os.environ["DB_USER"],
            password=os.environ["DB_PASSWORD"],
            cursor_factory=RealDictCursor,
        )
    except psycopg2.OperationalError as e:
        raise HTTPException(status_code=503, detail=f"Database unavailable: {e}")
    try:
        yield conn
    finally:
        conn.close()
