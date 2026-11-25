"""EML-01 .. EML-03 and the places where the app decides to send email."""

import logging
import smtplib

import pytest

from agileflow.extensions import db
from agileflow.models import BackgroundJob
from agileflow.workers.email_backends import (
    ConsoleBackend,
    EmailMessage,
    MemoryBackend,
    SmtpBackend,
    build_backend,
)
from tests.helpers import create_story, create_task


def email_jobs(app, to=None):
    with app.app_context():
        jobs = db.session.query(BackgroundJob).filter_by(job_type="send_email").all()
        return [j.payload for j in jobs if to is None or j.payload["to"] == to]


def sent(app):
    return app.extensions["mail_backend"].sent


# ---------- EML-01: when emails are queued ----------

def test_eml_01_assigning_a_task_queues_one_email(app, world, run_jobs):
    run_jobs()  # flush the "added to project" emails first
    before = len(sent(app))
    story = create_story(world.lead, world.pid, "Login")
    create_task(world.lead, story["id"], "Build form", assigned_to_id=world.member.id, due_date="2030-01-02")
    run_jobs()
    new = sent(app)[before:]
    assert len(new) == 1
    assert new[0].to == world.member.email
    assert "Build form" in new[0].subject and "Lead User" in new[0].body and "2030-01-02" in new[0].body


def test_eml_01b_no_email_when_assigning_yourself_or_nobody(app, world, run_jobs):
    run_jobs()
    before = len(sent(app))
    story = create_story(world.lead, world.pid)
    create_task(world.lead, story["id"], "Mine", assigned_to_id=world.lead.id)
    create_task(world.lead, story["id"], "Nobody's")
    run_jobs()
    assert len(sent(app)) == before


def test_eml_01c_reassign_emails_only_when_assignee_changes(app, world, run_jobs):
    story = create_story(world.lead, world.pid)
    task = create_task(world.lead, story["id"], assigned_to_id=world.member.id)
    run_jobs()
    before = len(sent(app))
    world.lead.patch(f"/api/tasks/{task['id']}", {"assigned_to_id": world.member.id, "title": "Renamed"})  # same person
    world.lead.patch(f"/api/tasks/{task['id']}", {"assigned_to_id": None})  # unassign
    run_jobs()
    assert len(sent(app)) == before
    world.lead.patch(f"/api/tasks/{task['id']}", {"assigned_to_id": world.viewer.id})
    run_jobs()
    assert [m.to for m in sent(app)[before:]] == [world.viewer.email]


def test_eml_01d_adding_a_member_emails_them(app, world, make_actor, run_jobs):
    newcomer = make_actor("New Person")
    run_jobs()
    before = len(sent(app))
    world.lead.post(f"/api/projects/{world.pid}/members", {"email": newcomer.email, "role": "Viewer"})
    world.lead.post(f"/api/projects/{world.pid}/members", {"email": newcomer.email, "role": "Member"})  # role change: no 2nd email
    run_jobs()
    new = sent(app)[before:]
    assert len(new) == 1 and new[0].to == newcomer.email and "Viewer" in new[0].body


def test_emails_are_queued_not_sent_inside_the_request(app, world):
    # No job has run, so nothing has been delivered yet, but the jobs are waiting in the queue.
    assert sent(app) == []
    assert {j["to"] for j in email_jobs(app)} == {world.member.email, world.viewer.email}


# ---------- EML-02: delivery failures ----------

@pytest.fixture()
def failing_smtp(monkeypatch):
    class Refusing:
        def __init__(self, *args, **kwargs):
            raise ConnectionRefusedError("mail server is down")

    monkeypatch.setattr(smtplib, "SMTP", Refusing)


def test_eml_02_smtp_failure_retries_then_fails_and_can_be_retried(app_factory, failing_smtp):
    app = app_factory(JOB_BACKOFF_BASE_SECONDS=0, MAIL_BACKEND="smtp", SMTP_HOST="smtp.invalid")
    from agileflow.workers import job_queue

    with app.app_context():
        job = job_queue.enqueue("send_email", {"to": "a@example.com", "subject": "S", "body": "B"})
        assert job_queue.run_pending() == 3
        job = db.session.get(BackgroundJob, job.id)
        assert job.status == "Failed" and job.attempts == 3
        assert "ConnectionRefusedError" in job.error and "mail server is down" in job.error

        # the mail server comes back: swap in a working backend and retry by hand
        app.extensions["mail_backend"] = MemoryBackend()
        job_queue.reset_for_retry(job)
        job_queue.run_pending()
        assert db.session.get(BackgroundJob, job.id).status == "Completed"
        assert len(app.extensions["mail_backend"].sent) == 1


def test_eml_02b_failed_email_is_visible_to_the_person_who_triggered_it(app_factory, failing_smtp, make_actor):
    app = app_factory(JOB_BACKOFF_BASE_SECONDS=0, MAIL_BACKEND="smtp", SMTP_HOST="smtp.invalid")
    from tests.helpers import add_member, create_project, register_actor

    lead = register_actor(app, "Lead User", "Team Lead")
    member = register_actor(app, "Member User")
    project = create_project(lead)
    add_member(lead, project["id"], member)
    with app.app_context():
        from agileflow.workers import job_queue

        job_queue.run_pending()
    jobs = lead.get("/api/jobs").get_json()["items"]
    assert [j["status"] for j in jobs] == ["Failed"]
    assert "ConnectionRefusedError" in jobs[0]["error"]
    assert jobs[0]["summary"].startswith(f"Email to {member.email}")
    assert member.get("/api/jobs").get_json()["items"] == []  # not the recipient's job


# ---------- EML-03: backends ----------

def test_eml_03_memory_backend_captures():
    backend = MemoryBackend()
    message = EmailMessage("a@example.com", "Hello", "Body")
    backend.send(message)
    assert backend.sent == [message]


def test_eml_03_console_backend_logs(caplog):
    with caplog.at_level(logging.INFO):
        ConsoleBackend().send(EmailMessage("a@example.com", "Hello", "Body text"))
    assert "a@example.com" in caplog.text and "Hello" in caplog.text and "Body text" in caplog.text


def test_eml_03_smtp_backend_speaks_smtp(monkeypatch):
    calls = []

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            calls.append(("connect", host, port, timeout))

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def starttls(self, context):
            calls.append(("starttls",))

        def login(self, user, password):
            calls.append(("login", user, password))

        def send_message(self, mime):
            calls.append(("send", mime["To"], mime["Subject"], mime["From"], mime.get_content().strip()))

    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    SmtpBackend(host="mail.example.com", port=587, user="u", password="p", use_tls=True, sender="AgileFlow <a@x.io>", timeout=5).send(
        EmailMessage("to@example.com", "Subj", "Body")
    )
    assert calls == [
        ("connect", "mail.example.com", 587, 5),
        ("starttls",),
        ("login", "u", "p"),
        ("send", "to@example.com", "Subj", "AgileFlow <a@x.io>", "Body"),
    ]


def test_eml_03_smtp_without_host_raises():
    backend = SmtpBackend(host="", port=587, user="", password="", use_tls=True, sender="x", timeout=1)
    with pytest.raises(RuntimeError, match="SMTP_HOST"):
        backend.send(EmailMessage("a@example.com", "S", "B"))


def test_build_backend_selects_by_name_and_rejects_unknown():
    assert isinstance(build_backend({"MAIL_BACKEND": "console"}), ConsoleBackend)
    assert isinstance(build_backend({"MAIL_BACKEND": "MEMORY"}), MemoryBackend)
    with pytest.raises(ValueError, match="Unknown MAIL_BACKEND"):
        build_backend({"MAIL_BACKEND": "pigeon"})
