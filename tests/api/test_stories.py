"""STY-01 .. STY-04."""

from tests.helpers import create_story, create_task


def test_sty_01_lead_and_member_create(world):
    for actor in (world.lead, world.member):
        response = actor.post(f"/api/projects/{world.pid}/stories", {"title": f"By {actor.name}", "priority": "High"})
        assert response.status_code == 201
        body = response.get_json()
        assert body["priority"] == "High" and body["status"] == "To Do" and body["tasks"] == []


def test_sty_01b_positions_are_sequential(world):
    positions = [create_story(world.lead, world.pid, f"S{i}")["position"] for i in range(3)]
    assert positions == [0, 1, 2]


def test_sty_02_viewer_cannot_write(world):
    story = create_story(world.lead, world.pid)
    assert world.viewer.post(f"/api/projects/{world.pid}/stories", {"title": "x"}).status_code == 403
    assert world.viewer.patch(f"/api/stories/{story['id']}", {"status": "Done"}).status_code == 403
    assert world.viewer.get(f"/api/stories/{story['id']}").status_code == 200  # read is fine


def test_sty_03_validation(world):
    url = f"/api/projects/{world.pid}/stories"
    for bad in ({}, {"title": ""}, {"title": 7}, {"title": "ok", "priority": "Urgent"}, {"title": "ok", "status": "Blocked"}, {"title": "t" * 161}):
        assert world.lead.post(url, bad).status_code == 400, bad
    story = create_story(world.lead, world.pid)
    sid = story["id"]
    assert world.lead.patch(f"/api/stories/{sid}", {"title": ""}).status_code == 400
    assert world.lead.patch(f"/api/stories/{sid}", {"title": ["x"]}).status_code == 400
    assert world.lead.patch(f"/api/stories/{sid}", {"priority": "Urgent"}).status_code == 400
    ok = world.lead.patch(f"/api/stories/{sid}", {"title": "New title", "status": "In Progress"})
    assert ok.status_code == 200 and ok.get_json()["title"] == "New title"


def test_sty_04_only_lead_deletes_and_cascades(world, app):
    from agileflow.extensions import db
    from agileflow.models import Task

    story = create_story(world.lead, world.pid)
    create_task(world.lead, story["id"])
    assert world.member.delete(f"/api/stories/{story['id']}").status_code == 403
    assert world.lead.delete(f"/api/stories/{story['id']}").status_code == 200
    with app.app_context():
        assert db.session.query(Task).count() == 0
    assert world.lead.get(f"/api/stories/{story['id']}").status_code == 404


def test_sty_04b_delete_resequences_remaining(world):
    ids = [create_story(world.lead, world.pid, f"S{i}")["id"] for i in range(3)]
    world.lead.delete(f"/api/stories/{ids[0]}")
    listing = world.lead.get(f"/api/projects/{world.pid}/stories").get_json()["items"]
    assert [(s["title"], s["position"]) for s in listing] == [("S1", 0), ("S2", 1)]


def test_stories_of_other_projects_are_hidden(world):
    story = create_story(world.lead, world.pid)
    assert world.outsider.get(f"/api/stories/{story['id']}").status_code == 404
    assert world.outsider.patch(f"/api/stories/{story['id']}", {"title": "x"}).status_code == 404
    assert world.outsider.delete(f"/api/stories/{story['id']}").status_code == 404
