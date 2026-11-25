from __future__ import annotations

from flask import current_app

from ...models import BackgroundJob
from ...services import notification_service, report_service


def handle(job: BackgroundJob) -> str:
    """Build the progress report for the user who requested it."""
    # Test-only hook: fail the first N attempts on purpose so retries can be tested.
    if current_app.config.get("JOB_FAIL_HOOK"):
        fail_n_times = int((job.payload or {}).get("fail_n_times", 0))
        if job.attempts <= fail_n_times:
            raise RuntimeError(f"Injected failure on attempt {job.attempts} (will fail {fail_n_times} time(s))")
    return report_service.build_report_text(job.user_id)


def after_success(job: BackgroundJob) -> None:
    notification_service.notify_report_ready(job)
