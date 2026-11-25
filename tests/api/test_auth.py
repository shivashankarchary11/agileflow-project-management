"""AUTH-01 .. AUTH-06 plus the registration role policy."""

from tests.helpers import PASSWORD, register_actor

VALID = {"name": "Ada Lovelace", "email": "ada@example.com", "password": PASSWORD, "role": "Member"}


def test_auth_01_register_valid_sets_session(client):
    response = client.post("/auth/register", json=VALID)
    assert response.status_code == 201
    assert response.get_json()["role"] == "Member"
    me = client.get("/api/me")
    assert me.status_code == 200
    assert me.get_json()["email"] == "ada@example.com"


def test_auth_02_duplicate_email_conflict(client):
    client.post("/auth/register", json=VALID)
    again = client.post("/auth/register", json={**VALID, "email": "ADA@example.com"})  # case-insensitive
    assert again.status_code == 409


def test_auth_03_invalid_input_is_400(client):
    for bad in (
        {**VALID, "password": "short"},
        {**VALID, "email": "not-an-email"},
        {**VALID, "name": "   "},
        {**VALID, "name": 123},
        {**VALID, "role": "Admin"},
        {**VALID, "name": "x" * 81},
    ):
        response = client.post("/auth/register", json=bad)
        assert response.status_code == 400, bad
        assert "error" in response.get_json()


def test_auth_03b_body_must_be_json_object(client):
    assert client.post("/auth/register", data="not json", content_type="text/plain").status_code == 400
    assert client.post("/auth/register", json=["a", "list"]).status_code == 400


def test_auth_04_login_success_and_identical_failures(app, client):
    register_actor(app, "Ada Lovelace")
    ok = client.post("/auth/login", json={"email": "ada.lovelace@example.com", "password": PASSWORD})
    assert ok.status_code == 200
    wrong = client.post("/auth/login", json={"email": "ada.lovelace@example.com", "password": "wrong-password"})
    unknown = client.post("/auth/login", json={"email": "nobody@example.com", "password": PASSWORD})
    assert wrong.status_code == unknown.status_code == 401
    # same message, so an attacker cannot tell which emails exist
    assert wrong.get_json()["error"] == unknown.get_json()["error"]


def test_auth_05_protected_api_requires_login(client):
    for method, url in (("get", "/api/projects"), ("post", "/api/projects"), ("get", "/api/me"), ("post", "/api/reports")):
        response = getattr(client, method)(url)
        assert response.status_code == 401, url
        assert response.is_json


def test_auth_05b_page_redirects_to_login_when_anonymous(client):
    response = client.get("/")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_auth_06_logout_ends_session(app):
    user = register_actor(app, "Ada Lovelace")
    assert user.get("/api/projects").status_code == 200
    assert user.logout().status_code == 200
    assert user.get("/api/projects").status_code == 401


def test_deleted_user_session_is_rejected(app):
    from agileflow.extensions import db
    from agileflow.models import User

    user = register_actor(app, "Ada Lovelace")
    with app.app_context():
        db.session.delete(db.session.get(User, user.id))
        db.session.commit()
    assert user.get("/api/me").status_code == 401


def test_first_user_becomes_team_lead_when_role_choice_disabled(app_factory):
    app = app_factory(ALLOW_SELF_SELECT_ROLE=False)
    first = register_actor(app, "First Person", "Viewer")  # requested role is ignored
    second = register_actor(app, "Second Person", "Team Lead")  # cannot self-promote
    assert first.get("/api/me").get_json()["role"] == "Team Lead"
    assert second.get("/api/me").get_json()["role"] == "Member"
