from __future__ import annotations

from ..domain.constants import MEMBER
from ..extensions import db
from .base import utcnow


class User(db.Model):
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(160), nullable=False, unique=True, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    # Global role picked at sign-up. It only controls who may create projects.
    role = db.Column(db.String(20), nullable=False, default=MEMBER)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User {self.id} {self.email}>"
