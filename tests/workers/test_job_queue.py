"""JOB-02 .. JOB-05: queue mechanics, retries, backoff and recovery (no real sleeping)."""

import time
from datetime import timedelta

import pytest

from agileflow.extensions import db
from agileflow.models import BackgroundJob, utcnow
from agileflow.workers import job_queue
from agileflow.workers.handlers import HANDLERS


@pytest.fixture()
def fast_app(app_factory):
    """No waiting between retries."""
    return app_factory(JOB_BACKOFF_BASE_SECONDS=0)


def fresh(job_id):
    db.session.expire_all()
    return db.session.get(BackgroundJob, job_id)


def test_job_02_fails_once_then_succeeds(fast_app, monkeypatch):
    calls = []

    def flaky(job):
        calls.append(job.attempts)
        if len(calls) == 1:
            raise ConnectionError("temporary outage")
        return "done"

    monkeypatch.setitem(HANDLERS, "flaky", flaky)
    with fast_app.app_context():
        job = job_queue.enqueue("flaky")
        assert job_queue.run_pending() == 2  # first attempt + the retry
        job = fresh(job.id)
        assert (job.status, job.attempts, job.result, job.error) == ("Completed", 2, "done", "")
        assert calls == [1, 2]


def test_job_03_always_failing_ends_failed_with_error(fast_app, monkeypatch):
    def broken(job):
        raise RuntimeError("boom")

    monkeypatch.setitem(HANDLERS, "broken", broken)
    with fast_app.app_context():
        job = job_queue.enqueue("broken", max_attempts=3)
        assert job_queue.run_pending() == 3
        job = fresh(job.id)
        assert job.status == "Failed" and job.attempts == 3
        assert job.error == "RuntimeError: boom"
        assert job_queue.run_pending() == 0  # Failed jobs are never picked up again


def test_job_03b_unknown_type_fails_cleanly(fast_app):
    with fast_app.app_context():
        job = job_queue.enqueue("no_such_type", max_attempts=1)
        job_queue.run_pending()
        job = fresh(job.id)
        assert job.status == "Failed" and "No handler registered" in job.error


def test_job_03c_long_errors_are_truncated(fast_app, monkeypatch):
    monkeypatch.setitem(HANDLERS, "loud", lambda job: (_ for _ in ()).throw(RuntimeError("x" * 5000)))
    with fast_app.app_context():
        job = job_queue.enqueue("loud", max_attempts=1)
        job_queue.run_pending()
        assert len(fresh(job.id).error) == job_queue.MAX_ERROR_LENGTH


def test_job_04_backoff_grows_exponentially(app_factory):
    app = app_factory(JOB_BACKOFF_BASE_SECONDS=1)
    boom = RuntimeError("x")
    with app.app_context():
        t0 = utcnow()
        job = job_queue.enqueue("anything", max_attempts=5, run_at=t0)

        claimed = job_queue.claim_next(now=t0)
        assert claimed.id == job.id and claimed.attempts == 1 and claimed.status == "Running"
        job_queue.fail_or_retry(claimed, boom, now=t0)
        first = fresh(job.id).next_run_at
        assert first == t0 + timedelta(seconds=2)  # base * 2**1
        assert job_queue.claim_next(now=t0) is None  # not due yet

        claimed = job_queue.claim_next(now=first)
        assert claimed.attempts == 2
        job_queue.fail_or_retry(claimed, boom, now=first)
        second = fresh(job.id).next_run_at
        assert second == first + timedelta(seconds=4)  # base * 2**2
        assert (second - first) > (first - t0)


def test_job_05_stale_running_jobs_are_requeued(app):
    with app.app_context():
        now = utcnow()
        stuck = job_queue.enqueue("anything", run_at=now - timedelta(hours=1))
        healthy = job_queue.enqueue("anything", run_at=now - timedelta(hours=1))
        job_queue.claim_next(now=now - timedelta(minutes=30))  # a worker took it long ago, then died
        job_queue.claim_next(now=now)  # this one was claimed just now
        assert fresh(stuck.id).status == "Running"
        assert job_queue.recover_stale(now=now, stale_seconds=300) == 1
        assert fresh(stuck.id).status == "Queued" and fresh(stuck.id).locked_at is None
        assert fresh(healthy.id).status == "Running"
        assert job_queue.recover_stale(now=now, stale_seconds=300) == 0


def test_claim_is_exclusive(app):
    with app.app_context():
        job_queue.enqueue("anything")
        first = job_queue.claim_next()
        assert first is not None
        assert job_queue.claim_next() is None  # already Running, cannot be claimed twice


def test_future_jobs_wait_for_their_time(app):
    with app.app_context():
        job_queue.enqueue("anything", run_at=utcnow() + timedelta(hours=1))
        assert job_queue.claim_next() is None


def test_oldest_due_job_goes_first(app):
    with app.app_context():
        a = job_queue.enqueue("anything")
        b = job_queue.enqueue("anything")
        assert job_queue.claim_next().id == a.id
        assert job_queue.claim_next().id == b.id


def test_after_success_hook_failure_does_not_undo_job(fast_app, monkeypatch):
    from agileflow.workers.handlers import AFTER_SUCCESS

    monkeypatch.setitem(HANDLERS, "hooked", lambda job: "ok")
    monkeypatch.setitem(AFTER_SUCCESS, "hooked", lambda job: (_ for _ in ()).throw(RuntimeError("hook broke")))
    with fast_app.app_context():
        job = job_queue.enqueue("hooked")
        job_queue.run_pending()
        assert fresh(job.id).status == "Completed"


def test_reset_for_retry_gives_fresh_budget(fast_app, monkeypatch):
    monkeypatch.setitem(HANDLERS, "broken", lambda job: (_ for _ in ()).throw(RuntimeError("boom")))
    with fast_app.app_context():
        job = job_queue.enqueue("broken", max_attempts=2)
        job_queue.run_pending()
        assert fresh(job.id).status == "Failed"
        job_queue.reset_for_retry(fresh(job.id))
        job = fresh(job.id)
        assert (job.status, job.attempts, job.error) == ("Queued", 0, "")


def test_worker_thread_processes_jobs_end_to_end(app_factory, tmp_path):
    """The real background thread picks up a queued job and finishes it (file DB, like production)."""
    app = app_factory(
        SQLALCHEMY_DATABASE_URI=f"sqlite:///{(tmp_path / 'worker.db').as_posix()}",
        WORKER_POLL_SECONDS=0.05,
    )
    from agileflow.models import User

    with app.app_context():
        db.create_all()
        user = User(name="A", email="a@example.com", password_hash="x", role="Member")
        db.session.add(user)
        db.session.commit()
        job = job_queue.enqueue("send_email", {"to": "a@example.com", "subject": "Hi", "body": "Body"}, user_id=user.id)
        job_id = job.id

    worker = app.extensions["worker"]
    worker.start()
    try:
        status = None
        for _ in range(100):  # up to ~5 seconds
            with app.app_context():
                status = db.session.get(BackgroundJob, job_id).status
                db.session.remove()
            if status == "Completed":
                break
            time.sleep(0.05)
        assert status == "Completed"
    finally:
        worker.stop()
    assert [m.subject for m in app.extensions["mail_backend"].sent] == ["Hi"]
