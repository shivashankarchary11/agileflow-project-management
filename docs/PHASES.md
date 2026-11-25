# AgileFlow: Delivery Phases

Target runtime: **Python 3.14 only** (`requires-python = ">=3.14,<3.15"` from Phase 1).
Each phase is a branch + commit(s) pushed to GitHub, and ends with `pytest` green on 3.14.

| Phase | Branch | Theme | Status |
|---|---|---|---|
| 0 | `phase-0-docs` | Understand, document, baseline on 3.14 | done |
| 1 | `phase-1-foundation` | App factory, config, migrations, test isolation | planned |
| 2 | `phase-2-services-api` | Clean architecture, validation, bug fixes | planned |
| 3 | `phase-3-jobs-email` | Durable background jobs, retries, email | planned |
| 4 | `phase-4-organize-api` | Move, reorder, filter, search, board API | planned |
| 5 | `phase-5-frontend` | Modular UI, Kanban, toasts, edit forms | planned |
| 6 | `phase-6-security` | CSRF, rate limit, headers | planned |
| 7 | `phase-7-release` | Full tests, CI, Docker, final docs | planned |

For each phase: **Beginner** = what and why in plain words. **Advanced** = the engineering concepts.

---

## Phase 0: Understand and document
- **Beginner:** A web app has three layers: the browser (what you see), the server (the rules) and the database (storage). This phase only reads and explains them, and proves the app runs on Python 3.14.
- **Advanced:** Request lifecycle, the two-level authorization model, the thread-based job runner and its failure modes, dependency resolution on a new interpreter.
- **Delivered:** [PROJECT_WALKTHROUGH.md](PROJECT_WALKTHROUGH.md), [TESTING.md](TESTING.md), this file, `.gitignore` additions, `SQLAlchemy==2.0.58` pin (SQLAlchemy 2.1.9 fails to import on Python 3.14.7), baseline test run (2 passed).

## Phase 1: Python 3.14 foundation and app factory
- **Beginner:** An "app factory" is a function that builds the app. Tests can then build a throwaway copy with a throwaway database and never touch real data.
- **Advanced:** Config classes (Dev/Test/Prod), extension initialisation, `PRAGMA foreign_keys=ON` through an engine event, Alembic migrations (Flask-Migrate) replacing hand-written `ALTER TABLE`, timezone-aware datetimes.
- **Deliverables:** `pyproject.toml`, `.python-version`, pinned dependencies, `agileflow/` package skeleton, `wsgi.py`, models moved to `agileflow/models/`, initial migration, isolated `conftest.py`, ruff config.
- **Exit check:** `/api/health` works; tests never touch `instance/`; no deprecation warnings.

## Phase 2: Clean architecture, validation, and bug fixes
- **Beginner:** Put each business rule in one place ("only a Team Lead may delete") instead of repeating it in every URL handler.
- **Advanced:** Layering `api -> services -> repositories -> models`, a permission policy object, domain exceptions mapped to JSON errors, input schemas for POST and PATCH, N+1 query removal, 404-not-403 for hidden resources.
- **Deliverables:** `domain/`, `repositories/`, `services/`, `api/` blueprints (same URLs), ISO date validation, XSS fix, safe PATCH, role lookups from the DB, new endpoints (`GET` single project/story/task, remove member).
- **Exit check:** every route has happy-path and error tests (AUTH, PRJ, MEM, STY, TSK scenarios).

## Phase 3: Durable background jobs and email
- **Beginner:** Slow or failure-prone work (sending an email, building a report) happens in the background, and the app remembers its status so nothing is silently lost.
- **Advanced:** At-least-once delivery, atomic job claiming (`UPDATE ... WHERE status='Queued'`), exponential backoff, stale-lock recovery on startup, enqueue-after-commit, pluggable email backends (console, SMTP, memory).
- **Deliverables:** extended `background_job` table, `workers/` package, `progress_report` and `send_email` handlers, notification triggers (task assigned, added to project, report ready), `GET /api/jobs`, `POST /api/jobs/{id}/retry`, `.env.example`.
- **Exit check:** JOB and EML scenarios pass, including fail-once, fail-always and restart recovery.

## Phase 4: Organise features in the API
- **Beginner:** Let people sort, search and move work around.
- **Advanced:** Integer positions with transactional re-numbering, same-project move invariant, filtering and pagination pushed into the repository layer.
- **Deliverables:** `position` columns + migration, `PATCH .../move`, filtered list endpoints (`status`, `priority`, `assignee_id`, `q`, `limit`, `offset`), `GET /api/projects/{id}/board`.
- **Exit check:** ORG scenarios pass.

## Phase 5: Frontend rewrite
- **Beginner:** A friendlier screen: a board where you drag cards, forms to edit anything, and a pop-up message after every action.
- **Advanced:** ES modules, one API client that handles 401/CSRF, safe DOM rendering, accessible toast region, keyboard alternative to drag-and-drop, polling with timeout.
- **Deliverables:** modular `static/js/*`, readable CSS, Kanban board, filter/search bar, edit forms, remove member, job panel with Retry, no external font requests.
- **Exit check:** E2E-01 passes.

## Phase 6: Security hardening
- **Beginner:** Make sure only the right people do the right things and bad input cannot hurt us.
- **Advanced:** CSRF double-submit tokens, login throttling with generic error messages, CSP and other headers, secure cookie defaults, OWASP Top 10 mapping.
- **Deliverables:** CSRF middleware, rate limiter, header hook, `docs/SECURITY.md`.
- **Exit check:** SEC scenarios pass.

## Phase 7: Release
- **Beginner:** One command proves everything works, and a new teammate can set it up from the README.
- **Advanced:** Coverage gate, CI on 3.14, reproducible container, API reference with examples, schema documentation with ER diagram.
- **Deliverables:** full scenario coverage (>= 85% line coverage), GitHub Actions workflow, `Dockerfile` (`python:3.14-slim`, non-root), `docker-compose.yml`, final README, `API.md`, `SCHEMA.md`, `DECISIONS.md`, AI-usage and "what next" sections, tag `v1.0.0`.
