"""Task rules: create, edit, assign, move/reorder and the Kanban board."""

from __future__ import annotations

from ..domain.constants import WORK_STATUSES
from ..domain.errors import ValidationError
from ..extensions import db
from ..models import Project, Task, User
from ..repositories import project_repo, story_repo, task_repo, user_repo
from . import notification_service, ordering, serializers
from .access import project_for, story_for, task_for


def _resolve_assignee(project: Project, assignee_id: int | None) -> User | None:
    """The assignee must be the project's Team Lead or one of its members."""
    if assignee_id is None:
        return None
    assignee = user_repo.get(assignee_id)
    if assignee is None or not project_repo.is_participant(project, assignee.id):
        raise ValidationError("Assignee must be a member of this project.")
    return assignee


def create_task(user: User, story_id: int, data: dict) -> dict:
    story, project, _ = story_for(user, story_id, "task.create")
    assignee = _resolve_assignee(project, data.get("assigned_to_id"))
    task = Task(
        story_id=story.id,
        title=data["title"],
        description=data.get("description", ""),
        status=data.get("status", "To Do"),
        due_date=data.get("due_date"),
        assigned_to_id=assignee.id if assignee else None,
        position=task_repo.next_position(story.id),
    )
    db.session.add(task)
    db.session.commit()
    if assignee:
        notification_service.notify_task_assigned(task, assignee, actor=user)
    return serializers.task_dict(task)


def get_task(user: User, task_id: int) -> dict:
    task, _, _ = task_for(user, task_id)
    return serializers.task_dict(task)


def update_task(user: User, task_id: int, data: dict) -> dict:
    task, project, _ = task_for(user, task_id, "task.edit")
    new_assignee = None
    if "assigned_to_id" in data:
        new_assignee = _resolve_assignee(project, data["assigned_to_id"])
        changed = (new_assignee.id if new_assignee else None) != task.assigned_to_id
        task.assigned_to_id = new_assignee.id if new_assignee else None
        if not changed:
            new_assignee = None  # same person: nothing to announce
    for key in ("title", "description", "status", "due_date"):
        if key in data:
            setattr(task, key, data[key])
    db.session.commit()
    if new_assignee:
        notification_service.notify_task_assigned(task, new_assignee, actor=user)
    return serializers.task_dict(task)


def delete_task(user: User, task_id: int) -> None:
    task, _, _ = task_for(user, task_id, "task.delete")
    story_id = task.story_id
    db.session.delete(task)
    db.session.flush()
    ordering.resequence(task_repo.siblings(story_id))
    db.session.commit()


def move_task(user: User, task_id: int, data: dict) -> dict:
    """Change a task's story, status and/or position (any combination, at least one)."""
    task, project, _ = task_for(user, task_id, "task.edit")
    if not any(k in data for k in ("story_id", "status", "position")):
        raise ValidationError("Provide at least one of: story_id, status, position.")

    if "status" in data:
        task.status = data["status"]

    old_story_id = task.story_id
    target_story_id = data.get("story_id", old_story_id)
    if target_story_id != old_story_id:
        target = story_repo.get(target_story_id)
        if target is None or target.project_id != project.id:
            # Same message whether the story is missing or belongs to someone else's project.
            raise ValidationError("Target story must exist in the same project.")
        task.story_id = target.id
        db.session.flush()
        ordering.resequence(task_repo.siblings(old_story_id))
        ordering.place(task_repo.siblings(target.id), task, data.get("position"))
    elif "position" in data:
        ordering.place(task_repo.siblings(old_story_id), task, data["position"])

    db.session.commit()
    return serializers.task_dict(task)


def board(user: User, project_id: int, filters: dict) -> dict:
    """Tasks of a project grouped into the three Kanban columns."""
    project, _ = project_for(user, project_id)
    tasks = task_repo.board(project.id, **filters)
    columns: dict[str, list[dict]] = {status: [] for status in WORK_STATUSES}
    for task in tasks:
        columns[task.status].append(serializers.task_dict(task))
    return {"project_id": project.id, "columns": columns, "total": len(tasks)}
