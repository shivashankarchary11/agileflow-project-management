import time
import pytest
from app import app, db


_test_database_configured = False


@pytest.fixture()
def client(tmp_path_factory):
    global _test_database_configured
    if not _test_database_configured:
        db_path = tmp_path_factory.getbasetemp() / "test_agileflow.db"
        app.config.update(
            TESTING=True,
            SECRET_KEY="test-secret-key",
            SQLALCHEMY_DATABASE_URI=f"sqlite:///{db_path.as_posix()}",
        )
        _test_database_configured = True
    with app.app_context():
        db.session.remove()
        db.drop_all()
        db.create_all()
    with app.test_client() as test_client:
        yield test_client
    with app.app_context():
        db.session.remove()


def register(client, name, email, role="Member"):
    return client.post("/auth/register", json={
        "name": name, "email": email, "password": "password-123", "role": role
    })


def test_project_story_task_roles_and_report(client):
    # The user explicitly chooses the Team Lead role during registration.
    response = register(client, "Lead User", "lead@example.com", "Team Lead")
    assert response.status_code == 201
    assert response.get_json()["role"] == "Team Lead"

    created = client.post("/api/projects", json={"name": "Demo Project"})
    assert created.status_code == 201
    project_id = created.get_json()["id"]

    client.post("/auth/logout")
    member_register = register(client, "Member User", "member@example.com")
    assert member_register.status_code == 201
    client.post("/auth/logout")

    # Sign back in as lead and add the registered member.
    login = client.post("/auth/login", json={"email": "lead@example.com", "password": "password-123"})
    assert login.status_code == 200
    added = client.post(f"/api/projects/{project_id}/members", json={"email": "member@example.com", "role": "Member"})
    assert added.status_code == 201

    client.post("/auth/logout")
    client.post("/auth/login", json={"email": "member@example.com", "password": "password-123"})
    story = client.post(f"/api/projects/{project_id}/stories", json={"title": "Build sign-in"})
    assert story.status_code == 201
    story_id = story.get_json()["id"]
    task = client.post(f"/api/stories/{story_id}/tasks", json={"title": "Create login form", "assigned_to_id": 2})
    assert task.status_code == 201
    assert task.get_json()["assigned_to"] == "Member User"

    # Member can generate a report, but only for projects they can access.
    job_response = client.post("/api/reports")
    assert job_response.status_code == 202
    job_id = job_response.get_json()["job_id"]
    for _ in range(30):
        job = client.get(f"/api/jobs/{job_id}").get_json()
        if job["status"] in ("Completed", "Failed"):
            break
        time.sleep(0.1)
    assert job["status"] == "Completed"
    assert "Demo Project" in job["result"]


def test_viewer_cannot_create_story(client):
    register(client, "Lead User", "lead@example.com", "Team Lead")
    project = client.post("/api/projects", json={"name": "Read Only"}).get_json()
    client.post("/auth/logout")
    register(client, "Viewer User", "viewer@example.com", "Viewer")
    client.post("/auth/logout")
    client.post("/auth/login", json={"email": "lead@example.com", "password": "password-123"})
    client.post(f"/api/projects/{project['id']}/members", json={"email": "viewer@example.com", "role": "Viewer"})
    client.post("/auth/logout")
    client.post("/auth/login", json={"email": "viewer@example.com", "password": "password-123"})
    denied = client.post(f"/api/projects/{project['id']}/stories", json={"title": "Should be blocked"})
    assert denied.status_code == 403
