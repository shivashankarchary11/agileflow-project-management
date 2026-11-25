"""Shared fixtures.

Every test builds its own app with ``create_app("testing")``: an isolated in-memory SQLite
database, no background thread, in-memory email backend. Nothing here can touch ``instance/``.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from agileflow import create_app
from agileflow.extensions import db
from tests import helpers


@pytest.fixture()
def app_factory():
    """Build apps with config overrides, e.g. ``app_factory(CSRF_ENABLED=True)``."""
    created = []

    def build(**overrides):
        application = create_app("testing", **overrides)
        with application.app_context():
            db.create_all()
        created.append(application)
        return application

    yield build
    for application in created:
        with application.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()


@pytest.fixture()
def app(app_factory):
    return app_factory()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def make_actor(app):
    return lambda name, role="Member": helpers.register_actor(app, name, role)


@pytest.fixture()
def world(app):
    """A ready-made team: a lead who owns a project; a member and a viewer inside it; an outsider."""
    lead = helpers.register_actor(app, "Lead User", "Team Lead")
    member = helpers.register_actor(app, "Member User", "Member")
    viewer = helpers.register_actor(app, "Viewer User", "Viewer")
    outsider = helpers.register_actor(app, "Outsider User", "Member")
    project = helpers.create_project(lead, "Demo Project")
    helpers.add_member(lead, project["id"], member, "Member")
    helpers.add_member(lead, project["id"], viewer, "Viewer")
    return SimpleNamespace(lead=lead, member=member, viewer=viewer, outsider=outsider, project=project, pid=project["id"])


@pytest.fixture()
def run_jobs(app):
    """Run every due background job now (the worker thread is off in tests)."""
    from agileflow.workers import job_queue

    def run(limit: int = 100) -> int:
        with app.app_context():
            return job_queue.run_pending(limit)

    return run
