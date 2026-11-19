import json
from pathlib import Path

import requests

import db
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

SCHEMA = """
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'reflections')
CREATE TABLE reflections (
    id INT IDENTITY(1,1) PRIMARY KEY,
    hackathon_id INT NOT NULL,
    went_well NVARCHAR(MAX) NULL,
    went_badly NVARCHAR(MAX) NULL,
    lesson NVARCHAR(MAX) NULL,
    created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'checklist_rules')
CREATE TABLE checklist_rules (
    id INT IDENTITY(1,1) PRIMARY KEY,
    condition_field NVARCHAR(64) NOT NULL,
    condition_value NVARCHAR(64) NOT NULL,
    item NVARCHAR(255) NOT NULL,
    CONSTRAINT uq_checklist_rule UNIQUE (condition_field, condition_value, item)
);
"""


def setup_db(conn):
    cur = conn.cursor()
    for statement in SCHEMA.split(";"):
        sql = statement.strip()
        if sql:
            cur.execute(sql)
    conn.commit()
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
