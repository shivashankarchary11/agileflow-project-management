from __future__ import annotations

from ..extensions import db
from .base import utcnow


class UserStory(db.Model):
    __tablename__ = "user_story"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id", ondelete="CASCADE"), nullable=False, index=True)
    title = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, nullable=False, default="")
    priority = db.Column(db.String(20), nullable=False, default="Medium")
    status = db.Column(db.String(30), nullable=False, default="To Do")
    # 0-based order of this story inside its project.
    position = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    project = db.relationship("Project", back_populates="stories")
    tasks = db.relationship(
        "Task",
        back_populates="story",
        cascade="all, delete-orphan",
        order_by="Task.position, Task.id",
    )
