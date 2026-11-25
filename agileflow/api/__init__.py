"""HTTP layer: thin blueprints that parse input, call a service and return JSON."""

from __future__ import annotations

from flask import Blueprint, Flask, jsonify

from . import auth, jobs, projects, stories, tasks
from .errors import register_error_handlers

health_bp = Blueprint("health", __name__)


@health_bp.get("/api/health")
def health():
    return jsonify({"status": "ok"})


def register_api(app: Flask) -> None:
    for blueprint in (health_bp, auth.bp, projects.bp, stories.bp, tasks.bp, jobs.bp):
        app.register_blueprint(blueprint)
    register_error_handlers(app)
