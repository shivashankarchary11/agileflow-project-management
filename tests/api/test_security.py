"""SEC-01 .. SEC-04: CSRF, rate limiting, headers, error shape."""

from tests.helpers import PASSWORD, register_actor

CREDS = {"name": "Ada", "email": "ada@example.com", "password": PASSWORD, "role": "Member"}


def csrf_client(app):
    return app.test_client()


# ---------- CSRF ----------

def test_sec_01_state_changing_request_without_token_is_403(app_factory):
    app = app_factory(CSRF_ENABLED=True)
    client = csrf_client(app)
    response = client.post("/auth/register", json=CREDS)
    assert response.status_code == 403
    assert "CSRF" in response.get_json()["error"]


def test_sec_01b_wrong_token_is_403_and_right_token_works(app_factory):
    app = app_factory(CSRF_ENABLED=True)
    client = csrf_client(app)
    token = client.get("/api/csrf-token").get_json()["csrf_token"]
    assert client.post("/auth/register", json=CREDS, headers={"X-CSRF-Token": "forged"}).status_code == 403
    ok = client.post("/auth/register", json=CREDS, headers={"X-CSRF-Token": token})
    assert ok.status_code == 201
    # the token rotates on login, and the response hands over the new one
    new_token = ok.get_json()["csrf_token"]
    assert new_token != token
    assert client.post("/api/reports", json={}, headers={"X-CSRF-Token": token}).status_code == 403  # old token
    assert client.post("/api/reports", json={}, headers={"X-CSRF-Token": new_token}).status_code == 202


def test_sec_01c_safe_methods_do_not_need_a_token(app_factory):
    app = app_factory(CSRF_ENABLED=True)
    client = csrf_client(app)
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/projects").status_code == 401  # reaches the auth check, not blocked by CSRF


def test_sec_01d_pages_embed_a_token_the_ui_can_use(app_factory):
    app = app_factory(CSRF_ENABLED=True)
    client = csrf_client(app)
    page = client.get("/login").get_data(as_text=True)
    token = page.split('name="csrf-token" content="')[1].split('"')[0]
    assert len(token) >= 32
    assert client.post("/auth/register", json=CREDS, headers={"X-CSRF-Token": token}).status_code == 201


# ---------- rate limiting ----------

def test_sec_02_sixth_failed_login_is_throttled(app_factory):
    app = app_factory(RATE_LIMIT_ENABLED=True)
    register_actor(app, "Ada Lovelace")
    client = app.test_client()
    bad = {"email": "ada.lovelace@example.com", "password": "wrong-password"}
    assert [client.post("/auth/login", json=bad).status_code for _ in range(5)] == [401] * 5
    throttled = client.post("/auth/login", json=bad)
    assert throttled.status_code == 429 and throttled.get_json()["code"] == "too_many_requests"
    # even the right password is refused while locked out
    good = {"email": "ada.lovelace@example.com", "password": PASSWORD}
    assert client.post("/auth/login", json=good).status_code == 429


def test_sec_02b_limit_is_per_account_and_success_resets(app_factory):
    app = app_factory(RATE_LIMIT_ENABLED=True)
    register_actor(app, "Ada Lovelace")
    register_actor(app, "Bob Builder")
    client = app.test_client()
    ada_bad = {"email": "ada.lovelace@example.com", "password": "wrong-password"}
    for _ in range(4):
        client.post("/auth/login", json=ada_bad)
    # a different account is unaffected
    assert client.post("/auth/login", json={"email": "bob.builder@example.com", "password": "wrong-password"}).status_code == 401
    # a correct login clears Ada's failures
    assert client.post("/auth/login", json={"email": "ada.lovelace@example.com", "password": PASSWORD}).status_code == 200
    assert [client.post("/auth/login", json=ada_bad).status_code for _ in range(5)] == [401] * 5


def test_sec_02c_registration_is_rate_limited_too(app_factory):
    app = app_factory(RATE_LIMIT_ENABLED=True, REGISTER_RATE_LIMIT=3)
    client = app.test_client()
    codes = [client.post("/auth/register", json={**CREDS, "email": f"u{i}@example.com"}).status_code for i in range(5)]
    assert codes == [201, 201, 201, 429, 429]


def test_rate_limiting_is_off_by_default_in_tests(app):
    client = app.test_client()
    bad = {"email": "x@example.com", "password": "wrong-password"}
    assert {client.post("/auth/login", json=bad).status_code for _ in range(8)} == {401}


# ---------- headers ----------

def test_sec_04_security_headers_on_pages_and_api(client):
    for url in ("/login", "/api/health", "/api/projects"):
        headers = client.get(url).headers
        csp = headers["Content-Security-Policy"]
        assert "default-src 'self'" in csp and "script-src 'self'" in csp and "frame-ancestors 'none'" in csp
        assert "'unsafe-inline'" not in csp and "'unsafe-eval'" not in csp
        assert headers["X-Content-Type-Options"] == "nosniff"
        assert headers["X-Frame-Options"] == "DENY"
        assert headers["Referrer-Policy"] == "same-origin"
    assert client.get("/api/health").headers["Cache-Control"] == "no-store"


def test_hsts_only_on_https(client):
    assert "Strict-Transport-Security" not in client.get("/api/health").headers
    secure = client.get("/api/health", base_url="https://localhost")
    assert "max-age" in secure.headers["Strict-Transport-Security"]


def test_session_cookie_flags(client):
    cookie = client.post("/auth/register", json=CREDS).headers["Set-Cookie"]
    assert "HttpOnly" in cookie and "SameSite=Lax" in cookie


# ---------- error shape ----------

def test_unknown_api_route_returns_json_404(client):
    response = client.get("/api/does-not-exist")
    assert response.status_code == 404 and response.is_json and "error" in response.get_json()


def test_wrong_method_returns_json_405(client):
    response = client.delete("/api/health")
    assert response.status_code == 405 and response.is_json


def test_unexpected_errors_are_json_500_without_details(app, client, monkeypatch):
    from agileflow.services import project_service

    def explode(*args, **kwargs):
        raise RuntimeError("secret internal detail")

    monkeypatch.setattr(project_service, "list_projects", explode)
    register_actor(app, "Ada Lovelace")
    ada = app.test_client()
    ada.post("/auth/login", json={"email": "ada.lovelace@example.com", "password": PASSWORD})
    response = ada.get("/api/projects")
    assert response.status_code == 500
    assert response.get_json() == {"error": "Internal server error.", "code": "internal_error"}
    assert "secret" not in response.get_data(as_text=True)


def test_sec_03_hostile_strings_roundtrip_as_data(world):
    hostile = "<img src=x onerror=alert(1)>"
    story = world.lead.post(f"/api/projects/{world.pid}/stories", {"title": hostile, "description": hostile}).get_json()
    task = world.lead.post(f"/api/stories/{story['id']}/tasks", {"title": hostile}).get_json()
    assert task["title"] == hostile and task["story_title"] == hostile  # stored as text, never interpreted
    # and a hostile *date* is refused outright (this was the stored-XSS hole in the old UI)
    assert world.lead.patch(f"/api/projects/{world.pid}", {"deadline": hostile}).status_code == 400
