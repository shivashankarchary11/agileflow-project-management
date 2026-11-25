"""Shared extension instances (created here, initialised in ``create_app``)."""

from __future__ import annotations

import sqlite3

from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from sqlalchemy.engine import Engine

db = SQLAlchemy()
# render_as_batch lets Alembic alter SQLite tables (SQLite cannot ALTER most things).
migrate = Migrate(render_as_batch=True)


@event.listens_for(Engine, "connect")
def _configure_sqlite(dbapi_connection, _record):
    """Turn on foreign keys (off by default in SQLite) and friendlier concurrency."""
    if not isinstance(dbapi_connection, sqlite3.Connection):
        return
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=15000")
    # WAL lets the web thread read while the worker thread writes. It is not
    # supported for in-memory databases, so ignore failures there.
    try:
        cursor.execute("PRAGMA journal_mode=WAL")
    except sqlite3.DatabaseError:  # pragma: no cover - defensive
        pass
    cursor.close()
