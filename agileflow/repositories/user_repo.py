from __future__ import annotations

from sqlalchemy import func, select

from ..extensions import db
from ..models import User


def get(user_id: int | None) -> User | None:
    return db.session.get(User, user_id) if user_id else None


def by_email(email: str) -> User | None:
    return db.session.execute(select(User).where(User.email == email)).scalar_one_or_none()


def count() -> int:
    return db.session.execute(select(func.count(User.id))).scalar_one()
