"""Background worker thread that keeps draining the job queue while the app runs."""

from __future__ import annotations

import logging
import threading

from flask import Flask
from sqlalchemy.exc import OperationalError

from ..extensions import db
from . import job_queue

logger = logging.getLogger(__name__)


class Worker:
    def __init__(self, app: Flask):
        self.app = app
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="agileflow-worker", daemon=True)
        self._thread.start()
        logger.info("Background worker started")

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout)

    def _loop(self) -> None:
        poll = self.app.config["WORKER_POLL_SECONDS"]
        # `python wsgi.py` creates the app (and this thread) and only then runs the migrations,
        # so give the database a moment before the first pass.
        self._stop.wait(poll)
        while not self._stop.is_set():
            ran = 0
            try:
                with self.app.app_context():
                    job_queue.recover_stale()
                    ran = job_queue.run_pending(limit=20)
                    db.session.remove()
            except OperationalError as exc:
                db.session.remove()
                logger.warning("Worker is waiting for the database (has `flask db upgrade` run?): %s", exc.orig)
            except Exception:  # noqa: BLE001 - the loop must survive any error
                logger.exception("Worker iteration failed")
            if ran == 0:
                self._stop.wait(poll)
