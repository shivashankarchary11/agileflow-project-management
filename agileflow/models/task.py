from __future__ import annotations

from ..extensions import db
from .base import utcnow


class Task(db.Model):
    __tablename__ = "task"

    id = db.Column(db.Integer, primary_key=True)
    story_id = db.Column(db.Integer, db.ForeignKey("user_story.id", ondelete="CASCADE"), nullable=False, index=True)
    title = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, nullable=False, default="")
    status = db.Column(db.String(30), nullable=False, default="To Do")
    due_date = db.Column(db.Date, nullable=True)
    # 0-based order of this task inside its story.
    position = db.Column(db.Integer, nullable=False, default=0)
    assigned_to_id = db.Column(db.Integer, db.ForeignKey("user.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    story = db.relationship("UserStory", back_populates="tasks")
    assignee = db.relationship("User")
