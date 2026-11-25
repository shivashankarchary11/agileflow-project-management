from __future__ import annotations

from flask import current_app

from ...models import BackgroundJob
from ..email_backends import EmailMessage


def handle(job: BackgroundJob) -> str:
    """Send one email described by the job payload. Any exception triggers a retry."""
    payload = job.payload or {}
    message = EmailMessage(to=payload["to"], subject=payload["subject"], body=payload["body"])
    current_app.extensions["mail_backend"].send(message)
    return f"Sent to {message.to}"
