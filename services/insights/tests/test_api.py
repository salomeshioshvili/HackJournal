import db


def test_health_reports_db_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json()["db"] == "ok"


def test_non_numeric_hackathon_id_is_rejected(client):
    response = client.post("/api/reflections", json={"hackathon_id": "abc", "went_well": "x"})
    assert response.status_code == 400
    assert "number" in response.get_json()["error"]


def test_log_down_gives_designed_503(client, monkeypatch):
    monkeypatch.setattr(db, "LOG_URL", "http://127.0.0.1:9")
    summary = client.get("/api/summary")
    assert summary.status_code == 503
    body = summary.get_json()
    assert body["error"] == "log_unavailable"
    assert body["reflections"] == []
    assert client.get("/api/checklist/1").status_code == 503
    assert client.post("/api/reflections", json={"hackathon_id": 1, "went_well": "x"}).status_code == 503
    assert client.get("/api/reflections").status_code == 200
