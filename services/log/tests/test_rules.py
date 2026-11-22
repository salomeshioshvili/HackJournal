from datetime import date

import pytest

from rules import can_transition, country_from_location, parse_technologies, urgency, validate_hackathon

TODAY = date(2026, 11, 22)


def test_allowed_and_blocked_transitions():
    assert can_transition("interested", "applied")
    assert can_transition("applied", "accepted")
    assert can_transition("accepted", "attended")
    assert not can_transition("interested", "attended")
    assert not can_transition("attended", "skipped")
    assert not can_transition("unknown", "applied")


@pytest.mark.parametrize(
    "deadline, expected",
    [
        (None, "no_deadline"),
        ("2026-11-21", "overdue"),
        ("2026-11-25", "urgent"),
        ("2026-12-06", "soon"),
        ("2027-01-30", "later"),
    ],
)
def test_urgency(deadline, expected):
    assert urgency(deadline, TODAY) == expected


def test_parse_technologies_cleans_and_dedupes():
    assert parse_technologies(" Python, react,python ,, ") == ["python", "react"]
    assert parse_technologies(None) == []


@pytest.mark.parametrize(
    "location, expected",
    [
        ("Gdańsk, Poland", "Poland"),
        ("Lausanne, Vaud, Switzerland", "Switzerland"),
        ("Online", None),
        ("Paris,", None),
        (None, None),
    ],
)
def test_country_from_location(location, expected):
    assert country_from_location(location) == expected


def test_validate_hackathon_ok():
    h = validate_hackathon(
        {
            "name": " Junction ",
            "mode": "in_person",
            "start_date": "2026-11-01",
            "end_date": "2026-11-03",
            "travel_funded": "on",
        }
    )
    assert h["name"] == "Junction"
    assert h["travel_funded"] == 1
    assert h["application_deadline"] is None
    assert h["location"] is None


@pytest.mark.parametrize(
    "data, message",
    [
        ({"mode": "online", "start_date": "2026-11-01", "end_date": "2026-11-01"}, "Name"),
        ({"name": "A", "mode": "boat", "start_date": "2026-11-01", "end_date": "2026-11-01"}, "Mode"),
        ({"name": "A", "mode": "online", "end_date": "2026-11-01"}, "Start date"),
        ({"name": "A", "mode": "online", "start_date": "01/11/2026", "end_date": "2026-11-01"}, "Start date"),
        ({"name": "A", "mode": "online", "start_date": "2026-11-05", "end_date": "2026-11-01"}, "End date"),
    ],
)
def test_validate_hackathon_errors(data, message):
    with pytest.raises(ValueError, match=message):
        validate_hackathon(data)
