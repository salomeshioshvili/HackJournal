from datetime import date

STATUSES = ("interested", "applied", "accepted", "attended", "rejected", "skipped")
MODES = ("in_person", "online", "hybrid")
RESULTS = ("participated", "finalist", "winner")

ALLOWED_TRANSITIONS = {
    "interested": {"applied", "skipped"},
    "applied": {"accepted", "rejected", "skipped"},
    "accepted": {"attended", "skipped"},
    "attended": set(),
    "rejected": set(),
    "skipped": set(),
}


def can_transition(current: str, new: str) -> bool:
    return new in ALLOWED_TRANSITIONS.get(current, set())


def urgency(deadline, today: date) -> str:
    if not deadline:
        return "no_deadline"
    days_left = (date.fromisoformat(str(deadline)[:10]) - today).days
    if days_left < 0:
        return "overdue"
    if days_left <= 3:
        return "urgent"
    if days_left <= 14:
        return "soon"
    return "later"


def country_from_location(location):
    if not location or "," not in location:
        return None
    return location.rsplit(",", 1)[1].strip() or None


def parse_technologies(text) -> list:
    names = {part.strip().lower() for part in (text or "").split(",")}
    names.discard("")
    return sorted(names)


def _parse_date(value, label: str, required: bool):
    value = (value or "").strip()
    if not value:
        if required:
            raise ValueError(f"{label} is required.")
        return None
    try:
        date.fromisoformat(value)
    except ValueError:
        raise ValueError(f"{label} must look like 2026-10-30.") from None
    return value


def validate_hackathon(data) -> dict:
    name = (data.get("name") or "").strip()
    if not name:
        raise ValueError("Name is required.")
    mode = data.get("mode")
    if mode not in MODES:
        raise ValueError("Mode must be one of: " + ", ".join(MODES) + ".")
    start = _parse_date(data.get("start_date"), "Start date", required=True)
    end = _parse_date(data.get("end_date"), "End date", required=True)
    if end < start:
        raise ValueError("End date cannot be before start date.")
    deadline = _parse_date(data.get("application_deadline"), "Application deadline", required=False)
    location = (data.get("location") or "").strip() or None
    return {
        "name": name,
        "location": location,
        "country": country_from_location(location),
        "mode": mode,
        "start_date": start,
        "end_date": end,
        "application_deadline": deadline,
        "travel_funded": 1 if data.get("travel_funded") in (True, "true", "1", "on", 1) else 0,
        "notes": (data.get("notes") or "").strip() or None,
    }
