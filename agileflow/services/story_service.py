"""User story rules."""

from __future__ import annotations

from ..domain.errors import ValidationError
from ..extensions import db
from ..models import User, UserStory
from ..repositories import story_repo
from . import ordering, serializers
from .access import project_for, story_for


def create_story(user: User, project_id: int, data: dict) -> dict:
    project, _ = project_for(user, project_id, "story.create")
    story = UserStory(
        project_id=project.id,
        title=data["title"],
        description=data.get("description", ""),
        priority=data.get("priority", "Medium"),
        status=data.get("status", "To Do"),
        position=story_repo.next_position(project.id),
    )
    db.session.add(story)
    db.session.commit()
    return serializers.story_dict(story)


def get_story(user: User, story_id: int) -> dict:
    story, _, _ = story_for(user, story_id)
    return serializers.story_dict(story)


def list_stories(user: User, project_id: int, filters: dict, limit: int, offset: int) -> dict:
    project, _ = project_for(user, project_id)
    items, total = story_repo.list_filtered(project.id, limit=limit, offset=offset, **filters)
    return {"items": [serializers.story_dict(s) for s in items], "total": total, "limit": limit, "offset": offset}


def update_story(user: User, story_id: int, data: dict) -> dict:
    story, _, _ = story_for(user, story_id, "story.edit")
    for key in ("title", "description", "priority", "status"):
        if key in data:
            setattr(story, key, data[key])
    db.session.commit()
    return serializers.story_dict(story)


def delete_story(user: User, story_id: int) -> None:
    story, project, _ = story_for(user, story_id, "story.delete")
    db.session.delete(story)
    db.session.flush()
    ordering.resequence(story_repo.siblings(project.id))
    db.session.commit()


def move_story(user: User, story_id: int, position: int | None) -> dict:
    story, project, _ = story_for(user, story_id, "story.edit")
    if position is None:
        raise ValidationError("'position' is required.")
    ordering.place(story_repo.siblings(project.id), story, position)
    db.session.commit()
    return serializers.story_dict(story)
