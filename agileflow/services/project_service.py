"""Project and membership rules."""

from __future__ import annotations

from ..domain.constants import TEAM_LEAD
from ..domain.errors import Forbidden, NotFound, ValidationError
from ..extensions import db
from ..models import Project, ProjectMember, User
from ..repositories import project_repo, task_repo, user_repo
from . import notification_service, serializers
from .access import project_for


def _detail(project_id: int, role: str) -> dict:
    return serializers.project_detail(project_repo.get_with_tree(project_id), role)


def create_project(user: User, data: dict) -> dict:
    if user.role != TEAM_LEAD:
        raise Forbidden("Only a Team Lead can create projects.")
    project = Project(
        name=data["name"],
        description=data.get("description", ""),
        status=data.get("status", "Active"),
        deadline=data.get("deadline"),
        owner_id=user.id,
    )
    db.session.add(project)
    db.session.commit()
    return _detail(project.id, TEAM_LEAD)


def list_projects(user: User, *, q: str | None, limit: int, offset: int) -> dict:
    projects, total = project_repo.list_for_user(user.id, q=q, limit=limit, offset=offset)
    ids = [p.id for p in projects]
    stats, roles = project_repo.stats(ids), project_repo.roles_for(user.id, projects)
    items = [serializers.project_summary(p, roles[p.id], stats[p.id]) for p in projects]
    return {"items": items, "total": total, "limit": limit, "offset": offset}


def get_project(user: User, project_id: int) -> dict:
    project, role = project_for(user, project_id)
    return _detail(project.id, role)


def update_project(user: User, project_id: int, data: dict) -> dict:
    project, role = project_for(user, project_id, "project.edit")
    for key in ("name", "description", "status", "deadline"):
        if key in data:
            setattr(project, key, data[key])
    db.session.commit()
    return _detail(project.id, role)


def delete_project(user: User, project_id: int) -> None:
    project, _ = project_for(user, project_id, "project.delete")
    db.session.delete(project)
    db.session.commit()


def add_member(user: User, project_id: int, email: str, role: str) -> tuple[dict, bool]:
    """Add (or change the role of) a registered user. Returns ``(project, created)``."""
    project, my_role = project_for(user, project_id, "member.manage")
    target = user_repo.by_email(email)
    if target is None:
        raise NotFound("No registered user found with that email. Ask them to create an account first.")
    if target.id == project.owner_id:
        raise ValidationError("The Team Lead already owns this project.")
    membership = project_repo.get_member(project.id, target.id)
    created = membership is None
    if created:
        db.session.add(ProjectMember(project_id=project.id, user_id=target.id, role=role))
    else:
        membership.role = role
    db.session.commit()
    if created:
        notification_service.notify_member_added(project, target, role, actor=user)
    return _detail(project.id, my_role), created


def remove_member(user: User, project_id: int, member_user_id: int) -> dict:
    project, my_role = project_for(user, project_id, "member.manage")
    membership = project_repo.get_member(project.id, member_user_id)
    if membership is None:
        raise NotFound("Member not found in this project.")
    task_repo.unassign_user_in_project(project.id, member_user_id)
    db.session.delete(membership)
    db.session.commit()
    return _detail(project.id, my_role)
