from __future__ import annotations

from flask import Blueprint, jsonify

from ..services import story_service, task_service
from . import schemas
from .deps import current_user, json_body, login_required

bp = Blueprint("stories", __name__, url_prefix="/api/stories")


@bp.get("/<int:story_id>")
@login_required
def get_story(story_id):
    return jsonify(story_service.get_story(current_user(), story_id))


@bp.patch("/<int:story_id>")
@login_required
def update_story(story_id):
    data = schemas.parse_story(json_body(), partial=True)
    return jsonify(story_service.update_story(current_user(), story_id, data))


@bp.delete("/<int:story_id>")
@login_required
def delete_story(story_id):
    story_service.delete_story(current_user(), story_id)
    return jsonify({"message": "Story and its tasks deleted."})


@bp.patch("/<int:story_id>/move")
@login_required
def move_story(story_id):
    data = schemas.parse_story_move(json_body())
    return jsonify(story_service.move_story(current_user(), story_id, data["position"]))


@bp.post("/<int:story_id>/tasks")
@login_required
def create_task(story_id):
    data = schemas.parse_task(json_body())
    return jsonify(task_service.create_task(current_user(), story_id, data)), 201
