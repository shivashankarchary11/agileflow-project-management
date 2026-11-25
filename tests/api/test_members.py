"""MEM-01 .. MEM-04."""

from tests.helpers import create_story, create_task


def test_mem_01_add_member_and_viewer(world, make_actor):
    newcomer = make_actor("New Person")
    response = world.lead.post(f"/api/projects/{world.pid}/members", {"email": newcomer.email, "role": "Viewer"})
    assert response.status_code == 201
    assert any(m["email"] == newcomer.email and m["role"] == "Viewer" for m in response.get_json()["members"])
    assert newcomer.get(f"/api/projects/{world.pid}").status_code == 200


def test_mem_01b_email_lookup_is_case_insensitive(world, make_actor):
    newcomer = make_actor("New Person")
    response = world.lead.post(f"/api/projects/{world.pid}/members", {"email": newcomer.email.upper()})
    assert response.status_code == 201


def test_mem_02_rejections(world):
    url = f"/api/projects/{world.pid}/members"
    assert world.lead.post(url, {"email": "ghost@example.com"}).status_code == 404
    assert world.lead.post(url, {"email": world.lead.email}).status_code == 400  # the owner
    assert world.lead.post(url, {"email": world.outsider.email, "role": "Team Lead"}).status_code == 400
    assert world.lead.post(url, {"email": "not-an-email"}).status_code == 400
    assert world.lead.post(url, {"role": "Member"}).status_code == 400


def test_mem_02b_only_lead_can_manage_members(world):
    url = f"/api/projects/{world.pid}/members"
    assert world.member.post(url, {"email": world.outsider.email}).status_code == 403
    assert world.viewer.post(url, {"email": world.outsider.email}).status_code == 403
    assert world.outsider.post(url, {"email": world.outsider.email}).status_code == 404


def test_mem_03_re_adding_changes_role(world):
    url = f"/api/projects/{world.pid}/members"
    response = world.lead.post(url, {"email": world.viewer.email, "role": "Member"})
    assert response.status_code == 200  # updated, not created
    assert world.viewer.post(f"/api/projects/{world.pid}/stories", {"title": "Now allowed"}).status_code == 201


def test_mem_04_remove_member_unassigns_their_tasks(world):
    story = create_story(world.lead, world.pid)
    task = create_task(world.lead, story["id"], assigned_to_id=world.member.id)
    response = world.lead.delete(f"/api/projects/{world.pid}/members/{world.member.id}")
    assert response.status_code == 200
    assert all(m["id"] != world.member.id for m in response.get_json()["members"])
    assert world.lead.get(f"/api/tasks/{task['id']}").get_json()["assigned_to_id"] is None
    assert world.member.get(f"/api/projects/{world.pid}").status_code == 404  # lost access


def test_mem_04b_remove_unknown_member_404_and_non_lead_403(world):
    assert world.lead.delete(f"/api/projects/{world.pid}/members/9999").status_code == 404
    assert world.lead.delete(f"/api/projects/{world.pid}/members/{world.lead.id}").status_code == 404  # owner is not a member row
    assert world.member.delete(f"/api/projects/{world.pid}/members/{world.viewer.id}").status_code == 403
