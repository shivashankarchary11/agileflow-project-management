"""E2E-01 (server side): the pages render, assets load, and the UI is CSP-clean.

A real-browser test (drag a card, see a toast) is described in docs/TESTING.md as a manual
script; these tests check everything that can be verified without a browser.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.helpers import register_actor

WEB = Path(__file__).resolve().parents[2] / "agileflow" / "web"
JS = sorted((WEB / "static" / "js").glob("*.js"))


def test_login_and_register_pages_render(client):
    login = client.get("/login")
    assert login.status_code == 200
    html = login.get_data(as_text=True)
    assert 'data-mode="login"' in html and 'name="email"' in html and 'name="name"' not in html
    register = client.get("/register").get_data(as_text=True)
    assert 'data-mode="register"' in register and 'name="name"' in register and 'name="role"' in register


def test_register_page_hides_role_choice_when_disabled(app_factory):
    page = app_factory(ALLOW_SELF_SELECT_ROLE=False).test_client().get("/register").get_data(as_text=True)
    assert 'name="role"' not in page and "first account becomes Team Lead" in page


def test_dashboard_requires_login_then_renders_shell(app):
    assert app.test_client().get("/").status_code == 302
    lead = register_actor(app, "Lead User", "Team Lead")
    page = lead.get("/")
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert 'id="main"' in html and 'id="toasts"' in html and 'id="formDialog"' in html
    assert f'data-user-id="{lead.id}"' in html and 'data-role="Team Lead"' in html
    assert 'name="csrf-token"' in html
    assert lead.get("/login").status_code == 302  # already signed in


def test_user_name_is_escaped_in_the_page(app):
    hacker = register_actor(app, "<script>alert(1)</script>")
    html = hacker.get("/").get_data(as_text=True)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_static_assets_are_served(client):
    with client.get("/static/css/app.css") as response:  # `with` closes the streamed file
        assert response.status_code == 200
    for path in JS:
        with client.get(f"/static/js/{path.name}") as response:
            assert response.status_code == 200, path.name
            assert "javascript" in response.mimetype


def test_templates_have_no_inline_script_or_style(app):
    """The CSP forbids inline code; templates must only reference external files."""
    for template in (WEB / "templates").glob("*.html"):
        text = template.read_text(encoding="utf-8")
        assert not re.search(r"<script(?![^>]*\bsrc=)[^>]*>", text), f"inline <script> in {template.name}"
        assert " style=" not in text, f"inline style attribute in {template.name}"
        assert not re.search(r"\son[a-z]+=", text), f"inline event handler in {template.name}"
        assert "fonts.googleapis" not in text


def test_javascript_never_assigns_html_strings():
    """All DOM is built with text nodes, so user data cannot become markup."""
    for path in JS:
        code = path.read_text(encoding="utf-8")
        for forbidden in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval(", "new Function"):
            assert forbidden not in code, f"{forbidden} found in {path.name}"


def test_every_js_import_resolves():
    names = {p.name for p in JS}
    for path in JS:
        for target in re.findall(r'from "\./([\w-]+\.js)"', path.read_text(encoding="utf-8")):
            assert target in names, f"{path.name} imports missing module {target}"


def test_css_has_no_external_requests():
    css = (WEB / "static" / "css" / "app.css").read_text(encoding="utf-8")
    assert "http://" not in css and "https://" not in css and "@import" not in css


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js not installed")
@pytest.mark.parametrize("path", JS, ids=lambda p: p.name)
def test_javascript_syntax_is_valid(path):
    result = subprocess.run(["node", "--check", str(path)], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
