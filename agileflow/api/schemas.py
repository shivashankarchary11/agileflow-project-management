"""Input validation. Every function returns a *clean* dict or raises ``ValidationError`` (HTTP 400).

Rules: values must have the right type (never a 500 on bad JSON), text is stripped and
length-checked (rejected, not silently cut), enums are checked, dates are strict ``YYYY-MM-DD``.
PATCH-style ("partial") parsing only validates the keys that were actually sent.
"""

from __future__ import annotations

import re
from datetime import date

from ..domain import constants as c
from ..domain.errors import ValidationError

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MAX_LIMIT = 200
DEFAULT_LIMIT = 50


# ---------- primitives ----------

def require_object(data) -> dict:
    if not isinstance(data, dict):
        raise ValidationError("Request body must be a JSON object.")
    return data


def text(data: dict, key: str, *, max_len: int, required: bool = False) -> str | None:
    """Return the cleaned string for ``key`` (``None`` if the key is absent and not required)."""
    if key not in data:
        if required:
            raise ValidationError(f"'{key}' is required.")
        return None
    value = data[key]
    if value is None and not required:
        value = ""
    if not isinstance(value, str):
        raise ValidationError(f"'{key}' must be text.")
    value = value.strip()
    if required and not value:
        raise ValidationError(f"'{key}' cannot be empty.")
    if len(value) > max_len:
        raise ValidationError(f"'{key}' must be at most {max_len} characters.")
    return value


def choice(data: dict, key: str, allowed: tuple[str, ...]) -> str | None:
    if key not in data:
        return None
    value = data[key]
    if not isinstance(value, str) or value not in allowed:
        raise ValidationError(f"'{key}' must be one of: {', '.join(allowed)}.")
    return value


def iso_date(data: dict, key: str) -> tuple[bool, date | None]:
    """Return ``(present, value)``. ``null`` or ``""`` means "clear the date"."""
    if key not in data:
        return False, None
    value = data[key]
    if value in (None, ""):
        return True, None
    if not isinstance(value, str) or not _DATE_RE.match(value):
        raise ValidationError(f"'{key}' must be a date in YYYY-MM-DD format.")
    try:
        return True, date.fromisoformat(value)
    except ValueError:
        raise ValidationError(f"'{key}' is not a real calendar date.") from None


def integer(value, name: str, *, allow_none: bool = False, minimum: int | None = None) -> int | None:
    if value in (None, "") and allow_none:
        return None
    if isinstance(value, bool) or not isinstance(value, int | str):
        raise ValidationError(f"'{name}' must be a whole number.")
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ValidationError(f"'{name}' must be a whole number.") from None
    if minimum is not None and number < minimum:
        raise ValidationError(f"'{name}' must be at least {minimum}.")
    return number


def _put(out: dict, key: str, value) -> None:
    if value is not None:
        out[key] = value


# ---------- auth ----------

def _email(data: dict) -> str:
    email = text(data, "email", max_len=c.MAX_EMAIL, required=True).lower()
    if not _EMAIL_RE.match(email):
        raise ValidationError("Enter a valid email address.")
    return email


def _password(data: dict) -> str:
    password = data.get("password")
    if not isinstance(password, str) or not (c.MIN_PASSWORD <= len(password) <= c.MAX_PASSWORD):
        raise ValidationError(f"Password must be {c.MIN_PASSWORD}-{c.MAX_PASSWORD} characters.")
    return password


def parse_register(data) -> dict:
    data = require_object(data)
    role = data.get("role")
    if role is not None and not isinstance(role, str):
        raise ValidationError("'role' must be text.")
    return {
        "name": text(data, "name", max_len=c.MAX_NAME, required=True),
        "email": _email(data),
        "password": _password(data),
        "requested_role": role,
    }


def parse_login(data) -> dict:
    data = require_object(data)
    email = data.get("email")
    password = data.get("password")
    if not isinstance(email, str) or not isinstance(password, str) or not email.strip() or not password:
        raise ValidationError("Enter your email and password.")
    return {"email": email.strip().lower(), "password": password}


# ---------- projects ----------

def parse_project(data, *, partial: bool = False) -> dict:
    data = require_object(data)
    out: dict = {}
    _put(out, "name", text(data, "name", max_len=c.MAX_PROJECT_NAME, required=not partial))
    if partial and "name" in data and not out.get("name"):
        raise ValidationError("'name' cannot be empty.")
    _put(out, "description", text(data, "description", max_len=c.MAX_DESCRIPTION))
    _put(out, "status", choice(data, "status", c.PROJECT_STATUSES))
    present, deadline = iso_date(data, "deadline")
    if present:
        out["deadline"] = deadline
    return out


def parse_member(data) -> dict:
    data = require_object(data)
    role = data.get("role", c.MEMBER)
    if role not in c.PROJECT_MEMBER_ROLES:
        raise ValidationError("Choose Member or Viewer.")
    return {"email": _email(data), "role": role}


# ---------- stories ----------

def parse_story(data, *, partial: bool = False) -> dict:
    data = require_object(data)
    out: dict = {}
    _put(out, "title", text(data, "title", max_len=c.MAX_TITLE, required=not partial))
    if partial and "title" in data and not out.get("title"):
        raise ValidationError("'title' cannot be empty.")
    _put(out, "description", text(data, "description", max_len=c.MAX_DESCRIPTION))
    _put(out, "priority", choice(data, "priority", c.PRIORITIES))
    _put(out, "status", choice(data, "status", c.WORK_STATUSES))
    return out


def parse_story_move(data) -> dict:
    data = require_object(data)
    if "position" not in data:
        raise ValidationError("'position' is required.")
    return {"position": integer(data["position"], "position", minimum=0)}


# ---------- tasks ----------

def parse_task(data, *, partial: bool = False) -> dict:
    data = require_object(data)
    out: dict = {}
    _put(out, "title", text(data, "title", max_len=c.MAX_TITLE, required=not partial))
    if partial and "title" in data and not out.get("title"):
        raise ValidationError("'title' cannot be empty.")
    _put(out, "description", text(data, "description", max_len=c.MAX_DESCRIPTION))
    _put(out, "status", choice(data, "status", c.WORK_STATUSES))
    present, due = iso_date(data, "due_date")
    if present:
        out["due_date"] = due
    if "assigned_to_id" in data:
        out["assigned_to_id"] = integer(data["assigned_to_id"], "assigned_to_id", allow_none=True, minimum=1)
    return out


def parse_task_move(data) -> dict:
    data = require_object(data)
    out: dict = {}
    if "story_id" in data:
        out["story_id"] = integer(data["story_id"], "story_id", minimum=1)
    _put(out, "status", choice(data, "status", c.WORK_STATUSES))
    if "position" in data:
        out["position"] = integer(data["position"], "position", minimum=0)
    return out


# ---------- query strings ----------

def parse_paging(args) -> tuple[int, int]:
    limit = integer(args.get("limit", DEFAULT_LIMIT), "limit", minimum=1)
    offset = integer(args.get("offset", 0), "offset", minimum=0)
    return min(limit, MAX_LIMIT), offset


def _query_text(args, key: str) -> str | None:
    value = (args.get(key) or "").strip()
    if len(value) > 100:
        raise ValidationError(f"'{key}' must be at most 100 characters.")
    return value or None


def _query_choice(args, key: str, allowed: tuple[str, ...]) -> str | None:
    value = args.get(key)
    if not value:
        return None
    if value not in allowed:
        raise ValidationError(f"'{key}' must be one of: {', '.join(allowed)}.")
    return value


def parse_story_filters(args) -> dict:
    return {
        "status": _query_choice(args, "status", c.WORK_STATUSES),
        "priority": _query_choice(args, "priority", c.PRIORITIES),
        "assignee_id": integer(args.get("assignee_id"), "assignee_id", allow_none=True, minimum=1),
        "q": _query_text(args, "q"),
    }


def parse_board_filters(args) -> dict:
    return {
        "priority": _query_choice(args, "priority", c.PRIORITIES),
        "assignee_id": integer(args.get("assignee_id"), "assignee_id", allow_none=True, minimum=1),
        "story_id": integer(args.get("story_id"), "story_id", allow_none=True, minimum=1),
        "q": _query_text(args, "q"),
    }


def parse_project_search(args) -> str | None:
    return _query_text(args, "q")
