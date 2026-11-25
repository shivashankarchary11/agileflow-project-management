"""Pluggable email delivery, selected with ``MAIL_BACKEND``.

* ``console`` (default): writes the email to the application log. No setup needed.
* ``smtp``: sends through a real SMTP server (``SMTP_HOST`` etc.).
* ``memory``: keeps messages in a list. Used by the tests.
"""

from __future__ import annotations

import logging
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage as MimeMessage
from typing import Protocol

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EmailMessage:
    to: str
    subject: str
    body: str


class EmailBackend(Protocol):
    def send(self, message: EmailMessage) -> None: ...


class ConsoleBackend:
    def send(self, message: EmailMessage) -> None:
        logger.info("EMAIL (console backend)\n  To: %s\n  Subject: %s\n  %s", message.to, message.subject, message.body)


class MemoryBackend:
    def __init__(self) -> None:
        self.sent: list[EmailMessage] = []

    def send(self, message: EmailMessage) -> None:
        self.sent.append(message)


class SmtpBackend:
    def __init__(self, *, host: str, port: int, user: str, password: str, use_tls: bool, sender: str, timeout: int):
        self.host, self.port, self.user, self.password = host, port, user, password
        self.use_tls, self.sender, self.timeout = use_tls, sender, timeout

    def send(self, message: EmailMessage) -> None:
        if not self.host:
            raise RuntimeError("SMTP_HOST is not configured")
        mime = MimeMessage()
        mime["From"] = self.sender
        mime["To"] = message.to
        mime["Subject"] = message.subject
        mime.set_content(message.body)
        with smtplib.SMTP(self.host, self.port, timeout=self.timeout) as server:
            if self.use_tls:
                server.starttls(context=ssl.create_default_context())
            if self.user:
                server.login(self.user, self.password)
            server.send_message(mime)


def build_backend(config) -> EmailBackend:
    name = (config.get("MAIL_BACKEND") or "console").lower()
    if name == "console":
        return ConsoleBackend()
    if name == "memory":
        return MemoryBackend()
    if name == "smtp":
        return SmtpBackend(
            host=config["SMTP_HOST"],
            port=config["SMTP_PORT"],
            user=config["SMTP_USER"],
            password=config["SMTP_PASSWORD"],
            use_tls=config["SMTP_USE_TLS"],
            sender=config["MAIL_FROM"],
            timeout=config["SMTP_TIMEOUT_SECONDS"],
        )
    raise ValueError(f"Unknown MAIL_BACKEND '{name}'. Use console, smtp or memory.")
