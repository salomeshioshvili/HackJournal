"""Cross-seam integration test: insights calls the real log service over HTTP."""

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
import requests

import db

LOG_DIR = Path(__file__).resolve().parents[2] / "log"
LOG_PORT = 18001


@pytest.fixture(scope="module")
def log_url():
    database_url = os.environ.get("LOG_DATABASE_URL")
    if not database_url:
        pytest.skip("LOG_DATABASE_URL is not set")
    env = {k: v for k, v in os.environ.items() if not k.startswith("COV_")}
    env.update({"DATABASE_URL": database_url, "PORT": str(LOG_PORT)})
    process = subprocess.Popen([sys.executable, "app.py"], cwd=LOG_DIR, env=env)
    url = f"http://127.0.0.1:{LOG_PORT}"
    for _ in range(60):
        try:
            if requests.get(f"{url}/health", timeout=1).status_code == 200:
                break
        except requests.RequestException:
            pass
        time.sleep(1)
    else:
        process.terminate()
        pytest.fail("log service did not start")
    yield url
    process.terminate()
    process.wait(timeout=10)


def _attended_hackathon(log_url):
    created = requests.post(
        f"{log_url}/api/hackathons",
        json={"name": "Seam Hack", "mode": "online", "start_date": "2026-11-01", "end_date": "2026-11-02"},
        timeout=5,
    ).json()
    for status in ("applied", "accepted", "attended"):
        requests.post(f"{log_url}/api/hackathons/{created['id']}/status", json={"status": status}, timeout=5)
    requests.post(
        f"{log_url}/api/hackathons/{created['id']}/projects",
        json={"name": "Seam Project", "result": "winner", "technologies": "python"},
        timeout=5,
    )
    return created["id"]


def test_reflection_and_summary_across_the_seam(client, log_url, monkeypatch):
    monkeypatch.setattr(db, "LOG_URL", log_url)
    hackathon_id = _attended_hackathon(log_url)

    created = client.post(
        "/api/reflections", json={"hackathon_id": hackathon_id, "lesson": "Ship early"}
    )
    assert created.status_code == 201

    summary = client.get("/api/summary").get_json()
    assert summary["stats"]["won"] >= 1
    names = [r["hackathon_name"] for r in summary["reflections"]]
    assert "Seam Hack" in names

    checklist = client.get(f"/api/checklist/{hackathon_id}").get_json()
    assert "Stable internet and headset" in checklist["items"]


def test_reflection_for_unknown_hackathon_is_rejected(client, log_url, monkeypatch):
    monkeypatch.setattr(db, "LOG_URL", log_url)
    response = client.post("/api/reflections", json={"hackathon_id": 999999, "lesson": "x"})
    assert response.status_code == 400
    assert client.get("/api/checklist/999999").status_code == 404
