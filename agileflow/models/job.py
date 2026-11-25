from __future__ import annotations

from ..domain.constants import JOB_QUEUED
from ..extensions import db
from .base import utcnow


class BackgroundJob(db.Model):
    """A unit of background work. Doubles as a durable queue (see ``workers/job_queue.py``)."""

    __tablename__ = "background_job"
    __table_args__ = (db.Index("ix_job_status_next_run", "status", "next_run_at"),)

    id = db.Column(db.Integer, primary_key=True)
    job_type = db.Column(db.String(40), nullable=False)
    status = db.Column(db.String(20), nullable=False, default=JOB_QUEUED)
    payload = db.Column(db.JSON, nullable=False, default=dict)
    result = db.Column(db.Text, nullable=False, default="")
    error = db.Column(db.Text, nullable=False, default="")  # last error message
    attempts = db.Column(db.Integer, nullable=False, default=0)
    max_attempts = db.Column(db.Integer, nullable=False, default=3)
    next_run_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    locked_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"), nullable=True, index=True)

    user = db.relationship("User")
