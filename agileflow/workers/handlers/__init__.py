"""Registry mapping a job type to the function that performs it."""

from __future__ import annotations

from ...domain.constants import JOB_PROGRESS_REPORT, JOB_SEND_EMAIL
from . import progress_report, send_email

# handler(job) -> result text. Raising an exception means "this attempt failed".
HANDLERS = {
    JOB_PROGRESS_REPORT: progress_report.handle,
    JOB_SEND_EMAIL: send_email.handle,
}

# Optional hook run once, after a job has been marked Completed.
AFTER_SUCCESS = {
    JOB_PROGRESS_REPORT: progress_report.after_success,
}
