from datetime import date

import pytest

import migrate
import service


def test_second_migration_run_applies_nothing(conn):
    assert migrate.run_migrations(conn) == []


def test_split_batches_on_go_lines():
    assert migrate.split_batches("SELECT 1\nGO\n\n go \nSELECT 2\n") == ["SELECT 1", "SELECT 2"]


def test_failing_migration_is_rolled_back_and_not_recorded(conn, tmp_path):
    (tmp_path / "999_broken.sql").write_text("CREATE TABLE broken_tmp (id INT);\nSELECT * FROM missing_table;")
    with pytest.raises(Exception):
        migrate.run_migrations(conn, tmp_path)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS n FROM schema_migrations WHERE version = '999_broken.sql'")
    assert cur.fetchone()["n"] == 0
    cur.execute("SELECT COUNT(*) AS n FROM sys.tables WHERE name = 'broken_tmp'")
    assert cur.fetchone()["n"] == 0


def test_seed_only_when_empty(conn):
    service.seed_if_empty(conn)
    first = len(service.list_hackathons(conn))
    service.seed_if_empty(conn)
    assert first > 0
    assert len(service.list_hackathons(conn)) == first


def test_add_and_get_hackathon(conn, make_hackathon):
    new_id = make_hackathon(name="Junction", location="Helsinki", application_deadline="2026-11-24")
    h = service.get_hackathon(conn, new_id)
    assert h["name"] == "Junction"
    assert h["status"] == "interested"
    assert h["projects"] == [] and h["teammates"] == []
    assert service.get_hackathon(conn, new_id + 999) is None


def test_list_hackathons_sets_urgency_only_for_interested(conn, make_hackathon):
    make_hackathon(name="Soon", application_deadline="2026-11-24")
    other = make_hackathon(name="Applied", application_deadline="2026-11-24")
    service.change_status(conn, other, "applied")
    rows = {h["name"]: h for h in service.list_hackathons(conn, today=date(2026, 11, 22))}
    assert rows["Soon"]["urgency"] == "urgent"
    assert rows["Applied"]["urgency"] == "none"


def test_change_status_rules(conn, make_hackathon):
    new_id = make_hackathon()
    service.change_status(conn, new_id, "applied")
    assert service.get_hackathon(conn, new_id)["status"] == "applied"
    with pytest.raises(ValueError):
        service.change_status(conn, new_id, "interested")
    with pytest.raises(LookupError):
        service.change_status(conn, new_id + 999, "applied")
    assert service.next_statuses("applied") == ["accepted", "rejected", "skipped"]


def test_add_teammate_is_idempotent(conn, make_hackathon):
    new_id = make_hackathon()
    service.add_teammate(conn, new_id, "Ana")
    service.add_teammate(conn, new_id, " Ana ")
    assert service.get_hackathon(conn, new_id)["teammates"] == ["Ana"]
    with pytest.raises(ValueError):
        service.add_teammate(conn, new_id, "  ")


def _attended(conn, make_hackathon):
    new_id = make_hackathon()
    for status in ("applied", "accepted", "attended"):
        service.change_status(conn, new_id, status)
    return new_id


def test_add_project_with_technologies(conn, make_hackathon):
    new_id = _attended(conn, make_hackathon)
    service.add_project(conn, new_id, "Sleep Inbox", "winner", "Python, React")
    project = service.get_hackathon(conn, new_id)["projects"][0]
    assert project["name"] == "Sleep Inbox"
    assert project["technologies"] == ["python", "react"]


def test_add_project_errors(conn, make_hackathon):
    not_attended = make_hackathon()
    with pytest.raises(ValueError, match="attended"):
        service.add_project(conn, not_attended, "X", "winner", "")
    attended = _attended(conn, make_hackathon)
    with pytest.raises(ValueError, match="name"):
        service.add_project(conn, attended, " ", "winner", "")
    with pytest.raises(ValueError, match="Result"):
        service.add_project(conn, attended, "X", "champion", "")


def test_list_records_returns_full_records(conn, make_hackathon):
    new_id = _attended(conn, make_hackathon)
    service.add_teammate(conn, new_id, "Ana")
    records = service.list_records(conn)
    assert [r["id"] for r in records] == [new_id]
    assert records[0]["teammates"] == ["Ana"]
