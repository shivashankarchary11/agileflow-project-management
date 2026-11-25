from __future__ import annotations

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import selectinload

from ..extensions import db
from ..models import Task, UserStory


def get(task_id: int) -> Task | None:
    return db.session.get(Task, task_id)


def next_position(story_id: int) -> int:
    top = db.session.execute(select(func.max(Task.position)).where(Task.story_id == story_id)).scalar_one()
    return 0 if top is None else top + 1


def siblings(story_id: int) -> list[Task]:
    return list(
        db.session.execute(select(Task).where(Task.story_id == story_id).order_by(Task.position, Task.id)).scalars()
    )


def board(
    project_id: int,
    *,
    assignee_id: int | None = None,
    priority: str | None = None,
    story_id: int | None = None,
    q: str | None = None,
) -> list[Task]:
    """All tasks of a project (with story + assignee loaded) matching the filters."""
    stmt = (
        select(Task)
        .join(UserStory, Task.story_id == UserStory.id)
        .where(UserStory.project_id == project_id)
        .options(selectinload(Task.story), selectinload(Task.assignee))
        .order_by(UserStory.position, UserStory.id, Task.position, Task.id)
    )
    if assignee_id is not None:
        stmt = stmt.where(Task.assigned_to_id == assignee_id)
    if priority:
        stmt = stmt.where(UserStory.priority == priority)
    if story_id is not None:
        stmt = stmt.where(Task.story_id == story_id)
    if q:
        stmt = stmt.where(
            or_(Task.title.icontains(q, autoescape=True), UserStory.title.icontains(q, autoescape=True))
        )
    return list(db.session.execute(stmt).scalars())


def unassign_user_in_project(project_id: int, user_id: int) -> None:
    """Clear the assignee on every task of ``project_id`` that was assigned to ``user_id``."""
    story_ids = select(UserStory.id).where(UserStory.project_id == project_id)
    db.session.execute(
        update(Task).where(Task.story_id.in_(story_ids), Task.assigned_to_id == user_id).values(assigned_to_id=None)
    )
