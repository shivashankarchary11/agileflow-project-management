from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from ..extensions import db
from ..models import Task, UserStory


def get(story_id: int) -> UserStory | None:
    return db.session.get(UserStory, story_id)


def next_position(project_id: int) -> int:
    top = db.session.execute(
        select(func.max(UserStory.position)).where(UserStory.project_id == project_id)
    ).scalar_one()
    return 0 if top is None else top + 1


def siblings(project_id: int) -> list[UserStory]:
    return list(
        db.session.execute(
            select(UserStory).where(UserStory.project_id == project_id).order_by(UserStory.position, UserStory.id)
        ).scalars()
    )


def list_filtered(
    project_id: int,
    *,
    status: str | None = None,
    priority: str | None = None,
    assignee_id: int | None = None,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    """Stories of a project matching the filters. Returns ``(items, total)``."""
    stmt = select(UserStory).where(UserStory.project_id == project_id)
    if status:
        stmt = stmt.where(UserStory.status == status)
    if priority:
        stmt = stmt.where(UserStory.priority == priority)
    if assignee_id is not None:
        stmt = stmt.where(UserStory.tasks.any(Task.assigned_to_id == assignee_id))
    if q:
        stmt = stmt.where(
            or_(
                UserStory.title.icontains(q, autoescape=True),
                UserStory.description.icontains(q, autoescape=True),
                UserStory.tasks.any(Task.title.icontains(q, autoescape=True)),
            )
        )
    total = db.session.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    items = (
        db.session.execute(
            stmt.options(selectinload(UserStory.tasks).selectinload(Task.assignee))
            .order_by(UserStory.position, UserStory.id)
            .limit(limit)
            .offset(offset)
        )
        .scalars()
        .all()
    )
    return items, total
