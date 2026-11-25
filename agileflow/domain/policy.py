"""Who may do what inside a project. Pure functions, no database access."""

from __future__ import annotations

from .constants import MEMBER, TEAM_LEAD, VIEWER
from .errors import Forbidden

# action -> roles allowed to perform it (role = the person's role *in that project*)
PERMISSIONS: dict[str, frozenset[str]] = {
    "project.view": frozenset({TEAM_LEAD, MEMBER, VIEWER}),
    "project.edit": frozenset({TEAM_LEAD}),
    "project.delete": frozenset({TEAM_LEAD}),
    "member.manage": frozenset({TEAM_LEAD}),
    "story.create": frozenset({TEAM_LEAD, MEMBER}),
    "story.edit": frozenset({TEAM_LEAD, MEMBER}),
    "story.delete": frozenset({TEAM_LEAD}),
    "task.create": frozenset({TEAM_LEAD, MEMBER}),
    "task.edit": frozenset({TEAM_LEAD, MEMBER}),
    "task.delete": frozenset({TEAM_LEAD}),
}


def can(role: str | None, action: str) -> bool:
    """True if ``role`` may perform ``action``. ``None`` (not in the project) never can."""
    if action not in PERMISSIONS:
        raise KeyError(f"Unknown action: {action}")
    return role in PERMISSIONS[action]


def require(role: str | None, action: str) -> None:
    if not can(role, action):
        raise Forbidden("You do not have permission to perform this action.")


def capabilities(role: str | None) -> dict[str, bool]:
    """Action map the UI uses to show or hide buttons (the server still enforces everything)."""
    return {action: can(role, action) for action in PERMISSIONS}
