"""Load a record *and* check the caller may act on it, in one step.

Visibility rule: a person who is not in a project gets ``404`` for anything inside
it (so IDs cannot be probed). A person who is in the project but lacks the
permission gets ``403``.
"""

from __future__ import annotations

from ..domain import policy
from ..domain.errors import NotFound
from ..models import Project, Task, User, UserStory
from ..repositories import project_repo, story_repo, task_repo


def project_for(user: User, project_id: int, action: str = "project.view") -> tuple[Project, str]:
    project = project_repo.get(project_id)
    role = project_repo.role_of(project, user.id) if project else None
    if role is None:
        raise NotFound("Project not found.")
    policy.require(role, action)
    return project, role


def story_for(user: User, story_id: int, action: str = "project.view") -> tuple[UserStory, Project, str]:
    story = story_repo.get(story_id)
    if story is None:
        raise NotFound("User story not found.")
    try:
        project, role = project_for(user, story.project_id, action)
    except NotFound:
        raise NotFound("User story not found.") from None
    return story, project, role


def task_for(user: User, task_id: int, action: str = "project.view") -> tuple[Task, Project, str]:
    task = task_repo.get(task_id)
    if task is None:
        raise NotFound("Task not found.")
    try:
        project, role = project_for(user, task.story.project_id, action)
    except NotFound:
        raise NotFound("Task not found.") from None
    return task, project, role
