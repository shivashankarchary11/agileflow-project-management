"""Registration and login rules."""

from __future__ import annotations

from flask import current_app
from werkzeug.security import check_password_hash, generate_password_hash

from ..domain.constants import GLOBAL_ROLES, MEMBER, TEAM_LEAD
from ..domain.errors import Conflict, Unauthorized, ValidationError
from ..extensions import db
from ..models import User
from ..repositories import user_repo

_DUMMY_HASH: str | None = None


def _dummy_hash() -> str:
    # Checked when the email is unknown, so "no such user" costs the same time as "wrong password".
    global _DUMMY_HASH
    if _DUMMY_HASH is None:
        _DUMMY_HASH = generate_password_hash("not-a-real-password", method=current_app.config["PASSWORD_HASH_METHOD"])
    return _DUMMY_HASH


def register(*, name: str, email: str, password: str, requested_role: str | None, allow_select_role: bool) -> User:
    if user_repo.by_email(email):
        raise Conflict("An account with this email already exists.")
    if allow_select_role:
        role = requested_role or MEMBER
        if role not in GLOBAL_ROLES:
            raise ValidationError(f"Role must be one of: {', '.join(GLOBAL_ROLES)}.")
    else:
        # Production-style policy: the first account administers the team, everyone else is a Member.
        role = TEAM_LEAD if user_repo.count() == 0 else MEMBER
    method = current_app.config["PASSWORD_HASH_METHOD"]
    user = User(name=name, email=email, password_hash=generate_password_hash(password, method=method), role=role)
    db.session.add(user)
    db.session.commit()
    return user


def authenticate(email: str, password: str) -> User:
    user = user_repo.by_email(email)
    if user is None:
        check_password_hash(_dummy_hash(), password)
        raise Unauthorized("Incorrect email or password.")
    if not check_password_hash(user.password_hash, password):
        raise Unauthorized("Incorrect email or password.")
    return user
