"""Turn model objects into JSON-ready dicts (one place, so every endpoint agrees on the shape)."""

from __future__ import annotations

from datetime import date, datetime

from ..domain import policy
from ..domain.constants import TEAM_LEAD
from ..models import BackgroundJob, Project, Task, User, UserStory


def iso_date(value: date | None) -> str | None:
    return value.isoformat() if value else None


def iso_datetime(value: datetime | None) -> str | None:
    return value.isoformat() + "Z" if value else None  # stored as naive UTC


def user_brief(user: User, role: str | None = None) -> dict:
    return {"id": user.id, "name": user.name, "email": user.email, "role": role or user.role}


def task_dict(task: Task) -> dict:
    story = task.story
    return {
        "id": task.id,
        "story_id": task.story_id,
        "project_id": story.project_id,
        "story_title": story.title,
        "story_priority": story.priority,
        "title": task.title,
        "description": task.description,
        "status": task.status,
        "due_date": iso_date(task.due_date),
        "position": task.position,
        "assigned_to_id": task.assigned_to_id,
        "assigned_to": task.assignee.name if task.assignee else "",
        "created_at": iso_datetime(task.created_at),
    }


def story_dict(story: UserStory, *, with_tasks: bool = True) -> dict:
    data = {
        "id": story.id,
        "project_id": story.project_id,
        "title": story.title,
        "description": story.description,
        "priority": story.priority,
        "status": story.status,
        "position": story.position,
        "created_at": iso_datetime(story.created_at),
    }
    if with_tasks:
        data["tasks"] = [task_dict(t) for t in story.tasks]
    return data


def _members(project: Project) -> list[dict]:
    people = [user_brief(project.owner, TEAM_LEAD)]
    people += [user_brief(m.user, m.role) for m in project.members]
    return people


def project_detail(project: Project, role: str) -> dict:
    stories = [story_dict(s) for s in project.stories]
    tasks = [t for s in stories for t in s["tasks"]]
    done = sum(1 for t in tasks if t["status"] == "Done")
    return {
        "id": project.id,
        "name": project.name,
        "description": project.description,
        "status": project.status,
        "deadline": iso_date(project.deadline),
        "created_at": iso_datetime(project.created_at),
        "owner_id": project.owner_id,
        "my_role": role,
        "capabilities": policy.capabilities(role),
        "members": _members(project),
        "story_count": len(stories),
        "task_count": len(tasks),
        "done_count": done,
        "stories": stories,
    }


def project_summary(project: Project, role: str, stats: dict[str, int]) -> dict:
    return {
        "id": project.id,
        "name": project.name,
        "description": project.description,
        "status": project.status,
        "deadline": iso_date(project.deadline),
        "owner_id": project.owner_id,
        "owner_name": project.owner.name if project.owner else "",
        "my_role": role,
        **stats,
    }


def job_dict(job: BackgroundJob, *, include_result: bool = False) -> dict:
    data = {
        "id": job.id,
        "type": job.job_type,
        "status": job.status,
        "attempts": job.attempts,
        "max_attempts": job.max_attempts,
        "next_run_at": iso_datetime(job.next_run_at),
        "error": job.error,
        "has_result": bool(job.result),
        "created_at": iso_datetime(job.created_at),
        "updated_at": iso_datetime(job.updated_at),
    }
    if job.job_type == "send_email":
        data["summary"] = f"Email to {(job.payload or {}).get('to', '?')}: {(job.payload or {}).get('subject', '')}"
    else:
        data["summary"] = "Progress report"
    if include_result:
        data["result"] = job.result
    return data
