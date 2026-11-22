import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import db  # noqa: E402
import service  # noqa: E402


@pytest.fixture
def conn():
    connection = db.connect(retries=10)
    service.setup_db(connection)
    connection.cursor().execute("DELETE FROM reflections")
    connection.commit()
    yield connection
    connection.close()


@pytest.fixture
def client(conn):
    import app

    return app.create_app().test_client()
