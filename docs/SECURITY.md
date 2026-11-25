# Security considerations

What is protected, how, where it is tested, and what is *not* covered. Mapped to the OWASP Top 10 (2021).

| OWASP | Risk | What AgileFlow does | Tested in |
|---|---|---|---|
| A01 Broken access control | Reading or changing other people's work | Every route loads the record **and** checks the caller's role in that project (`services/access.py`, `domain/policy.py`). Non-members get `404`, so IDs cannot be probed. Roles are read from the database on each request, never cached in the cookie. A task can only be assigned to someone in the project, and can only be moved within its project. Jobs are visible only to their owner. | `test_prj_05*`, `test_task_permissions`, `test_job_06`, `test_org_02`, `tests/unit/test_policy.py` |
| A02 Cryptographic failures | Passwords, sessions | Passwords hashed with Werkzeug **scrypt** (never stored or returned). Session is a signed cookie: `HttpOnly`, `SameSite=Lax`, `Secure` by default in production, 8 h lifetime. `SECRET_KEY` is **required** (>= 16 chars, not the dev default) when `APP_ENV=production`; the app refuses to start without it. HSTS is sent over HTTPS. | `test_production_requires_a_real_secret`, `test_session_cookie_flags`, `test_hsts_only_on_https` |
| A03 Injection | SQL injection, XSS | All database access uses SQLAlchemy bound parameters. `LIKE` wildcards in search are escaped. Every input is type/length/enum/date validated before use (`api/schemas.py`). The UI builds the DOM with text nodes only (no `innerHTML`), and a strict CSP forbids inline script. The old stored-XSS via `deadline` is closed twice: dates are strict `YYYY-MM-DD`, and output is always escaped. | `test_prj_03*`, `test_tsk_03`, `test_sec_03`, `test_javascript_never_assigns_html_strings`, browser test (hostile project name renders as text) |
| A04 Insecure design | Abuse of the role model | Production policy: first account is Team Lead, everyone else Member (`ALLOW_SELF_SELECT_ROLE=0`). Open role choice exists only as a demo switch (on in development). | `test_first_user_becomes_team_lead_when_role_choice_disabled` |
| A05 Security misconfiguration | Debug mode, headers | Debug is off unless `FLASK_DEBUG=1`. Headers on every response: `Content-Security-Policy` (`default-src 'self'`, no inline script/style, `frame-ancestors 'none'`), `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy`; API responses are `Cache-Control: no-store`. No third-party fonts or scripts. The container runs as a non-root user. Errors never leak internals (`500` is a generic JSON body). | `test_sec_04*`, `test_unexpected_errors_are_json_500_without_details`, `test_css_has_no_external_requests` |
| A06 Vulnerable components | Old dependencies | Everything is pinned in `requirements.txt`. SQLAlchemy is held at 2.0.x because 2.1.x fails to import on Python 3.14.7. | CI installs the pins |
| A07 Authentication failures | Brute force, enumeration | Login is throttled: 5 failed attempts per minute per address+email, then `429` (even for the right password). Registration is throttled (10/min per address). Unknown email and wrong password give the **same** message, and a dummy hash is checked for unknown emails so response time does not reveal which emails exist. Passwords must be 8-128 characters. | `test_sec_02*`, `test_auth_04` |
| A08 Integrity failures | Cross-site request forgery | Every `POST`/`PATCH`/`DELETE` needs a per-session `X-CSRF-Token` (compared in constant time). The token rotates at login. `SameSite=Lax` is a second layer. | `test_sec_01*` |
| A09 Logging failures | No trace of failures | Failed jobs, retries and unexpected exceptions are logged with context; the last error of each job is stored and shown to its owner. | live smoke test checks the retry log lines |
| A10 SSRF | Server-side requests | The server makes no requests to user-supplied URLs. The only outbound connection is SMTP to the configured host. | n/a |

## Known limitations (be honest about these)

- **Rate limiting is in memory**, per process. With several server processes use a shared store (Redis).
- **Registration reveals whether an email exists** (`409`), as most sign-up forms do; it is throttled. Adding a teammate reveals the same to a Team Lead.
- **Email invitations are not verified**: anyone can register with any address. Production should verify email ownership.
- **No password reset, no account lockout notification, no MFA, no audit log.**
- **SQLite** is a single-writer database. Fine for 3-10 users; use PostgreSQL beyond that (the code uses SQLAlchemy only, so the switch is a connection string plus a migration run).
- **The session cookie is not revocable server-side** (logout clears it, but a stolen cookie works until it expires). A server-side session store would fix this.
- **Job handlers are at-least-once.** A report may very rarely be produced twice; an email may be sent twice after a worker crash at the wrong moment.
- The test-only failure hook (`JOB_FAIL_HOOK`) is enabled only by the `testing` config; there is no way to switch it on in production configuration.

## Reporting and configuration checklist for a real deployment

1. `APP_ENV=production` and a long random `SECRET_KEY`.
2. Serve behind HTTPS (`COOKIE_SECURE` stays on) with a real WSGI server (the Docker image uses gunicorn).
3. `ALLOW_SELF_SELECT_ROLE=0`.
4. Back up `instance/agileflow.db` (or use PostgreSQL).
5. Configure `MAIL_BACKEND=smtp` with a dedicated sending account.
