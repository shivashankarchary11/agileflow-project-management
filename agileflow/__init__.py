"""AgileFlow: a small-team Agile project tracker (Project -> User Story -> Task)."""

from __future__ import annotations

import logging
import os

from flask import Flask

from .config import load_config
from .extensions import db, migrate

__all__ = ["create_app"]


def create_app(config_name: str | None = None, **overrides) -> Flask:
    """Application factory: builds a fully configured app.

    ``config_name`` is development, testing or production (default: the ``APP_ENV``
    environment variable, else development). Keyword ``overrides`` replace config values,
    which is how tests tweak individual settings.
    """
    name = config_name or os.environ.get("APP_ENV", "development")
    app = Flask(
        __name__,
        instance_relative_config=True,
        template_folder="web/templates",
        static_folder="web/static",
        static_url_path="/static",
    )
    app.config.update(load_config(name))
    app.config.update(overrides)
    app.json.sort_keys = False  # keep our key order (e.g. board columns: To Do, In Progress, Done)
    os.makedirs(app.instance_path, exist_ok=True)

    # Flask attaches a stderr handler to the "agileflow" logger; we only have to let INFO through
    # (otherwise INFO records, such as console emails and worker start-up, fall back to WARNING).
    logging.getLogger(__name__).setLevel(app.config["LOG_LEVEL"].upper())

    db.init_app(app)
    migrate.init_app(app, db)

    from . import models  # noqa: F401  (registers tables with SQLAlchemy)
    from .api import register_api
    from .security import init_security
    from .web import bp as web_bp
    from .workers.email_backends import build_backend
    from .workers.worker import Worker

    init_security(app)
    register_api(app)
    app.register_blueprint(web_bp)
    app.extensions["mail_backend"] = build_backend(app.config)

    worker = Worker(app)
    app.extensions["worker"] = worker
    # Start the background worker once. With the Flask reloader there are two processes;
    # only the child (WERKZEUG_RUN_MAIN=true) should run it.
    reloader_parent = app.debug and os.environ.get("WERKZEUG_RUN_MAIN") != "true"
    if app.config["WORKER_ENABLED"] and not reloader_parent:
        worker.start()

    return app
