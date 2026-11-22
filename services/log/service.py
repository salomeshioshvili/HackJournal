import json
from datetime import date
from pathlib import Path

from migrate import run_migrations
from rules import (
    ALLOWED_TRANSITIONS,
    RESULTS,
    can_transition,
    country_from_location,
    parse_technologies,
    urgency,
    validate_hackathon,
)

SEED_PATH = Path(__file__).parent / "seed.json"


def _row(h):
    return {
        "id": h["id"],
        "name": h["name"],
        "location": h["location"],
        "country": h["country"],
        "mode": h["mode"],
        "start_date": str(h["start_date"])[:10] if h["start_date"] else None,
        "end_date": str(h["end_date"])[:10] if h["end_date"] else None,
        "application_deadline": str(h["application_deadline"])[:10] if h["application_deadline"] else None,
        "status": h["status"],
        "travel_funded": bool(h["travel_funded"]),
        "notes": h["notes"],
    }


def setup_db(conn):
    run_migrations(conn)
    seed_if_empty(conn)


def seed_if_empty(conn):
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS n FROM hackathons")
    if cur.fetchone()["n"] > 0:
        return
    seed = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    for h in seed["hackathons"]:
        cur.execute(
            """
            INSERT INTO hackathons
              (name, location, country, mode, start_date, end_date,
               application_deadline, status, travel_funded, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                h["name"],
                h.get("location"),
                country_from_location(h.get("location")),
                h["mode"],
                h["start_date"],
                h["end_date"],
                h.get("application_deadline"),
                h["status"],
                1 if h.get("travel_funded") else 0,
                h.get("notes"),
            ),
        )
    conn.commit()


def list_hackathons(conn, today=None):
    today = today or date.today()
    cur = conn.cursor()
    cur.execute("SELECT * FROM hackathons ORDER BY start_date, id")
    result = []
    for row in cur.fetchall():
        h = _row(row)
        if h["status"] == "interested":
            h["urgency"] = urgency(h["application_deadline"], today)
        else:
            h["urgency"] = "none"
        result.append(h)
    return result


def get_hackathon(conn, hackathon_id: int):
    cur = conn.cursor()
    cur.execute("SELECT * FROM hackathons WHERE id = %s", (hackathon_id,))
    row = cur.fetchone()
    if row is None:
        return None
    h = _row(row)
    h["projects"] = []
    cur.execute(
        "SELECT id, name, result FROM projects WHERE hackathon_id = %s ORDER BY id",
        (hackathon_id,),
    )
    for p in cur.fetchall():
        project = {"id": p["id"], "name": p["name"], "result": p["result"]}
        cur.execute(
            "SELECT technology FROM project_technologies WHERE project_id = %s ORDER BY technology",
            (p["id"],),
        )
        project["technologies"] = [r["technology"] for r in cur.fetchall()]
        h["projects"].append(project)
    cur.execute(
        """
        SELECT t.name FROM teammates t
        JOIN hackathon_teammates ht ON ht.teammate_id = t.id
        WHERE ht.hackathon_id = %s ORDER BY t.name
        """,
        (hackathon_id,),
    )
    h["teammates"] = [r["name"] for r in cur.fetchall()]
    return h


def list_records(conn):
    cur = conn.cursor()
    cur.execute("SELECT id FROM hackathons ORDER BY start_date, id")
    return [get_hackathon(conn, row["id"]) for row in cur.fetchall()]


def add_hackathon(conn, data) -> int:
    h = validate_hackathon(data)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO hackathons
          (name, location, country, mode, start_date, end_date,
           application_deadline, travel_funded, notes)
        OUTPUT INSERTED.id
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            h["name"],
            h["location"],
            h["country"],
            h["mode"],
            h["start_date"],
            h["end_date"],
            h["application_deadline"],
            h["travel_funded"],
            h["notes"],
        ),
    )
    new_id = cur.fetchone()["id"]
    conn.commit()
    return new_id


def _get_status(conn, hackathon_id: int) -> str:
    cur = conn.cursor()
    cur.execute("SELECT status FROM hackathons WHERE id = %s", (hackathon_id,))
    row = cur.fetchone()
    if row is None:
        raise LookupError("Hackathon not found.")
    return row["status"]


def change_status(conn, hackathon_id: int, new_status: str) -> None:
    current = _get_status(conn, hackathon_id)
    if not can_transition(current, new_status):
        raise ValueError(f"Cannot change status from {current} to {new_status}.")
    cur = conn.cursor()
    cur.execute("UPDATE hackathons SET status = %s WHERE id = %s", (new_status, hackathon_id))
    conn.commit()


def next_statuses(status: str):
    return sorted(ALLOWED_TRANSITIONS.get(status, set()))


def add_teammate(conn, hackathon_id: int, name) -> None:
    _get_status(conn, hackathon_id)
    name = (name or "").strip()
    if not name:
        raise ValueError("Teammate name is required.")
    cur = conn.cursor()
    cur.execute(
        """
        IF NOT EXISTS (SELECT 1 FROM teammates WHERE name = %s)
            INSERT INTO teammates (name) VALUES (%s)
        """,
        (name, name),
    )
    cur.execute("SELECT id FROM teammates WHERE name = %s", (name,))
    teammate_id = cur.fetchone()["id"]
    cur.execute(
        """
        IF NOT EXISTS (
            SELECT 1 FROM hackathon_teammates
            WHERE hackathon_id = %s AND teammate_id = %s
        )
            INSERT INTO hackathon_teammates (hackathon_id, teammate_id) VALUES (%s, %s)
        """,
        (hackathon_id, teammate_id, hackathon_id, teammate_id),
    )
    conn.commit()


def add_project(conn, hackathon_id: int, name, result, technologies_text) -> int:
    if _get_status(conn, hackathon_id) != "attended":
        raise ValueError("Projects can only be added to attended hackathons.")
    name = (name or "").strip()
    if not name:
        raise ValueError("Project name is required.")
    if result not in RESULTS:
        raise ValueError("Result must be one of: " + ", ".join(RESULTS) + ".")
    technologies = parse_technologies(technologies_text)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO projects (hackathon_id, name, result)
        OUTPUT INSERTED.id
        VALUES (%s, %s, %s)
        """,
        (hackathon_id, name, result),
    )
    project_id = cur.fetchone()["id"]
    for tech in technologies:
        cur.execute(
            "INSERT INTO project_technologies (project_id, technology) VALUES (%s, %s)",
            (project_id, tech),
        )
    conn.commit()
    return project_id
