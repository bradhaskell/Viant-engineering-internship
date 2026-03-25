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
