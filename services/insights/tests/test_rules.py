import pytest

from rules import (
    attended,
    compute_stats,
    find_record,
    generate_checklist,
    skill_gaps,
    upcoming,
    validate_reflection,
)

RECORDS = [
    {
        "id": 1,
        "status": "attended",
        "mode": "in_person",
        "teammates": ["Ana", "Ben"],
        "projects": [{"result": "winner", "technologies": ["python", "react"]}],
    },
    {
        "id": 2,
        "status": "attended",
        "mode": "online",
        "teammates": ["Ana"],
        "projects": [{"result": "participated", "technologies": ["python"]}],
    },
    {"id": 3, "status": "applied", "mode": "online", "teammates": [], "projects": []},
    {"id": 4, "status": "rejected", "mode": "online", "teammates": [], "projects": []},
]

RULES = [
    {"condition_field": "always", "condition_value": "*", "item": "Laptop"},
    {"condition_field": "mode", "condition_value": "in_person", "item": "Travel documents"},
    {"condition_field": "mode", "condition_value": "online", "item": "Headset"},
    {"condition_field": "always", "condition_value": "*", "item": "Laptop"},
]


def test_filters():
    assert [r["id"] for r in attended(RECORDS)] == [1, 2]
    assert [r["id"] for r in upcoming(RECORDS)] == [3]
    assert find_record(RECORDS, 2)["id"] == 2
    assert find_record(RECORDS, 99) is None


def test_compute_stats():
    stats = compute_stats(RECORDS)
    assert stats["attended"] == 2
    assert stats["projects"] == 2
    assert stats["won"] == 1
    assert stats["win_rate_percent"] == 50
    assert stats["top_technologies"][0] == ("python", 2)
    assert stats["top_teammates"][0] == ("Ana", 2)


def test_compute_stats_with_nothing_attended():
    assert compute_stats([])["win_rate_percent"] == 0


def test_skill_gaps_lists_unused_technologies():
    gaps = skill_gaps(RECORDS)
    assert "python" not in gaps and "react" not in gaps
    assert "docker" in gaps


def test_checklist_matches_mode_without_duplicates():
    assert generate_checklist(RECORDS[0], RULES) == ["Laptop", "Travel documents"]
    assert generate_checklist(RECORDS[1], RULES) == ["Laptop", "Headset"]


def test_validate_reflection():
    cleaned = validate_reflection(RECORDS[0], " Good team ", "", None)
    assert cleaned == {"hackathon_id": 1, "went_well": "Good team", "went_badly": None, "lesson": None}
    with pytest.raises(ValueError, match="attended"):
        validate_reflection(RECORDS[2], "x", "", "")
    with pytest.raises(ValueError, match="attended"):
        validate_reflection(None, "x", "", "")
    with pytest.raises(ValueError, match="at least one"):
        validate_reflection(RECORDS[0], " ", "", None)
