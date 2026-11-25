"""A small durable job queue stored in the ``background_job`` table.

Life cycle of a job::

    Queued --claim--> Running --ok--> Completed
                         |--error, attempts left--> Queued (next_run_at = now + backoff)
                         |--error, no attempts left--> Failed
    Running (stuck longer than JOB_STALE_SECONDS) --recover--> Queued

Guarantees
* **At-least-once**: a job whose worker died is re-queued, so a handler may run
  twice and must be safe to repeat.
* **No double claiming**: a job is claimed with a single conditional
  ``UPDATE ... WHERE status='Queued'``; only one worker sees ``rowcount == 1``.
* **Bounded retries** with exponential backoff: ``base * 2**attempts`` seconds.

Functions take an optional ``now`` so tests can control time without sleeping.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from flask import current_app
from sqlalchemy import select, update

from ..domain.constants import JOB_COMPLETED, JOB_FAILED, JOB_QUEUED, JOB_RUNNING
from ..extensions import db
from ..models import BackgroundJob, utcnow

logger = logging.getLogger(__name__)
MAX_ERROR_LENGTH = 2000


def enqueue(
    job_type: str,
    payload: dict | None = None,
    *,
    user_id: int | None = None,
    max_attempts: int | None = None,
    run_at: datetime | None = None,
) -> BackgroundJob:
    """Create a Queued job and commit it, so it survives a restart."""
    job = BackgroundJob(
        job_type=job_type,
        payload=payload or {},
        user_id=user_id,
        max_attempts=max_attempts or current_app.config["JOB_MAX_ATTEMPTS"],
        next_run_at=run_at or utcnow(),
    )
    db.session.add(job)
    db.session.commit()
    return job


def claim_next(now: datetime | None = None) -> BackgroundJob | None:
    """Atomically move the oldest due Queued job to Running and return it (or ``None``)."""
    now = now or utcnow()
    for _ in range(5):  # retry if another worker grabs our candidate first
        candidate_id = db.session.execute(
            select(BackgroundJob.id)
            .where(BackgroundJob.status == JOB_QUEUED, BackgroundJob.next_run_at <= now)
            .order_by(BackgroundJob.next_run_at, BackgroundJob.id)
            .limit(1)
        ).scalar_one_or_none()
        if candidate_id is None:
            return None
        claimed = db.session.execute(
            update(BackgroundJob)
            .where(BackgroundJob.id == candidate_id, BackgroundJob.status == JOB_QUEUED)
            .values(status=JOB_RUNNING, locked_at=now, attempts=BackgroundJob.attempts + 1, updated_at=now)
        ).rowcount
        db.session.commit()
        if claimed == 1:
            return db.session.get(BackgroundJob, candidate_id)
    return None


def complete(job: BackgroundJob, result: str = "", now: datetime | None = None) -> None:
    job.status = JOB_COMPLETED
    job.result = result or ""
    job.error = ""
    job.locked_at = None
    job.updated_at = now or utcnow()
    db.session.commit()


def backoff_delay(attempts: int) -> timedelta:
    return timedelta(seconds=current_app.config["JOB_BACKOFF_BASE_SECONDS"] * (2**attempts))


def fail_or_retry(job: BackgroundJob, exc: BaseException, now: datetime | None = None) -> BackgroundJob:
    """Record the error, then either re-queue with backoff or give up (Failed)."""
    now = now or utcnow()
    job.error = f"{type(exc).__name__}: {exc}"[:MAX_ERROR_LENGTH]
    job.locked_at = None
    job.updated_at = now
    if job.attempts >= job.max_attempts:
        job.status = JOB_FAILED
        logger.error("Job %s (%s) failed permanently: %s", job.id, job.job_type, job.error)
    else:
        job.status = JOB_QUEUED
        job.next_run_at = now + backoff_delay(job.attempts)
        logger.warning(
            "Job %s (%s) failed attempt %s/%s, retrying at %s: %s",
            job.id, job.job_type, job.attempts, job.max_attempts, job.next_run_at, job.error,
        )
    db.session.commit()
    return job


def recover_stale(now: datetime | None = None, stale_seconds: int | None = None) -> int:
    """Re-queue jobs stuck in Running (their worker probably died). Returns how many."""
    now = now or utcnow()
    if stale_seconds is None:
        stale_seconds = current_app.config["JOB_STALE_SECONDS"]
    cutoff = now - timedelta(seconds=stale_seconds)
    count = db.session.execute(
        update(BackgroundJob)
        .where(BackgroundJob.status == JOB_RUNNING, BackgroundJob.locked_at < cutoff)
        .values(status=JOB_QUEUED, locked_at=None, next_run_at=now, updated_at=now)
    ).rowcount
    db.session.commit()
    if count:
        logger.warning("Recovered %s stale job(s)", count)
    return count


def reset_for_retry(job: BackgroundJob, now: datetime | None = None) -> BackgroundJob:
    """Manually re-queue a Failed job with a fresh attempt budget."""
    now = now or utcnow()
    job.status = JOB_QUEUED
    job.attempts = 0
    job.error = ""
    job.locked_at = None
    job.next_run_at = now
    job.updated_at = now
    db.session.commit()
    return job


def run_job(job: BackgroundJob) -> None:
    """Execute one claimed job and record success, retry or failure."""
    from .handlers import AFTER_SUCCESS, HANDLERS  # local import avoids a cycle

    job_id = job.id
    try:
        handler = HANDLERS.get(job.job_type)
        if handler is None:
            raise LookupError(f"No handler registered for job type '{job.job_type}'")
        result = handler(job)
        complete(job, result)
    except Exception as exc:  # noqa: BLE001 - any handler error must be recorded, not crash the worker
        db.session.rollback()
        job = db.session.get(BackgroundJob, job_id)
        fail_or_retry(job, exc)
        return
    hook = AFTER_SUCCESS.get(job.job_type)
    if hook:
        try:
            hook(job)
        except Exception:  # noqa: BLE001 - a notification problem must not undo a finished job
            db.session.rollback()
            logger.exception("After-success hook failed for job %s", job_id)


def run_pending(limit: int = 100, now: datetime | None = None) -> int:
    """Run due jobs until none are left (or ``limit`` is reached). Returns how many ran."""
    ran = 0
    while ran < limit:
        job = claim_next(now)
        if job is None:
            break
        run_job(job)
        ran += 1
    return ran
