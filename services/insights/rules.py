from collections import Counter

KNOWN_TECHNOLOGIES = (
    "python", "javascript", "typescript", "react", "node",
    "sql", "docker", "flask", "fastapi", "swift",
)
UPCOMING_STATUSES = ("interested", "applied", "accepted")


def attended(records) -> list:
    return [r for r in records if r.get("status") == "attended"]


def upcoming(records) -> list:
    return [r for r in records if r.get("status") in UPCOMING_STATUSES]


def find_record(records, hackathon_id):
    for record in records:
        if record.get("id") == hackathon_id:
            return record
    return None


def _ranked(counter: Counter, limit: int) -> list:
    return sorted(counter.items(), key=lambda pair: (-pair[1], pair[0]))[:limit]


def compute_stats(records, limit: int = 5) -> dict:
    done = attended(records)
    technologies = Counter()
    teammates = Counter()
    project_count = 0
    won = 0
    for record in done:
        teammates.update(record.get("teammates") or [])
        for project in record.get("projects") or []:
            project_count += 1
            technologies.update(project.get("technologies") or [])
        if any(project.get("result") == "winner" for project in record.get("projects") or []):
            won += 1
    win_rate_percent = round(100 * won / len(done)) if done else 0
    return {
        "attended": len(done),
        "projects": project_count,
        "won": won,
        "win_rate_percent": win_rate_percent,
        "top_technologies": _ranked(technologies, limit),
        "top_teammates": _ranked(teammates, limit),
    }


def skill_gaps(records, known=KNOWN_TECHNOLOGIES) -> list:
    used = {
        t
        for r in records
        for p in (r.get("projects") or [])
        for t in (p.get("technologies") or [])
    }
    return [technology for technology in known if technology not in used]


def generate_checklist(record, rules) -> list:
    items = []
    for rule in rules:
        field, value = rule["condition_field"], rule["condition_value"]
        applies = field == "always" or str(record.get(field)) == value
        if applies and rule["item"] not in items:
            items.append(rule["item"])
    return items


def validate_reflection(record, went_well, went_badly, lesson) -> dict:
    if record is None or record.get("status") != "attended":
        raise ValueError("Choose an attended hackathon.")
    texts = {
        "went_well": (went_well or "").strip() or None,
        "went_badly": (went_badly or "").strip() or None,
        "lesson": (lesson or "").strip() or None,
    }
    if not any(texts.values()):
        raise ValueError("Write at least one of: what went well, what went badly, or a lesson.")
    return {"hackathon_id": record["id"], **texts}
