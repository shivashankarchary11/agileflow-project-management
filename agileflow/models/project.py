from __future__ import annotations

from ..domain.constants import MEMBER
from ..extensions import db
from .base import utcnow


class Project(db.Model):
    __tablename__ = "project"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=False, default="")
    status = db.Column(db.String(30), nullable=False, default="Active")
    deadline = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    owner_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="RESTRICT"), nullable=False, index=True)

    owner = db.relationship("User")
    members = db.relationship("ProjectMember", back_populates="project", cascade="all, delete-orphan")
    stories = db.relationship(
        "UserStory",
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="UserStory.position, UserStory.id",
    )


class ProjectMember(db.Model):
    __tablename__ = "project_member"
    __table_args__ = (db.UniqueConstraint("project_id", "user_id", name="uq_project_member"),)

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)
    role = db.Column(db.String(20), nullable=False, default=MEMBER)

    project = db.relationship("Project", back_populates="members")
    user = db.relationship("User")
