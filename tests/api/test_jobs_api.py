"""JOB-01, JOB-06, JOB-07 through the HTTP API, plus the report content."""

from agileflow.extensions import db
from agileflow.models import BackgroundJob
from tests.helpers import create_story, create_task


def start_report(actor, **body):
    response = actor.post("/api/reports", body or None)
    assert response.status_code == 202, response.get_json()
    return response.get_json()


def test_job_01_report_goes_queued_to_completed(world, run_jobs):
    story = create_story(world.lead, world.pid, "Story A")
    create_task(world.lead, story["id"], "Done task", status="Done")
    create_task(world.lead, story["id"], "Open task", due_date="2000-01-01")  # overdue
    started = start_report(world.member)
    assert started["status"] == "Queued" and started["job_id"] == started["id"]
    assert world.member.get(f"/api/jobs/{started['id']}").get_json()["status"] == "Queued"

    run_jobs()
    job = world.member.get(f"/api/jobs/{started['id']}").get_json()
    assert job["status"] == "Completed" and job["attempts"] == 1 and job["error"] == ""
    report = job["result"]
    assert "AGILE TEAM PROGRESS REPORT" in report
    assert "Demo Project" in report and "Projects: 1" in report
    assert "User stories: 1" in report and "Tasks: 2  (done: 1)" in report
    assert "Overall completion: 50.0%" in report
    assert "Overdue: 1" in report


def test_job_01b_report_only_covers_your_projects(world, run_jobs):
    start = start_report(world.outsider)
    run_jobs()
    result = world.outsider.get(f"/api/jobs/{start['id']}").get_json()["result"]
    assert "Projects: 0" in result and "Demo Project" not in result


def test_job_01c_completed_report_queues_a_ready_email(app, world, run_jobs):
    run_jobs()
    before = len(app.extensions["mail_backend"].sent)
    start_report(world.member)
    run_jobs()
    new = app.extensions["mail_backend"].sent[before:]
    assert [m.to for m in new] == [world.member.email]
    assert "report is ready" in new[0].subject.lower()


def test_job_02_report_fails_once_then_succeeds(app_factory, run_jobs):
    app = app_factory(JOB_BACKOFF_BASE_SECONDS=0)
    from agileflow.workers import job_queue
    from tests.helpers import register_actor

    user = register_actor(app, "Ada Lovelace")
    job = start_report(user, fail_n_times=1)
    with app.app_context():
        job_queue.run_pending()
    body = user.get(f"/api/jobs/{job['id']}").get_json()
    assert body["status"] == "Completed" and body["attempts"] == 2


def test_job_03_report_that_always_fails(app_factory):
    app = app_factory(JOB_BACKOFF_BASE_SECONDS=0)
    from agileflow.workers import job_queue
    from tests.helpers import register_actor

    user = register_actor(app, "Ada Lovelace")
    job = start_report(user, fail_n_times=99)
    with app.app_context():
        job_queue.run_pending()
    body = user.get(f"/api/jobs/{job['id']}").get_json()
    assert body["status"] == "Failed" and body["attempts"] == body["max_attempts"] == 3
    assert "Injected failure" in body["error"]


def test_fail_hook_is_ignored_when_disabled(app_factory):
    app = app_factory(JOB_FAIL_HOOK=False)
    from agileflow.workers import job_queue
    from tests.helpers import register_actor

    user = register_actor(app, "Ada Lovelace")
    job = start_report(user, fail_n_times=99)
    with app.app_context():
        job_queue.run_pending()
    assert user.get(f"/api/jobs/{job['id']}").get_json()["status"] == "Completed"


def test_job_06_other_users_jobs_are_hidden(world, run_jobs):
    mine = start_report(world.member)
    assert world.lead.get(f"/api/jobs/{mine['id']}").status_code == 404
    assert world.lead.post(f"/api/jobs/{mine['id']}/retry").status_code == 404
    assert world.lead.get("/api/jobs/99999").status_code == 404
    assert [j["id"] for j in world.member.get("/api/jobs").get_json()["items"]] == [mine["id"]]


def test_job_06b_job_list_omits_result_text(world, run_jobs):
    start_report(world.member)
    run_jobs()
    item = world.member.get("/api/jobs").get_json()["items"][0]
    assert item["has_result"] is True and "result" not in item


def test_job_07_retry_failed_job(app_factory):
    app = app_factory(JOB_BACKOFF_BASE_SECONDS=0)
    from agileflow.workers import job_queue
    from tests.helpers import register_actor

    user = register_actor(app, "Ada Lovelace")
    job = start_report(user, fail_n_times=99)
    with app.app_context():
        job_queue.run_pending()
    assert user.post(f"/api/jobs/{job['id']}/retry").status_code == 202
    queued = user.get(f"/api/jobs/{job['id']}").get_json()
    assert queued["status"] == "Queued" and queued["attempts"] == 0 and queued["error"] == ""

    with app.app_context():  # the underlying problem is fixed
        db.session.get(BackgroundJob, job["id"]).payload = {}
        db.session.commit()
        job_queue.run_pending()
    assert user.get(f"/api/jobs/{job['id']}").get_json()["status"] == "Completed"


def test_job_07b_only_failed_jobs_can_be_retried(world, run_jobs):
    job = start_report(world.member)
    assert world.member.post(f"/api/jobs/{job['id']}/retry").status_code == 409  # Queued
    run_jobs()
    assert world.member.post(f"/api/jobs/{job['id']}/retry").status_code == 409  # Completed


def test_report_requires_login_and_valid_hook_value(client, world):
    assert client.post("/api/reports").status_code == 401
    assert world.member.post("/api/reports", {"fail_n_times": "many"}).status_code == 400
