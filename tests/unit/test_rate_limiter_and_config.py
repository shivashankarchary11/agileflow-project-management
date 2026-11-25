import pytest

from agileflow.config import DEV_SECRET_KEY, load_config
from agileflow.domain.errors import TooManyRequests
from agileflow.security import RateLimiter
from agileflow.services.ordering import place, resequence


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def test_rate_limiter_sliding_window():
    clock = Clock()
    limiter = RateLimiter(60, clock=clock)
    for _ in range(3):
        limiter.check("k", 3)
        limiter.record("k")
    with pytest.raises(TooManyRequests):
        limiter.check("k", 3)
    limiter.check("other", 3)  # keys are independent
    clock.now += 59
    with pytest.raises(TooManyRequests):
        limiter.check("k", 3)
    clock.now += 2  # the window has passed
    limiter.check("k", 3)


def test_rate_limiter_reset_and_partial_expiry():
    clock = Clock()
    limiter = RateLimiter(10, clock=clock)
    limiter.record("k")
    clock.now += 6
    limiter.record("k")
    clock.now += 5  # first hit expired, second still counts
    limiter.check("k", 2)
    limiter.record("k")
    with pytest.raises(TooManyRequests):
        limiter.check("k", 2)
    limiter.reset("k")
    limiter.check("k", 2)


# ---------- config ----------

def test_testing_config_is_isolated_and_quiet():
    cfg = load_config("testing")
    assert cfg["SQLALCHEMY_DATABASE_URI"] == "sqlite://"
    assert cfg["WORKER_ENABLED"] is False and cfg["MAIL_BACKEND"] == "memory" and cfg["JOB_FAIL_HOOK"] is True


def test_development_defaults(monkeypatch):
    for name in ("SECRET_KEY", "DATABASE_URL", "COOKIE_SECURE", "MAIL_BACKEND"):
        monkeypatch.delenv(name, raising=False)
    cfg = load_config("development")
    assert cfg["SQLALCHEMY_DATABASE_URI"] == "sqlite:///agileflow.db"
    assert cfg["MAIL_BACKEND"] == "console" and cfg["CSRF_ENABLED"] is True and cfg["JOB_FAIL_HOOK"] is False
    assert cfg["ALLOW_SELF_SELECT_ROLE"] is True


def test_production_requires_a_real_secret(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        load_config("production")
    monkeypatch.setenv("SECRET_KEY", DEV_SECRET_KEY)
    with pytest.raises(RuntimeError):
        load_config("production")
    monkeypatch.setenv("SECRET_KEY", "short")
    with pytest.raises(RuntimeError):
        load_config("production")
    monkeypatch.setenv("SECRET_KEY", "a-long-random-production-secret")
    cfg = load_config("production")
    assert cfg["SESSION_COOKIE_SECURE"] is True and cfg["ALLOW_SELF_SELECT_ROLE"] is False


def test_env_overrides_and_unknown_environment(monkeypatch):
    monkeypatch.setenv("LOGIN_RATE_LIMIT", "9")
    monkeypatch.setenv("COOKIE_SECURE", "0")
    monkeypatch.setenv("SECRET_KEY", "a-long-random-production-secret")
    cfg = load_config("production")
    assert cfg["LOGIN_RATE_LIMIT"] == 9 and cfg["SESSION_COOKIE_SECURE"] is False
    with pytest.raises(ValueError):
        load_config("staging")


# ---------- ordering ----------

class Item:
    def __init__(self, id_, position=0):
        self.id, self.position = id_, position


def order(items):
    return [i.id for i in sorted(items, key=lambda i: i.position)]


def test_resequence_closes_gaps():
    items = [Item(1, 5), Item(2, 9), Item(3, 20)]
    resequence(items)
    assert [i.position for i in items] == [0, 1, 2]


def test_place_moves_clamps_and_appends():
    by_id = {n: Item(n) for n in (1, 2, 3, 4)}
    items = list(by_id.values())
    resequence(items)

    def siblings():  # like the repository: sorted by position
        return sorted(items, key=lambda i: i.position)

    place(siblings(), by_id[4], 0)
    assert order(items) == [4, 1, 2, 3]
    place(siblings(), by_id[1], 99)  # clamped to the end
    assert order(items) == [4, 2, 3, 1]
    place(siblings(), by_id[2], None)  # None = last
    assert order(items) == [4, 3, 1, 2]
    place(siblings(), by_id[3], -5)  # clamped to the start
    assert order(items) == [3, 4, 1, 2]
    assert sorted(i.position for i in items) == [0, 1, 2, 3]  # always a clean 0..n-1
