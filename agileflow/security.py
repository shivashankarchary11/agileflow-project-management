"""Cross-cutting security: CSRF protection, login rate limiting and security headers."""

from __future__ import annotations

import hmac
import secrets
import threading
import time
from collections import defaultdict, deque

from flask import Flask, request, session

from .domain.errors import Forbidden, TooManyRequests

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
PROTECTED_PREFIXES = ("/api/", "/auth/")


# ---------- CSRF ----------

def get_csrf_token() -> str:
    """The per-session CSRF token (created on first use)."""
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


def rotate_csrf_token() -> str:
    session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]


def _check_csrf() -> None:
    from flask import current_app

    if not current_app.config["CSRF_ENABLED"]:
        return
    if request.method not in UNSAFE_METHODS or not request.path.startswith(PROTECTED_PREFIXES):
        return
    sent = request.headers.get("X-CSRF-Token", "")
    expected = session.get("csrf_token", "")
    if not expected or not hmac.compare_digest(sent, expected):
        raise Forbidden("Missing or invalid CSRF token. Reload the page and try again.")


# ---------- rate limiting ----------

class RateLimiter:
    """In-memory sliding window: at most ``limit`` recorded hits per ``window`` seconds per key.

    Good enough for one process. With several workers use a shared store (Redis).
    """

    def __init__(self, window_seconds: float, clock=time.monotonic):
        self.window = window_seconds
        self._clock = clock
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, key: str, now: float) -> deque[float]:
        hits = self._hits[key]
        while hits and now - hits[0] >= self.window:
            hits.popleft()
        if not hits:
            self._hits.pop(key, None)
            return self._hits[key]
        return hits

    def check(self, key: str, limit: int) -> None:
        """Raise ``TooManyRequests`` if ``key`` already used up its ``limit``."""
        with self._lock:
            now = self._clock()
            if len(self._prune(key, now)) >= limit:
                raise TooManyRequests("Too many attempts. Please wait a minute and try again.")

    def record(self, key: str) -> None:
        with self._lock:
            now = self._clock()
            self._prune(key, now).append(now)

    def reset(self, key: str) -> None:
        with self._lock:
            self._hits.pop(key, None)


# ---------- headers ----------

CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    "font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; "
    "form-action 'self'; frame-ancestors 'none'"
)


def _add_headers(response):
    response.headers.setdefault("Content-Security-Policy", CSP)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if request.is_secure:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    if request.path.startswith(PROTECTED_PREFIXES):
        response.headers["Cache-Control"] = "no-store"
    return response


def init_security(app: Flask) -> None:
    app.extensions["rate_limiter"] = RateLimiter(app.config["RATE_LIMIT_WINDOW_SECONDS"])
    app.before_request(_check_csrf)
    app.after_request(_add_headers)
