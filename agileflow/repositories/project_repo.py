from __future__ import annotations

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import selectinload

from ..domain.constants import TEAM_LEAD
from ..extensions import db
from ..models import Project, ProjectMember, Task, UserStory


def get(project_id: int) -> Project | None:
    return db.session.get(Project, project_id)


def get_with_tree(project_id: int) -> Project | None:
    """Project plus members, stories, tasks and assignees in a handful of queries (no N+1)."""
    stmt = (
        select(Project)
        .where(Project.id == project_id)
        .options(
            selectinload(Project.owner),
            selectinload(Project.members).selectinload(ProjectMember.user),
            selectinload(Project.stories).selectinload(UserStory.tasks).selectinload(Task.assignee),
        )
    )
    return db.session.execute(stmt).scalar_one_or_none()


def _visible_to(user_id: int):
    member_of = select(ProjectMember.project_id).where(ProjectMember.user_id == user_id)
    return or_(Project.owner_id == user_id, Project.id.in_(member_of))


def list_for_user(user_id: int, *, q: str | None = None, limit: int = 50, offset: int = 0):
    """Projects the user owns or belongs to, newest first. Returns ``(items, total)``."""
    stmt = select(Project).where(_visible_to(user_id))
    if q:
        stmt = stmt.where(Project.name.icontains(q, autoescape=True))
    total = db.session.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    items = (
        db.session.execute(
            stmt.options(selectinload(Project.owner)).order_by(Project.id.desc()).limit(limit).offset(offset)
        )
        .scalars()
        .all()
    )
    return items, total


def accessible_ids(user_id: int) -> list[int]:
    return list(db.session.execute(select(Project.id).where(_visible_to(user_id))).scalars())


def stats(project_ids: list[int]) -> dict[int, dict[str, int]]:
    """Story/task/done counts per project using two grouped queries."""
    result = {pid: {"story_count": 0, "task_count": 0, "done_count": 0} for pid in project_ids}
    if not project_ids:
        return result
    for pid, n in db.session.execute(
        select(UserStory.project_id, func.count(UserStory.id))
        .where(UserStory.project_id.in_(project_ids))
        .group_by(UserStory.project_id)
    ):
        result[pid]["story_count"] = n
    done = case((Task.status == "Done", 1), else_=0)
    for pid, total, done_n in db.session.execute(
        select(UserStory.project_id, func.count(Task.id), func.coalesce(func.sum(done), 0))
        .join(Task, Task.story_id == UserStory.id)
        .where(UserStory.project_id.in_(project_ids))
        .group_by(UserStory.project_id)
    ):
        result[pid]["task_count"] = total
        result[pid]["done_count"] = int(done_n)
    return result


def roles_for(user_id: int, projects: list[Project]) -> dict[int, str]:
    """Role of ``user_id`` in each project (one query for all memberships)."""
    roles = {p.id: TEAM_LEAD for p in projects if p.owner_id == user_id}
    others = [p.id for p in projects if p.id not in roles]
    if others:
        for pid, role in db.session.execute(
            select(ProjectMember.project_id, ProjectMember.role).where(
                ProjectMember.user_id == user_id, ProjectMember.project_id.in_(others)
            )
        ):
            roles[pid] = role
    return roles


def task_status_counts(project_ids: list[int], today) -> dict[int, dict[str, int]]:
    """Tasks per status per project, plus how many open tasks are overdue (``today`` is a date)."""
    result = {pid: {"To Do": 0, "In Progress": 0, "Done": 0, "overdue": 0} for pid in project_ids}
    if not project_ids:
        return result
    for pid, status, n in db.session.execute(
        select(UserStory.project_id, Task.status, func.count(Task.id))
        .join(Task, Task.story_id == UserStory.id)
        .where(UserStory.project_id.in_(project_ids))
        .group_by(UserStory.project_id, Task.status)
    ):
        if status in result[pid]:
            result[pid][status] = n
    for pid, n in db.session.execute(
        select(UserStory.project_id, func.count(Task.id))
        .join(Task, Task.story_id == UserStory.id)
        .where(
            UserStory.project_id.in_(project_ids),
            Task.status != "Done",
            Task.due_date.is_not(None),
            Task.due_date < today,
        )
        .group_by(UserStory.project_id)
    ):
        result[pid]["overdue"] = n
    return result


def get_member(project_id: int, user_id: int) -> ProjectMember | None:
    return db.session.execute(
        select(ProjectMember).where(ProjectMember.project_id == project_id, ProjectMember.user_id == user_id)
    ).scalar_one_or_none()


def role_of(project: Project, user_id: int) -> str | None:
    """The user's role *inside this project*: Team Lead (owner), the member role, or ``None``."""
    if project.owner_id == user_id:
        return TEAM_LEAD
    membership = get_member(project.id, user_id)
    return membership.role if membership else None


def is_participant(project: Project, user_id: int) -> bool:
    return role_of(project, user_id) is not None
