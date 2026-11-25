"""Application configuration.

Settings come from environment variables (see ``.env.example``) with safe
defaults per environment. ``load_config`` returns a plain dict that
``create_app`` hands to Flask.
"""

from __future__ import annotations

import os
from datetime import timedelta

ENVIRONMENTS = ("development", "testing", "production")
DEV_SECRET_KEY = "dev-only-secret-key-do-not-use-in-production"


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    return int(raw) if raw not in (None, "") else default


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    return float(raw) if raw not in (None, "") else default


def load_config(name: str) -> dict:
    """Build the configuration dict for ``name`` (development/testing/production)."""
    name = (name or "development").lower()
    if name not in ENVIRONMENTS:
        raise ValueError(f"Unknown config '{name}'. Choose one of {ENVIRONMENTS}.")

    testing = name == "testing"
    production = name == "production"

    cfg: dict = {
        "ENV_NAME": name,
        "TESTING": testing,
        "SECRET_KEY": os.environ.get("SECRET_KEY") or ("test-secret-key" if testing else DEV_SECRET_KEY),
        # Database. ``sqlite://`` is an isolated in-memory DB (used by tests).
        # A relative sqlite path is created inside the ``instance/`` folder.
        "SQLALCHEMY_DATABASE_URI": (
            "sqlite://" if testing else os.environ.get("DATABASE_URL", "sqlite:///agileflow.db")
        ),
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        "SQLALCHEMY_ENGINE_OPTIONS": {"connect_args": {"timeout": 15}},
        # Sessions / cookies
        "SESSION_COOKIE_HTTPONLY": True,
        "SESSION_COOKIE_SAMESITE": "Lax",
        "SESSION_COOKIE_SECURE": _env_bool("COOKIE_SECURE", production),
        "PERMANENT_SESSION_LIFETIME": timedelta(hours=_env_int("SESSION_HOURS", 8)),
        "LOG_LEVEL": os.environ.get("LOG_LEVEL", "INFO"),
        # Security switches (tests turn most of them off unless a test needs them)
        # scrypt in real use; a cheap method in tests so the suite stays fast (never used outside tests).
        "PASSWORD_HASH_METHOD": "pbkdf2:sha256:1000" if testing else "scrypt",
        "ALLOW_SELF_SELECT_ROLE": _env_bool("ALLOW_SELF_SELECT_ROLE", not production),
        "CSRF_ENABLED": _env_bool("CSRF_ENABLED", not testing),
        "RATE_LIMIT_ENABLED": _env_bool("RATE_LIMIT_ENABLED", not testing),
        "LOGIN_RATE_LIMIT": _env_int("LOGIN_RATE_LIMIT", 5),
        "REGISTER_RATE_LIMIT": _env_int("REGISTER_RATE_LIMIT", 10),
        "RATE_LIMIT_WINDOW_SECONDS": _env_int("RATE_LIMIT_WINDOW_SECONDS", 60),
        # Background jobs
        "WORKER_ENABLED": _env_bool("WORKER_ENABLED", not testing),
        "WORKER_POLL_SECONDS": _env_float("WORKER_POLL_SECONDS", 1.0),
        "JOB_MAX_ATTEMPTS": _env_int("JOB_MAX_ATTEMPTS", 3),
        "JOB_BACKOFF_BASE_SECONDS": _env_float("JOB_BACKOFF_BASE_SECONDS", 2.0),
        "JOB_STALE_SECONDS": _env_int("JOB_STALE_SECONDS", 300),
        # Test-only hook that lets a job fail on purpose (never enabled outside tests).
        "JOB_FAIL_HOOK": testing,
        # Email
        "MAIL_BACKEND": "memory" if testing else os.environ.get("MAIL_BACKEND", "console"),
        "MAIL_FROM": os.environ.get("MAIL_FROM", "AgileFlow <no-reply@agileflow.local>"),
        "SMTP_HOST": os.environ.get("SMTP_HOST", ""),
        "SMTP_PORT": _env_int("SMTP_PORT", 587),
        "SMTP_USER": os.environ.get("SMTP_USER", ""),
        "SMTP_PASSWORD": os.environ.get("SMTP_PASSWORD", ""),
        "SMTP_USE_TLS": _env_bool("SMTP_USE_TLS", True),
        "SMTP_TIMEOUT_SECONDS": _env_int("SMTP_TIMEOUT_SECONDS", 10),
    }

    if production:
        key = cfg["SECRET_KEY"]
        if key == DEV_SECRET_KEY or len(key) < 16:
            raise RuntimeError(
                "SECRET_KEY must be set to a random value of at least 16 characters in production."
            )
    return cfg
