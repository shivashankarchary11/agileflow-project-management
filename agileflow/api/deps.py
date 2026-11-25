"""Request helpers shared by the blueprints."""

from __future__ import annotations

from functools import wraps

from flask import g, redirect, request, session, url_for

from ..domain.errors import Unauthorized, ValidationError
from ..models import User
from ..repositories import user_repo


def json_body():
    """Parsed JSON body. A missing/invalid body is a 400 (not an HTML error page)."""
    data = request.get_json(silent=True)
    if data is None:
        raise ValidationError("Request body must be valid JSON.")
    return data


def current_user() -> User:
    """The logged-in user, loaded fresh from the DB (so role changes apply immediately)."""
    if "current_user" not in g:
        user = user_repo.get(session.get("user_id"))
        if user is None:
            session.clear()
            raise Unauthorized("Please log in to continue.")
        g.current_user = user
    return g.current_user


def login_required(view):
    """For JSON endpoints: respond 401 JSON when not logged in."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        current_user()
        return view(*args, **kwargs)

    return wrapped


def page_login_required(view):
    """For HTML pages: redirect to the login page when not logged in."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        try:
            current_user()
        except Unauthorized:
            return redirect(url_for("web.login_page"))
        return view(*args, **kwargs)

    return wrapped
