"""Browser pages (HTML shells). All data comes from the JSON API via JavaScript."""

from __future__ import annotations

from flask import Blueprint, current_app, redirect, render_template, session, url_for

from .. import security
from ..api.deps import current_user, page_login_required

bp = Blueprint("web", __name__)


@bp.get("/")
@page_login_required
def index():
    user = current_user()
    return render_template("index.html", user=user, csrf_token=security.get_csrf_token())


def _auth_page(mode: str):
    if session.get("user_id"):
        return redirect(url_for("web.index"))
    return render_template(
        "login.html",
        mode=mode,
        csrf_token=security.get_csrf_token(),
        allow_role_select=current_app.config["ALLOW_SELF_SELECT_ROLE"],
    )


@bp.get("/login")
def login_page():
    return _auth_page("login")


@bp.get("/register")
def register_page():
    return _auth_page("register")
