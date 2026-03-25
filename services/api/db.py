import os
import psycopg2
from psycopg2.extras import RealDictCursor


def get_db():
    """FastAPI dependency — yields a psycopg2 RealDictCursor connection."""
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.getenv("DB_NAME", "ctv"),
        user=os.getenv("DB_USER", "ctv"),
        password=os.getenv("DB_PASSWORD", "ctv_password"),
        cursor_factory=RealDictCursor,
    )
    try:
        yield conn
    finally:
        conn.close()
