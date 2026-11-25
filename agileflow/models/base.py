from __future__ import annotations

from datetime import UTC, datetime


def utcnow() -> datetime:
    """Current UTC time as a *naive* datetime.

    SQLite has no timezone support, so every timestamp in the database is UTC
    and naive. ``datetime.utcnow()`` is deprecated, hence this helper.
    """
    return datetime.now(UTC).replace(tzinfo=None)
