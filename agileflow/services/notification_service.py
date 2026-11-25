"""Decides *when* to email people and queues the email as a background job.

Emails are never sent inside the web request: we only enqueue a ``send_email``
job (after the main change is committed). The worker delivers it, retrying with
backoff if the mail server is down.
"""

from __future__ import annotations

from ..domain.constants import JOB_SEND_EMAIL
from ..models import BackgroundJob, Project, Task, User
from ..repositories import user_repo
from ..workers import job_queue


def _queue_email(to: User, subject: str, body: str, *, owner_id: int | None) -> BackgroundJob:
    return job_queue.enqueue(
        JOB_SEND_EMAIL,
        {"to": to.email, "subject": subject, "body": body},
        # The person who triggered it can see delivery status in their jobs list.
        user_id=owner_id if owner_id is not None else to.id,
    )


def notify_task_assigned(task: Task, assignee: User, actor: User) -> None:
    if assignee.id == actor.id:
        return  # no need to email yourself
    story = task.story
    due = task.due_date.isoformat() if task.due_date else "no due date"
    body = (
        f"Hi {assignee.name},\n\n"
        f"{actor.name} assigned you a task in project \"{story.project.name}\":\n\n"
        f"  Task:  {task.title}\n  Story: {story.title}\n  Due:   {due}\n\n"
        "Open AgileFlow to see the details."
    )
    _queue_email(assignee, f"[AgileFlow] New task: {task.title}", body, owner_id=actor.id)


def notify_member_added(project: Project, member: User, role: str, actor: User) -> None:
    body = (
        f"Hi {member.name},\n\n"
        f"{actor.name} added you to the project \"{project.name}\" as a {role}.\n\n"
        "Open AgileFlow to get started."
    )
    _queue_email(member, f"[AgileFlow] You were added to {project.name}", body, owner_id=actor.id)


def notify_report_ready(job: BackgroundJob) -> None:
    user = user_repo.get(job.user_id)
    if user is None:
        return
    body = f"Hi {user.name},\n\nYour progress report (job #{job.id}) is ready. Open AgileFlow, go to Reports & jobs, and download it."
    _queue_email(user, "[AgileFlow] Your progress report is ready", body, owner_id=user.id)
