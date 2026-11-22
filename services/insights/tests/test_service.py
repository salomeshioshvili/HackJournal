import pytest

import migrate
import service


def test_second_migration_run_applies_nothing(conn):
    assert migrate.run_migrations(conn) == []


def test_split_batches_on_go_lines():
    assert migrate.split_batches("SELECT 1\nGO\nSELECT 2") == ["SELECT 1", "SELECT 2"]


def test_failing_migration_is_rolled_back_and_not_recorded(conn, tmp_path):
    (tmp_path / "999_broken.sql").write_text("CREATE TABLE broken_tmp (id INT);\nSELECT * FROM missing_table;")
    with pytest.raises(Exception):
        migrate.run_migrations(conn, tmp_path)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS n FROM schema_migrations WHERE version = '999_broken.sql'")
    assert cur.fetchone()["n"] == 0
    cur.execute("SELECT COUNT(*) AS n FROM sys.tables WHERE name = 'broken_tmp'")
    assert cur.fetchone()["n"] == 0


def test_checklist_rules_seeded_once(conn):
    first = service.list_checklist_rules(conn)
    service.seed_if_empty(conn)
    assert len(first) > 0
    assert len(service.list_checklist_rules(conn)) == len(first)


def test_add_and_list_reflections(conn):
    new_id = service.add_reflection(
        conn, {"hackathon_id": 7, "went_well": "Demo", "went_badly": None, "lesson": "Sleep"}
    )
    rows = service.list_reflections(conn)
    assert rows[0]["id"] == new_id
    assert rows[0]["hackathon_id"] == 7


def test_label_reflections_uses_log_names():
    reflections = [{"id": 1, "hackathon_id": 7}, {"id": 2, "hackathon_id": 8}]
    labelled = service.label_reflections(reflections, [{"id": 7, "name": "Junction"}])
    assert labelled[0]["hackathon_name"] == "Junction"
    assert labelled[1]["hackathon_name"] == "Unknown"
