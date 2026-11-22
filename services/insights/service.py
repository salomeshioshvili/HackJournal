import json
from pathlib import Path

import requests

import db
from migrate import run_migrations
from rules import (
    attended,
    compute_stats,
    find_record,
    generate_checklist,
    skill_gaps,
    upcoming,
    validate_reflection,
)

SEED_PATH = Path(__file__).parent / "seed.json"


def setup_db(conn):
    run_migrations(conn)
    seed_if_empty(conn)


def seed_if_empty(conn):
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS n FROM checklist_rules")
    if cur.fetchone()["n"] > 0:
        return
    seed = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    for rule in seed["checklist_rules"]:
        cur.execute(
            """
            INSERT INTO checklist_rules (condition_field, condition_value, item)
            VALUES (%s, %s, %s)
            """,
            (rule["condition_field"], rule["condition_value"], rule["item"]),
        )
    conn.commit()


def fetch_log_records():
    """Cross-seam call: ask the log service for full records."""
    response = requests.get(
        f"{db.LOG_URL}/api/records",
        timeout=db.LOG_TIMEOUT_S,
    )
    response.raise_for_status()
    return response.json()


def list_checklist_rules(conn):
    cur = conn.cursor()
    cur.execute(
        "SELECT condition_field, condition_value, item FROM checklist_rules ORDER BY id"
    )
    return [dict(row) for row in cur.fetchall()]


def list_reflections(conn):
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, hackathon_id, went_well, went_badly, lesson,
               CONVERT(varchar(33), created_at, 126) AS created_at
        FROM reflections ORDER BY id DESC
        """
    )
    return [dict(row) for row in cur.fetchall()]


def add_reflection(conn, data: dict) -> int:
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO reflections (hackathon_id, went_well, went_badly, lesson)
        OUTPUT INSERTED.id
        VALUES (%s, %s, %s, %s)
        """,
        (data["hackathon_id"], data["went_well"], data["went_badly"], data["lesson"]),
    )
    new_id = cur.fetchone()["id"]
    conn.commit()
    return new_id


def label_reflections(reflections, records):
    names = {record["id"]: record["name"] for record in records}
    return [
        {**reflection, "hackathon_name": names.get(reflection["hackathon_id"], "Unknown")}
        for reflection in reflections
    ]


# re-export helpers used by app
__all__ = [
    "setup_db",
    "fetch_log_records",
    "list_checklist_rules",
    "list_reflections",
    "add_reflection",
    "label_reflections",
    "compute_stats",
    "skill_gaps",
    "upcoming",
    "attended",
    "find_record",
    "generate_checklist",
    "validate_reflection",
]
