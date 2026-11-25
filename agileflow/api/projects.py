from __future__ import annotations

from flask import Blueprint, jsonify, request

from ..services import project_service, story_service, task_service
from . import schemas
from .deps import current_user, json_body, login_required

bp = Blueprint("projects", __name__, url_prefix="/api/projects")


@bp.get("")
@login_required
def list_projects():
    limit, offset = schemas.parse_paging(request.args)
    q = schemas.parse_project_search(request.args)
    return jsonify(project_service.list_projects(current_user(), q=q, limit=limit, offset=offset))


@bp.post("")
@login_required
def create_project():
    data = schemas.parse_project(json_body())
    return jsonify(project_service.create_project(current_user(), data)), 201


@bp.get("/<int:project_id>")
@login_required
def get_project(project_id):
    return jsonify(project_service.get_project(current_user(), project_id))


@bp.patch("/<int:project_id>")
@login_required
def update_project(project_id):
    data = schemas.parse_project(json_body(), partial=True)
    return jsonify(project_service.update_project(current_user(), project_id, data))


@bp.delete("/<int:project_id>")
@login_required
def delete_project(project_id):
    project_service.delete_project(current_user(), project_id)
    return jsonify({"message": "Project deleted."})


@bp.post("/<int:project_id>/members")
@login_required
def add_member(project_id):
    data = schemas.parse_member(json_body())
    project, created = project_service.add_member(current_user(), project_id, data["email"], data["role"])
    return jsonify(project), 201 if created else 200


@bp.delete("/<int:project_id>/members/<int:user_id>")
@login_required
def remove_member(project_id, user_id):
    return jsonify(project_service.remove_member(current_user(), project_id, user_id))


@bp.get("/<int:project_id>/stories")
@login_required
def list_stories(project_id):
    limit, offset = schemas.parse_paging(request.args)
    filters = schemas.parse_story_filters(request.args)
    return jsonify(story_service.list_stories(current_user(), project_id, filters, limit, offset))


@bp.post("/<int:project_id>/stories")
@login_required
def create_story(project_id):
    data = schemas.parse_story(json_body())
    return jsonify(story_service.create_story(current_user(), project_id, data)), 201


@bp.get("/<int:project_id>/board")
@login_required
def board(project_id):
    filters = schemas.parse_board_filters(request.args)
    return jsonify(task_service.board(current_user(), project_id, filters))
