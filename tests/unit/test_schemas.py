"""Input validators: clean values in, ValidationError for everything else."""

from datetime import date

import pytest

from agileflow.api import schemas
from agileflow.domain.errors import ValidationError


def test_text_strips_and_checks_type_and_length():
    assert schemas.text({"a": "  hi  "}, "a", max_len=5) == "hi"
    assert schemas.text({}, "a", max_len=5) is None
    assert schemas.text({"a": None}, "a", max_len=5) == ""
    for bad in (5, ["x"], {"x": 1}, True):
        with pytest.raises(ValidationError):
            schemas.text({"a": bad}, "a", max_len=5)
    with pytest.raises(ValidationError):
        schemas.text({"a": "123456"}, "a", max_len=5)  # rejected, not cut
    with pytest.raises(ValidationError):
        schemas.text({"a": "  "}, "a", max_len=5, required=True)
    with pytest.raises(ValidationError):
        schemas.text({}, "a", max_len=5, required=True)


def test_choice():
    assert schemas.choice({"s": "Done"}, "s", ("To Do", "Done")) == "Done"
    assert schemas.choice({}, "s", ("Done",)) is None
    for bad in ("done", "", None, 3, ["Done"]):
        with pytest.raises(ValidationError):
            schemas.choice({"s": bad}, "s", ("Done",))


@pytest.mark.parametrize("value", ["2030-01-31", "2024-02-29"])
def test_iso_date_accepts_real_dates(value):
    assert schemas.iso_date({"d": value}, "d") == (True, date.fromisoformat(value))


@pytest.mark.parametrize("value", ["2030-1-5", "20300131", "2030-02-30", "2023-02-29", "31-01-2030", "2030-01-31T00:00", "2030-W05-1", " 2030-01-31", 20300131, True])
def test_iso_date_rejects_everything_else(value):
    with pytest.raises(ValidationError):
        schemas.iso_date({"d": value}, "d")


def test_iso_date_clearing_and_absent():
    assert schemas.iso_date({"d": None}, "d") == (True, None)
    assert schemas.iso_date({"d": ""}, "d") == (True, None)
    assert schemas.iso_date({}, "d") == (False, None)


def test_integer():
    assert schemas.integer("5", "n") == 5
    assert schemas.integer(5, "n", minimum=1) == 5
    assert schemas.integer(None, "n", allow_none=True) is None
    assert schemas.integer("", "n", allow_none=True) is None
    for bad in ("x", 1.5, True, [], {}, None, 0):
        with pytest.raises(ValidationError):
            schemas.integer(bad, "n", minimum=1)


def test_parse_project_full_and_partial():
    full = schemas.parse_project({"name": " Apollo ", "status": "On Hold", "deadline": "2030-01-01"})
    assert full == {"name": "Apollo", "status": "On Hold", "deadline": date(2030, 1, 1)}
    assert schemas.parse_project({"status": "Completed"}, partial=True) == {"status": "Completed"}
    assert schemas.parse_project({"deadline": None}, partial=True) == {"deadline": None}
    for bad in ({}, {"name": ""}, "string", ["x"], None):
        with pytest.raises(ValidationError):
            schemas.parse_project(bad)
    with pytest.raises(ValidationError):
        schemas.parse_project({"name": ""}, partial=True)


def test_parse_task_assignee():
    assert schemas.parse_task({"title": "t", "assigned_to_id": "7"})["assigned_to_id"] == 7
    assert schemas.parse_task({"title": "t", "assigned_to_id": None})["assigned_to_id"] is None
    assert "assigned_to_id" not in schemas.parse_task({"title": "t"})
    with pytest.raises(ValidationError):
        schemas.parse_task({"title": "t", "assigned_to_id": 0})


def test_parse_move_payloads():
    assert schemas.parse_task_move({"story_id": 3, "status": "Done", "position": "2"}) == {"story_id": 3, "status": "Done", "position": 2}
    assert schemas.parse_task_move({}) == {}  # the service decides that "nothing" is an error
    assert schemas.parse_story_move({"position": 0}) == {"position": 0}
    with pytest.raises(ValidationError):
        schemas.parse_story_move({})


def test_parse_register_and_login():
    ok = schemas.parse_register({"name": "Ada", "email": " Ada@Example.COM ", "password": "12345678"})
    assert ok["email"] == "ada@example.com" and ok["requested_role"] is None
    for bad in ({"name": "A", "email": "a@b", "password": "12345678"}, {"name": "A", "email": "a@b.co", "password": "1234567"}, {"name": "A", "email": "a@b.co", "password": "x" * 129}):
        with pytest.raises(ValidationError):
            schemas.parse_register(bad)
    assert schemas.parse_login({"email": " A@B.CO ", "password": "pw"}) == {"email": "a@b.co", "password": "pw"}
    for bad in ({"email": "a@b.co"}, {"password": "x"}, {"email": 1, "password": "x"}, {"email": "", "password": "x"}):
        with pytest.raises(ValidationError):
            schemas.parse_login(bad)


def test_parse_paging_defaults_and_caps():
    assert schemas.parse_paging({}) == (50, 0)
    assert schemas.parse_paging({"limit": "500", "offset": "10"}) == (200, 10)
    for bad in ({"limit": "0"}, {"limit": "-1"}, {"offset": "-1"}, {"limit": "x"}):
        with pytest.raises(ValidationError):
            schemas.parse_paging(bad)


def test_parse_filters():
    assert schemas.parse_story_filters({"status": "Done", "q": " hi ", "assignee_id": "3"}) == {
        "status": "Done", "priority": None, "assignee_id": 3, "q": "hi",
    }
    assert schemas.parse_story_filters({}) == {"status": None, "priority": None, "assignee_id": None, "q": None}
    with pytest.raises(ValidationError):
        schemas.parse_story_filters({"priority": "Urgent"})
    with pytest.raises(ValidationError):
        schemas.parse_board_filters({"story_id": "x"})
