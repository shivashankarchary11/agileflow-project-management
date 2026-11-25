from __future__ import annotations

from flask import Blueprint, jsonify, request

from ..services import report_service
from . import schemas
from .deps import current_user, login_required

bp = Blueprint("jobs", __name__, url_prefix="/api")


@bp.post("/reports")
@login_required
def start_report():
    body = request.get_json(silent=True)
    fail_n = 0
    if isinstance(body, dict) and "fail_n_times" in body:
        fail_n = schemas.integer(body["fail_n_times"], "fail_n_times", minimum=0)
    job = report_service.request_report(current_user(), fail_n_times=fail_n)
    return jsonify({**job, "job_id": job["id"], "message": "Report generation started in the background."}), 202


@bp.get("/jobs")
@login_required
def list_jobs():
    limit, _ = schemas.parse_paging(request.args)
    return jsonify({"items": report_service.list_jobs(current_user(), limit)})


@bp.get("/jobs/<int:job_id>")
@login_required
def get_job(job_id):
    return jsonify(report_service.get_job(current_user(), job_id))


@bp.post("/jobs/<int:job_id>/retry")
@login_required
def retry_job(job_id):
    return jsonify(report_service.retry_job(current_user(), job_id)), 202
