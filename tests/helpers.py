"""Small helpers that make the tests read like the user stories they check."""

from __future__ import annotations

PASSWORD = "password-123"


class Actor:
    """A person with their own browser session (their own Flask test client)."""

    def __init__(self, client, name: str, email: str, role: str):
        self.client, self.name, self.email, self.role = client, name, email, role
        self.id: int | None = None

    # thin wrappers so tests stay short
    def get(self, url, **kwargs):
        return self.client.get(url, **kwargs)

    def post(self, url, json=None, **kwargs):
        return self.client.post(url, json={} if json is None else json, **kwargs)

    def patch(self, url, json=None, **kwargs):
        return self.client.patch(url, json={} if json is None else json, **kwargs)

    def delete(self, url, **kwargs):
        return self.client.delete(url, **kwargs)

    def login(self, password: str = PASSWORD):
        return self.post("/auth/login", {"email": self.email, "password": password})

    def logout(self):
        return self.post("/auth/logout")


def register_actor(app, name: str, role: str = "Member") -> Actor:
    email = f"{name.lower().replace(' ', '.')}@example.com"
    actor = Actor(app.test_client(), name, email, role)
    response = actor.post("/auth/register", {"name": name, "email": email, "password": PASSWORD, "role": role})
    assert response.status_code == 201, response.get_json()
    actor.id = actor.get("/api/me").get_json()["id"]
    return actor


def create_project(lead: Actor, name: str = "Demo Project", **extra) -> dict:
    response = lead.post("/api/projects", {"name": name, **extra})
    assert response.status_code == 201, response.get_json()
    return response.get_json()


def add_member(lead: Actor, project_id: int, person: Actor, role: str = "Member") -> dict:
    response = lead.post(f"/api/projects/{project_id}/members", {"email": person.email, "role": role})
    assert response.status_code in (200, 201), response.get_json()
    return response.get_json()


def create_story(actor: Actor, project_id: int, title: str = "A story", **extra) -> dict:
    response = actor.post(f"/api/projects/{project_id}/stories", {"title": title, **extra})
    assert response.status_code == 201, response.get_json()
    return response.get_json()


def create_task(actor: Actor, story_id: int, title: str = "A task", **extra) -> dict:
    response = actor.post(f"/api/stories/{story_id}/tasks", {"title": title, **extra})
    assert response.status_code == 201, response.get_json()
    return response.get_json()
