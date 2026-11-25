"""The whole product story in one test: the flow a team actually follows."""

from tests.helpers import PASSWORD


def test_full_team_workflow(app, run_jobs):
    lead, member = app.test_client(), app.test_client()

    # 1. People sign up
    assert lead.post("/auth/register", json={"name": "Lead User", "email": "lead@example.com", "password": PASSWORD, "role": "Team Lead"}).status_code == 201
    assert member.post("/auth/register", json={"name": "Member User", "email": "member@example.com", "password": PASSWORD, "role": "Member"}).status_code == 201
    member_id = member.get("/api/me").get_json()["id"]

    # 2. The lead creates a project and invites the member
    project = lead.post("/api/projects", json={"name": "Demo Project", "deadline": "2030-12-31"}).get_json()
    pid = project["id"]
    assert lead.post(f"/api/projects/{pid}/members", json={"email": "member@example.com", "role": "Member"}).status_code == 201

    # 3. The member plans work: Project -> Story -> Tasks
    story = member.post(f"/api/projects/{pid}/stories", json={"title": "Sign-in", "priority": "High"}).get_json()
    first = member.post(f"/api/stories/{story['id']}/tasks", json={"title": "Login form", "assigned_to_id": member_id}).get_json()
    second = member.post(f"/api/stories/{story['id']}/tasks", json={"title": "Password reset"}).get_json()

    # 4. Work moves across the board
    assert member.patch(f"/api/tasks/{first['id']}/move", json={"status": "In Progress"}).status_code == 200
    assert member.patch(f"/api/tasks/{first['id']}", json={"status": "Done"}).status_code == 200
    board = lead.get(f"/api/projects/{pid}/board").get_json()
    assert [t["title"] for t in board["columns"]["Done"]] == ["Login form"]
    assert [t["title"] for t in board["columns"]["To Do"]] == ["Password reset"]

    # 5. The lead assigns the other task: an email is queued and delivered in the background
    lead.patch(f"/api/tasks/{second['id']}", json={"assigned_to_id": member_id})
    run_jobs()
    mails = [m for m in app.extensions["mail_backend"].sent if "Password reset" in m.subject]
    assert [m.to for m in mails] == ["member@example.com"]

    # 6. A report is generated asynchronously
    job = member.post("/api/reports").get_json()
    assert job["status"] == "Queued"
    run_jobs()
    finished = member.get(f"/api/jobs/{job['job_id']}").get_json()
    assert finished["status"] == "Completed"
    assert "Demo Project" in finished["result"] and "Overall completion: 50.0%" in finished["result"]

    # 7. The nested view shows the whole hierarchy
    detail = lead.get(f"/api/projects/{pid}").get_json()
    assert (detail["story_count"], detail["task_count"], detail["done_count"]) == (1, 2, 1)
    assert [t["title"] for t in detail["stories"][0]["tasks"]] == ["Login form", "Password reset"]
