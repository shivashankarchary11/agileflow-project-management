"""The permission matrix, tested without any HTTP or database."""

import pytest

from agileflow.domain import policy
from agileflow.domain.errors import Forbidden

ALLOWED = {
    "project.view": {"Team Lead", "Member", "Viewer"},
    "project.edit": {"Team Lead"},
    "project.delete": {"Team Lead"},
    "member.manage": {"Team Lead"},
    "story.create": {"Team Lead", "Member"},
    "story.edit": {"Team Lead", "Member"},
    "story.delete": {"Team Lead"},
    "task.create": {"Team Lead", "Member"},
    "task.edit": {"Team Lead", "Member"},
    "task.delete": {"Team Lead"},
}


@pytest.mark.parametrize("action", sorted(ALLOWED))
@pytest.mark.parametrize("role", ["Team Lead", "Member", "Viewer", None])
def test_matrix(role, action):
    assert policy.can(role, action) is (role in ALLOWED[action])


def test_matrix_covers_every_action():
    assert set(policy.PERMISSIONS) == set(ALLOWED)


def test_require_raises_forbidden():
    policy.require("Team Lead", "project.delete")
    with pytest.raises(Forbidden):
        policy.require("Viewer", "story.create")
    with pytest.raises(Forbidden):
        policy.require(None, "project.view")


def test_unknown_action_is_a_programming_error():
    with pytest.raises(KeyError):
        policy.can("Team Lead", "project.explode")


def test_capabilities_map():
    assert policy.capabilities("Viewer") == {a: a == "project.view" for a in ALLOWED}
    assert all(policy.capabilities("Team Lead").values())
    assert not any(policy.capabilities(None).values())
