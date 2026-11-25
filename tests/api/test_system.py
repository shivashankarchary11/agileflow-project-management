"""SYS-01 .. SYS-03: isolation, health, Python version, and schema/migration consistency."""

import logging
import sqlite3
import sys
import tomllib
from contextlib import closing
from pathlib import Path

from agileflow import create_app
from agileflow.extensions import db
from tests.helpers import register_actor

ROOT = Path(__file__).resolve().parents[2]


def test_sys_01_test_runs_never_touch_the_dev_database(app):
    dev_db = ROOT / "instance" / "agileflow.db"
    before = dev_db.stat().st_mtime_ns if dev_db.exists() else None
    legacy = ROOT / "instance" / "agile_manager.db"  # the old test-polluted file
    legacy_before = legacy.stat().st_mtime_ns if legacy.exists() else None

    register_actor(app, "Ada Lovelace")
    assert str(app.config["SQLALCHEMY_DATABASE_URI"]) == "sqlite://"  # in-memory
    with app.app_context():
        assert db.engine.url.database in (None, "", ":memory:")

    assert (dev_db.stat().st_mtime_ns if dev_db.exists() else None) == before
    assert (legacy.stat().st_mtime_ns if legacy.exists() else None) == legacy_before


def test_each_app_gets_its_own_empty_database(app_factory):
    first, second = app_factory(), app_factory()
    register_actor(first, "Ada Lovelace")
    # "Ada" exists in the first app only
    second_client = second.test_client()
    login = second_client.post("/auth/login", json={"email": "ada.lovelace@example.com", "password": "password-123"})
    assert login.status_code == 401


def test_sys_02_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200 and response.get_json() == {"status": "ok"}


def test_sys_03_python_314_is_enforced_everywhere():
    assert sys.version_info[:2] == (3, 14), f"tests must run on Python 3.14, not {sys.version}"
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert project["requires-python"] == ">=3.14,<3.15"
    assert (ROOT / ".python-version").read_text().strip().startswith("3.14")
    dockerfile = (ROOT / "Dockerfile").read_text()
    assert "python:3.14" in dockerfile
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
    assert "3.14" in workflow


def test_foreign_keys_are_enforced_by_sqlite(app):
    with app.app_context():
        assert db.session.execute(db.text("PRAGMA foreign_keys")).scalar() == 1


def test_migrations_build_exactly_the_model_schema(tmp_path, monkeypatch):
    """`flask db upgrade` on an empty file must produce no drift versus the models."""
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext
    from flask_migrate import upgrade

    db_file = tmp_path / "migrated.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file.as_posix()}")
    monkeypatch.setenv("WORKER_ENABLED", "0")
    app = create_app("development")
    try:
        with app.app_context():
            upgrade(directory=str(ROOT / "migrations"))
            with db.engine.connect() as connection:
                diff = compare_metadata(MigrationContext.configure(connection), db.metadata)
        assert diff == [], f"models and migrations disagree: {diff}"
        # Regression: running migrations in-process once silently disabled all existing loggers
        # (worker retry logs, console emails) because Alembic's fileConfig defaults to disabling them.
        assert not logging.getLogger("agileflow.workers.job_queue").disabled
        with closing(sqlite3.connect(db_file)) as raw:  # sqlite3's own `with` does not close the connection
            tables = {row[0] for row in raw.execute("select name from sqlite_master where type='table'")}
        assert {"user", "project", "project_member", "user_story", "task", "background_job"} <= tables
    finally:
        with app.app_context():
            db.session.remove()
            db.engine.dispose()
