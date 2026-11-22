def test_health_reports_db_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json()["db"] == "ok"


def test_create_and_read_hackathon(client):
    response = client.post(
        "/api/hackathons",
        json={"name": "API Hack", "mode": "online", "start_date": "2026-12-01", "end_date": "2026-12-01"},
    )
    assert response.status_code == 201
    new_id = response.get_json()["id"]
    detail = client.get(f"/api/hackathons/{new_id}").get_json()
    assert detail["next_statuses"] == ["applied", "skipped"]
    assert client.get("/api/records").status_code == 200


def test_bad_input_and_missing_hackathon(client):
    assert client.post("/api/hackathons", json={"name": ""}).status_code == 400
    assert client.get("/api/hackathons/999999").status_code == 404
    assert client.post("/api/hackathons/999999/status", json={"status": "applied"}).status_code == 404


def test_cors_only_for_ui_origin(client, monkeypatch):
    import app

    monkeypatch.setattr(app, "UI_ORIGINS", {"http://ui.test"})
    allowed = client.get("/api/hackathons", headers={"Origin": "http://ui.test"})
    other = client.get("/api/hackathons", headers={"Origin": "http://evil.test"})
    assert allowed.headers["Access-Control-Allow-Origin"] == "http://ui.test"
    assert "Access-Control-Allow-Origin" not in other.headers
