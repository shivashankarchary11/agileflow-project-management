"""TSK-01 .. TSK-05."""

from tests.helpers import create_story, create_task


def test_tsk_01_create_with_valid_assignee(world):
    story = create_story(world.lead, world.pid)
    response = world.member.post(
        f"/api/stories/{story['id']}/tasks",
        {"title": "Build login", "assigned_to_id": world.member.id, "due_date": "2030-06-01", "description": "details"},
    )
    assert response.status_code == 201
    body = response.get_json()
    assert body["assigned_to"] == "Member User" and body["due_date"] == "2030-06-01" and body["status"] == "To Do"
    assert body["project_id"] == world.pid and body["story_title"] == story["title"]


def test_tsk_01b_lead_can_be_assignee_and_viewer_can_be_assigned(world):
    story = create_story(world.lead, world.pid)
    assert create_task(world.lead, story["id"], assigned_to_id=world.lead.id)["assigned_to"] == "Lead User"
    assert create_task(world.lead, story["id"], assigned_to_id=world.viewer.id)["assigned_to"] == "Viewer User"


def test_tsk_02_assignee_must_belong_to_project(world):
    story = create_story(world.lead, world.pid)
    url = f"/api/stories/{story['id']}/tasks"
    assert world.lead.post(url, {"title": "x", "assigned_to_id": world.outsider.id}).status_code == 400
    assert world.lead.post(url, {"title": "x", "assigned_to_id": 99999}).status_code == 400
    assert world.lead.post(url, {"title": "x", "assigned_to_id": "abc"}).status_code == 400
    assert world.lead.post(url, {"title": "x", "assigned_to_id": True}).status_code == 400


def test_tsk_03_due_date_format(world):
    story = create_story(world.lead, world.pid)
    url = f"/api/stories/{story['id']}/tasks"
    for bad in ("01-06-2030", "2030/06/01", "tomorrow", "2030-13-01", "20300601", 20300601):
        assert world.lead.post(url, {"title": "x", "due_date": bad}).status_code == 400, bad
    assert world.lead.post(url, {"title": "x", "due_date": ""}).status_code == 201  # empty = no date


def test_tsk_04_status_progression_persists(world):
    story = create_story(world.lead, world.pid)
    task = create_task(world.member, story["id"])
    for status in ("In Progress", "Done"):
        response = world.member.patch(f"/api/tasks/{task['id']}", {"status": status})
        assert response.status_code == 200
        assert world.member.get(f"/api/tasks/{task['id']}").get_json()["status"] == status
    assert world.member.patch(f"/api/tasks/{task['id']}", {"status": "Blocked"}).status_code == 400


def test_tsk_05_reassign_and_unassign(world):
    story = create_story(world.lead, world.pid)
    task = create_task(world.lead, story["id"], assigned_to_id=world.member.id)
    tid = task["id"]
    moved = world.lead.patch(f"/api/tasks/{tid}", {"assigned_to_id": world.lead.id}).get_json()
    assert moved["assigned_to"] == "Lead User"
    cleared = world.lead.patch(f"/api/tasks/{tid}", {"assigned_to_id": None}).get_json()
    assert cleared["assigned_to_id"] is None and cleared["assigned_to"] == ""
    assert world.lead.patch(f"/api/tasks/{tid}", {"assigned_to_id": world.outsider.id}).status_code == 400


def test_task_permissions(world):
    story = create_story(world.lead, world.pid)
    task = create_task(world.lead, story["id"])
    url = f"/api/tasks/{task['id']}"
    assert world.viewer.post(f"/api/stories/{story['id']}/tasks", {"title": "x"}).status_code == 403
    assert world.viewer.patch(url, {"status": "Done"}).status_code == 403
    assert world.member.delete(url).status_code == 403
    assert world.outsider.get(url).status_code == 404
    assert world.outsider.patch(url, {"status": "Done"}).status_code == 404
    assert world.lead.delete(url).status_code == 200
    assert world.lead.get(url).status_code == 404


def test_task_patch_validation(world):
    story = create_story(world.lead, world.pid)
    url = f"/api/tasks/{create_task(world.lead, story['id'])['id']}"
    assert world.lead.patch(url, {"title": ""}).status_code == 400
    assert world.lead.patch(url, {"title": 5}).status_code == 400
    assert world.lead.patch(url, {"due_date": "nope"}).status_code == 400
    assert world.lead.patch(url, {"due_date": None}).status_code == 200
    assert world.lead.patch(url, "not-an-object").status_code == 400
