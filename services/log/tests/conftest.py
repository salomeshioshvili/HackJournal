import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import db  # noqa: E402
import service  # noqa: E402

TABLES = ("project_technologies", "projects", "hackathon_teammates", "teammates", "hackathons")


@pytest.fixture
def conn():
    connection = db.connect(retries=10)
    service.setup_db(connection)
    cur = connection.cursor()
    for table in TABLES:
        cur.execute(f"DELETE FROM {table}")
    connection.commit()
    yield connection
    connection.close()


@pytest.fixture
def make_hackathon(conn):
    def _make(**overrides):
        data = {
            "name": "Test Hack",
            "mode": "online",
            "start_date": "2026-12-01",
            "end_date": "2026-12-02",
        }
        data.update(overrides)
        return service.add_hackathon(conn, data)

    return _make


@pytest.fixture
def client(conn):
    import app

    return app.create_app().test_client()
