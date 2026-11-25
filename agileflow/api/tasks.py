from __future__ import annotations

from flask import Blueprint, jsonify

from ..services import task_service
from . import schemas
from .deps import current_user, json_body, login_required

bp = Blueprint("tasks", __name__, url_prefix="/api/tasks")


@bp.get("/<int:task_id>")
@login_required
def get_task(task_id):
    return jsonify(task_service.get_task(current_user(), task_id))


@bp.patch("/<int:task_id>")
@login_required
def update_task(task_id):
    data = schemas.parse_task(json_body(), partial=True)
    return jsonify(task_service.update_task(current_user(), task_id, data))


@bp.delete("/<int:task_id>")
@login_required
def delete_task(task_id):
    task_service.delete_task(current_user(), task_id)
    return jsonify({"message": "Task deleted."})


@bp.patch("/<int:task_id>/move")
@login_required
def move_task(task_id):
    data = schemas.parse_task_move(json_body())
    return jsonify(task_service.move_task(current_user(), task_id, data))
