"""Progress reports (an asynchronous job) and job status/retry for the requesting user."""

from __future__ import annotations

from datetime import UTC, datetime

from flask import current_app
from sqlalchemy import select

from ..domain.constants import JOB_FAILED, JOB_PROGRESS_REPORT
from ..domain.errors import Conflict, NotFound
from ..extensions import db
from ..models import BackgroundJob, User
from ..repositories import project_repo
from ..workers import job_queue
from . import serializers


def request_report(user: User, fail_n_times: int = 0) -> dict:
    """Queue a report; the worker builds it in the background."""
    payload: dict = {}
    if fail_n_times and current_app.config.get("JOB_FAIL_HOOK"):
        payload["fail_n_times"] = fail_n_times
    job = job_queue.enqueue(JOB_PROGRESS_REPORT, payload, user_id=user.id)
    return serializers.job_dict(job)


def _own_job(user: User, job_id: int) -> BackgroundJob:
    job = db.session.get(BackgroundJob, job_id)
    if job is None or job.user_id != user.id:
        raise NotFound("Job not found.")
    return job


def get_job(user: User, job_id: int) -> dict:
    return serializers.job_dict(_own_job(user, job_id), include_result=True)


def list_jobs(user: User, limit: int = 20) -> list[dict]:
    jobs = db.session.execute(
        select(BackgroundJob).where(BackgroundJob.user_id == user.id).order_by(BackgroundJob.id.desc()).limit(limit)
    ).scalars()
    return [serializers.job_dict(j) for j in jobs]


def retry_job(user: User, job_id: int) -> dict:
    job = _own_job(user, job_id)
    if job.status != JOB_FAILED:
        raise Conflict("Only failed jobs can be retried.")
    return serializers.job_dict(job_queue.reset_for_retry(job))


def build_report_text(user_id: int | None) -> str:
    """Plain-text progress report covering only the projects ``user_id`` may see."""
    ids = project_repo.accessible_ids(user_id) if user_id else []
    today = datetime.now(UTC).date()
    projects = [project_repo.get(pid) for pid in sorted(ids)]
    stats = project_repo.stats(ids)
    breakdown = project_repo.task_status_counts(ids, today)

    total_tasks = sum(s["task_count"] for s in stats.values())
    done_tasks = sum(s["done_count"] for s in stats.values())
    pct = (done_tasks / total_tasks * 100) if total_tasks else 0.0

    lines = [
        "AGILE TEAM PROGRESS REPORT",
        f"Generated: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S')} UTC",
        "",
        f"Projects: {len(projects)}",
        f"User stories: {sum(s['story_count'] for s in stats.values())}",
        f"Tasks: {total_tasks}  (done: {done_tasks})",
        f"Overall completion: {pct:.1f}%",
        "",
    ]
    for project in projects:
        s, b = stats[project.id], breakdown[project.id]
        project_pct = (s["done_count"] / s["task_count"] * 100) if s["task_count"] else 0.0
        lines += [
            f"- {project.name} [{project.status}]",
            f"    stories: {s['story_count']}, tasks: {s['task_count']}, completion: {project_pct:.1f}%",
            f"    To Do: {b['To Do']}, In Progress: {b['In Progress']}, Done: {b['Done']}, Overdue: {b['overdue']}",
        ]
    return "\n".join(lines)
