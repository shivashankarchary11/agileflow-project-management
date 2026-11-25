from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request, session

from .. import security
from ..services import auth_service
from . import schemas
from .deps import current_user, json_body, login_required

bp = Blueprint("auth", __name__)


def _limiter_key(prefix: str, extra: str = "") -> str:
    return f"{prefix}|{request.remote_addr}|{extra}"


def _start_session(user) -> None:
    session.clear()
    session.permanent = True
    session["user_id"] = user.id
    security.rotate_csrf_token()


@bp.post("/auth/register")
def register():
    cfg = current_app.config
    limiter = current_app.extensions["rate_limiter"]
    key = _limiter_key("register")
    if cfg["RATE_LIMIT_ENABLED"]:
        limiter.check(key, cfg["REGISTER_RATE_LIMIT"])
        limiter.record(key)
    data = schemas.parse_register(json_body())
    user = auth_service.register(allow_select_role=cfg["ALLOW_SELF_SELECT_ROLE"], **data)
    _start_session(user)
    return jsonify({"message": "Account created.", "role": user.role, "csrf_token": session["csrf_token"]}), 201


@bp.post("/auth/login")
def login():
    cfg = current_app.config
    limiter = current_app.extensions["rate_limiter"]
    data = schemas.parse_login(json_body())
    key = _limiter_key("login", data["email"])
    if cfg["RATE_LIMIT_ENABLED"]:
        limiter.check(key, cfg["LOGIN_RATE_LIMIT"])
    try:
        user = auth_service.authenticate(data["email"], data["password"])
    except Exception:
        if cfg["RATE_LIMIT_ENABLED"]:
            limiter.record(key)  # only failed attempts count towards the limit
        raise
    limiter.reset(key)
    _start_session(user)
    return jsonify({"message": "Logged in successfully.", "role": user.role, "csrf_token": session["csrf_token"]})


@bp.post("/auth/logout")
def logout():
    session.clear()
    return jsonify({"message": "Logged out."})


@bp.get("/api/csrf-token")
def csrf_token():
    """Token for API clients that are not the bundled UI (the UI reads it from the page)."""
    return jsonify({"csrf_token": security.get_csrf_token()})


@bp.get("/api/me")
@login_required
def me():
    user = current_user()
    return jsonify({"id": user.id, "name": user.name, "email": user.email, "role": user.role})
