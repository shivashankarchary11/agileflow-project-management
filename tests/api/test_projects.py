"""PRJ-01 .. PRJ-06 and project detail/list behaviour."""

from tests.helpers import create_project, create_story, create_task


def test_prj_01_team_lead_creates_project(make_actor):
    lead = make_actor("Lead User", "Team Lead")
    response = lead.post("/api/projects", {"name": "Apollo", "description": "Moon", "status": "On Hold", "deadline": "2030-01-31"})
    assert response.status_code == 201
    body = response.get_json()
    assert (body["name"], body["status"], body["deadline"], body["my_role"]) == ("Apollo", "On Hold", "2030-01-31", "Team Lead")
    assert body["capabilities"]["project.delete"] is True


def test_prj_02_non_leads_cannot_create(make_actor):
    for role in ("Member", "Viewer"):
        person = make_actor(f"{role} Person", role)
        assert person.post("/api/projects", {"name": "Nope"}).status_code == 403


def test_prj_03_invalid_input_is_400_never_500(make_actor):
    lead = make_actor("Lead User", "Team Lead")
    for bad in (
        {"name": ""},
        {"name": "   "},
        {"name": 5},
        {"name": None},
        {},
        {"name": "ok", "status": "Archived"},
        {"name": "ok", "deadline": "31/01/2030"},
        {"name": "ok", "deadline": "2030-02-30"},
        {"name": "ok", "deadline": "<img src=x onerror=alert(1)>"},
        {"name": "x" * 121},
        {"name": "ok", "description": "d" * 2001},
    ):
        response = lead.post("/api/projects", bad)
        assert response.status_code == 400, bad


def test_prj_03b_patch_validates_too(world):
    lead, pid = world.lead, world.pid
    assert lead.patch(f"/api/projects/{pid}", {"name": 5}).status_code == 400
    assert lead.patch(f"/api/projects/{pid}", {"name": "  "}).status_code == 400
    assert lead.patch(f"/api/projects/{pid}", {"status": "Nope"}).status_code == 400
    assert lead.patch(f"/api/projects/{pid}", {"deadline": "soon"}).status_code == 400
    ok = lead.patch(f"/api/projects/{pid}", {"name": "Renamed", "deadline": "2031-05-05"})
    assert ok.status_code == 200
    assert ok.get_json()["name"] == "Renamed"
    cleared = lead.patch(f"/api/projects/{pid}", {"deadline": None})
    assert cleared.get_json()["deadline"] is None


def test_prj_04_list_shows_only_own_or_member_projects(world, make_actor):
    other_lead = make_actor("Other Lead", "Team Lead")
    create_project(other_lead, "Secret Project")
    names = lambda actor: {p["name"] for p in actor.get("/api/projects").get_json()["items"]}  # noqa: E731
    assert names(world.lead) == {"Demo Project"}
    assert names(world.member) == {"Demo Project"}
    assert names(world.viewer) == {"Demo Project"}
    assert names(world.outsider) == set()
    assert names(other_lead) == {"Secret Project"}


def test_prj_04b_list_has_counts_search_and_paging(world):
    story = create_story(world.lead, world.pid, "S1")
    create_task(world.lead, story["id"], "T1", status="Done")
    create_task(world.lead, story["id"], "T2")
    create_project(world.lead, "Another")
    items = world.lead.get("/api/projects").get_json()
    assert items["total"] == 2
    demo = next(p for p in items["items"] if p["name"] == "Demo Project")
    assert (demo["story_count"], demo["task_count"], demo["done_count"]) == (1, 2, 1)
    assert [p["name"] for p in world.lead.get("/api/projects?q=anoth").get_json()["items"]] == ["Another"]
    page = world.lead.get("/api/projects?limit=1&offset=1").get_json()
    assert len(page["items"]) == 1 and page["total"] == 2
    assert world.lead.get("/api/projects?limit=0").status_code == 400
    assert world.lead.get("/api/projects?limit=abc").status_code == 400


def test_prj_05_non_members_get_404_not_403(world):
    pid = world.pid
    outsider = world.outsider
    assert outsider.get(f"/api/projects/{pid}").status_code == 404
    assert outsider.patch(f"/api/projects/{pid}", {"name": "Hacked"}).status_code == 404
    assert outsider.delete(f"/api/projects/{pid}").status_code == 404
    assert outsider.post(f"/api/projects/{pid}/stories", {"title": "x"}).status_code == 404
    assert outsider.get(f"/api/projects/{pid}/board").status_code == 404
    # a project id that does not exist looks identical
    assert outsider.get("/api/projects/99999").status_code == 404


def test_prj_05b_members_cannot_edit_or_delete_project(world):
    for actor in (world.member, world.viewer):
        assert actor.patch(f"/api/projects/{world.pid}", {"name": "x"}).status_code == 403
        assert actor.delete(f"/api/projects/{world.pid}").status_code == 403


def test_prj_06_delete_cascades(world, app):
    from agileflow.extensions import db
    from agileflow.models import ProjectMember, Task, UserStory

    story = create_story(world.lead, world.pid)
    create_task(world.lead, story["id"])
    assert world.lead.delete(f"/api/projects/{world.pid}").status_code == 200
    with app.app_context():
        assert db.session.query(UserStory).count() == 0
        assert db.session.query(Task).count() == 0
        assert db.session.query(ProjectMember).count() == 0
    assert world.lead.get(f"/api/projects/{world.pid}").status_code == 404


def test_project_detail_nests_stories_tasks_and_members(world):
    story = create_story(world.lead, world.pid, "Story A")
    create_task(world.lead, story["id"], "Task A", assigned_to_id=world.member.id)
    detail = world.member.get(f"/api/projects/{world.pid}").get_json()
    assert detail["my_role"] == "Member"
    assert detail["capabilities"]["story.create"] is True
    assert detail["capabilities"]["story.delete"] is False
    assert [m["role"] for m in detail["members"]] == ["Team Lead", "Member", "Viewer"]
    task = detail["stories"][0]["tasks"][0]
    assert task["assigned_to"] == "Member User"


def test_script_in_text_fields_is_stored_as_plain_text(world):
    payload = "<script>alert(1)</script>"
    response = world.lead.patch(f"/api/projects/{world.pid}", {"name": payload, "description": payload})
    assert response.status_code == 200
    assert response.get_json()["name"] == payload  # stored verbatim, escaped by the UI when rendered
    assert response.mimetype == "application/json"
