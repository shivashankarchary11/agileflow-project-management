"""ORG-01 .. ORG-05: moving, reordering, filtering, board and paging."""

from tests.helpers import add_member, create_project, create_story, create_task


def titles(items):
    return [i["title"] for i in items]


def test_org_01_move_task_to_another_story_same_project(world):
    s1, s2 = create_story(world.lead, world.pid, "S1"), create_story(world.lead, world.pid, "S2")
    a = create_task(world.lead, s1["id"], "A")
    create_task(world.lead, s1["id"], "B")
    create_task(world.lead, s2["id"], "C")
    response = world.member.patch(f"/api/tasks/{a['id']}/move", {"story_id": s2["id"], "position": 0})
    assert response.status_code == 200 and response.get_json()["story_id"] == s2["id"]
    stories = {s["title"]: s for s in world.lead.get(f"/api/projects/{world.pid}/stories").get_json()["items"]}
    assert [(t["title"], t["position"]) for t in stories["S1"]["tasks"]] == [("B", 0)]  # old story renumbered
    assert [(t["title"], t["position"]) for t in stories["S2"]["tasks"]] == [("A", 0), ("C", 1)]


def test_org_01b_move_changes_status_too(world):
    s1 = create_story(world.lead, world.pid)
    task = create_task(world.lead, s1["id"])
    moved = world.lead.patch(f"/api/tasks/{task['id']}/move", {"status": "Done"}).get_json()
    assert moved["status"] == "Done"


def test_org_02_cannot_move_across_projects(world, make_actor):
    other_lead = make_actor("Other Lead", "Team Lead")
    other_project = create_project(other_lead, "Other")
    foreign_story = create_story(other_lead, other_project["id"], "Foreign")
    s1 = create_story(world.lead, world.pid)
    task = create_task(world.lead, s1["id"])
    response = world.lead.patch(f"/api/tasks/{task['id']}/move", {"story_id": foreign_story["id"]})
    assert response.status_code == 400
    # a story that does not exist gets the same answer (no information leak)
    assert world.lead.patch(f"/api/tasks/{task['id']}/move", {"story_id": 99999}).status_code == 400
    assert world.lead.get(f"/api/tasks/{task['id']}").get_json()["story_id"] == s1["id"]


def test_org_03_reorder_tasks_within_story(world):
    s1 = create_story(world.lead, world.pid)
    create_task(world.lead, s1["id"], "A")
    create_task(world.lead, s1["id"], "B")
    c = create_task(world.lead, s1["id"], "C")
    world.lead.patch(f"/api/tasks/{c['id']}/move", {"position": 0})
    tasks = world.lead.get(f"/api/stories/{s1['id']}").get_json()["tasks"]
    assert [(t["title"], t["position"]) for t in tasks] == [("C", 0), ("A", 1), ("B", 2)]
    world.lead.patch(f"/api/tasks/{c['id']}/move", {"position": 99})  # clamped to the end
    tasks = world.lead.get(f"/api/stories/{s1['id']}").get_json()["tasks"]
    assert titles(tasks) == ["A", "B", "C"]


def test_org_03b_reorder_stories(world):
    ids = [create_story(world.lead, world.pid, f"S{i}")["id"] for i in range(3)]
    assert world.member.patch(f"/api/stories/{ids[2]}/move", {"position": 0}).status_code == 200
    listing = world.lead.get(f"/api/projects/{world.pid}/stories").get_json()["items"]
    assert [(s["title"], s["position"]) for s in listing] == [("S2", 0), ("S0", 1), ("S1", 2)]
    assert world.lead.patch(f"/api/stories/{ids[0]}/move", {}).status_code == 400
    assert world.lead.patch(f"/api/stories/{ids[0]}/move", {"position": -1}).status_code == 400
    assert world.viewer.patch(f"/api/stories/{ids[0]}/move", {"position": 0}).status_code == 403


def test_org_03c_move_requires_a_change_and_permission(world):
    task = create_task(world.lead, create_story(world.lead, world.pid)["id"])
    url = f"/api/tasks/{task['id']}/move"
    assert world.lead.patch(url, {}).status_code == 400
    assert world.lead.patch(url, {"status": "Blocked"}).status_code == 400
    assert world.lead.patch(url, {"position": "first"}).status_code == 400
    assert world.viewer.patch(url, {"status": "Done"}).status_code == 403
    assert world.outsider.patch(url, {"status": "Done"}).status_code == 404


def build_filter_data(world):
    s_high = create_story(world.lead, world.pid, "Login page", priority="High", status="In Progress")
    s_low = create_story(world.lead, world.pid, "Footer links", priority="Low")
    create_task(world.lead, s_high["id"], "Design form", assigned_to_id=world.member.id, status="Done")
    create_task(world.lead, s_high["id"], "Write API", assigned_to_id=world.lead.id)
    create_task(world.lead, s_low["id"], "Add links")
    return s_high, s_low


def test_org_04_filter_stories(world):
    build_filter_data(world)
    base = f"/api/projects/{world.pid}/stories"
    get = lambda qs: world.lead.get(f"{base}?{qs}").get_json()  # noqa: E731
    assert titles(get("priority=High")["items"]) == ["Login page"]
    assert titles(get("status=In Progress")["items"]) == ["Login page"]
    assert titles(get(f"assignee_id={world.member.id}")["items"]) == ["Login page"]
    assert titles(get("q=footer")["items"]) == ["Footer links"]
    assert titles(get("q=ADD LINKS")["items"]) == ["Footer links"]  # matches a *task* title, case-insensitive
    assert titles(get("q=links add")["items"]) == []  # plain substring match, not word search
    assert titles(get("priority=High&status=To Do")["items"]) == []
    assert get("q=nomatch")["total"] == 0
    assert get("")["total"] == 2


def test_org_04b_filter_values_are_validated_and_wildcards_literal(world):
    build_filter_data(world)
    base = f"/api/projects/{world.pid}/stories"
    assert world.lead.get(f"{base}?priority=Urgent").status_code == 400
    assert world.lead.get(f"{base}?status=Nope").status_code == 400
    assert world.lead.get(f"{base}?assignee_id=abc").status_code == 400
    assert world.lead.get(f"{base}?q={'x' * 101}").status_code == 400
    assert world.lead.get(f"{base}?q=%25").get_json()["total"] == 0  # '%' is not a wildcard


def test_org_04c_paging(world):
    for i in range(5):
        create_story(world.lead, world.pid, f"S{i}")
    page = world.lead.get(f"/api/projects/{world.pid}/stories?limit=2&offset=2").get_json()
    assert titles(page["items"]) == ["S2", "S3"] and page["total"] == 5 and page["limit"] == 2
    assert world.lead.get(f"/api/projects/{world.pid}/stories?limit=1000").get_json()["limit"] == 200  # capped
    assert world.lead.get(f"/api/projects/{world.pid}/stories?offset=-1").status_code == 400


def test_org_05_board_groups_by_status(world):
    build_filter_data(world)
    board = world.viewer.get(f"/api/projects/{world.pid}/board").get_json()
    assert list(board["columns"]) == ["To Do", "In Progress", "Done"]
    assert titles(board["columns"]["Done"]) == ["Design form"]
    assert sorted(titles(board["columns"]["To Do"])) == ["Add links", "Write API"]
    assert board["total"] == 3


def test_org_05b_board_filters(world):
    build_filter_data(world)
    get = lambda qs: world.lead.get(f"/api/projects/{world.pid}/board?{qs}").get_json()  # noqa: E731
    assert get("priority=Low")["total"] == 1
    assert get(f"assignee_id={world.lead.id}")["total"] == 1
    assert get("q=form")["total"] == 1  # task title "Design form"
    assert get("q=login")["total"] == 2  # story title "Login page" matches both of its tasks


def test_board_rejects_bad_filter(world):
    assert world.lead.get(f"/api/projects/{world.pid}/board?priority=Nope").status_code == 400


def test_add_member_then_board_sees_their_tasks(world, make_actor):
    newcomer = make_actor("New Person")
    add_member(world.lead, world.pid, newcomer)
    story = create_story(world.lead, world.pid)
    create_task(world.lead, story["id"], "Mine", assigned_to_id=newcomer.id)
    assert newcomer.get(f"/api/projects/{world.pid}/board?assignee_id={newcomer.id}").get_json()["total"] == 1
