# AgileFlow: Delivery phases

Target runtime: **Python 3.14 only** (`requires-python = ">=3.14,<3.15"`).

| Phase | Theme | Status |
|---|---|---|
| 0 | Understand, document, baseline on 3.14 | done |
| 1 | App factory, config, migrations, isolated tests | done |
| 2 | Clean architecture, validation, bug fixes | done |
| 3 | Durable background jobs, retries, email | done |
| 4 | Organise: move, reorder, filter, search, board API | done |
| 5 | Modular UI: Kanban, toasts, edit forms, jobs panel | done |
| 6 | Security hardening | done |
| 7 | Full tests, CI, Docker, final docs | done |

For each phase: **Beginner** = what and why in plain words. **Advanced** = the engineering ideas. **Where** = the code. **Found while testing** = real bugs the tests caught on the way.

---

## Phase 0: Understand and document
- **Beginner:** A web app has three layers: the browser (what you see), the server (the rules), the database (the storage). We first read Varsha's code and wrote down how it works, before changing anything.
- **Advanced:** Request lifecycle, the two-level authorization model, the thread-based job runner and its failure modes, dependency resolution on a new interpreter.
- **Where:** [PROJECT_WALKTHROUGH.md](PROJECT_WALKTHROUGH.md) (describes the *original* code), baseline in TESTING.md.
- **Found:** `requirements.txt` did not pin SQLAlchemy, pip picked 2.1.9, which cannot even be imported on Python 3.14.7. The old tests wrote into the real development database.

## Phase 1: Python 3.14 foundation and app factory
- **Beginner:** An "app factory" is a function that builds the app. Tests can build a throwaway copy with a throwaway database and never touch real data.
- **Advanced:** Config classes per environment, extension initialisation, `PRAGMA foreign_keys=ON` via an engine event, Alembic migrations in batch mode, timezone-aware datetimes, pinned dependencies verified on 3.14.
- **Where:** `pyproject.toml`, `.python-version`, `requirements*.txt`, `agileflow/__init__.py`, `config.py`, `extensions.py`, `migrations/`, `tests/conftest.py`.
- **Found:** Alembic's default `fileConfig()` **disables every existing logger**. Because `python wsgi.py` migrates inside the app process, worker logs and console emails would have vanished silently. Fixed in `migrations/env.py`, with a regression test.

## Phase 2: Clean architecture, validation, bug fixes
- **Beginner:** Each business rule ("only a Team Lead may delete") lives in one place instead of being repeated in every URL handler.
- **Advanced:** Layering `api -> services -> repositories -> models`; a permission matrix as data (`domain/policy.py`); domain exceptions mapped to JSON errors; strict input schemas for POST and PATCH; N+1 removal with eager loading; 404-not-403 for hidden resources; roles read from the DB on every request.
- **Where:** `agileflow/domain/`, `repositories/`, `services/`, `api/`.
- **Fixed from the original:** stored XSS through `deadline`; HTML 500s on non-text JSON; unlimited-length PATCH values; self-assigned Team Lead in production; ID probing; role cached in the cookie; add-member always answering 201.
- **New endpoints:** `GET` single project/story/task, remove member.

## Phase 3: Durable background jobs and email
- **Beginner:** Slow or failure-prone work (sending an email, building a report) happens in the background. The app remembers the status, so nothing is silently lost and the user can see failures.
- **Advanced:** At-least-once delivery, atomic claim (`UPDATE ... WHERE status='Queued'`), exponential backoff, stale-lock recovery, enqueue-after-commit, pluggable backends (console/SMTP/memory), after-success hooks, bounded error storage.
- **Where:** `agileflow/workers/`, `services/notification_service.py`, `services/report_service.py`.
- **Emails sent when:** a task is assigned to someone else, a person is added to a project, a report is ready.
- **Found:** with Flask's default logger setup, INFO-level records (the console emails) were dropped; the worker also raced `python wsgi.py`'s migrations on a fresh database and printed a traceback. Both fixed.

## Phase 4: Organise features in the API
- **Beginner:** Let people sort, search and move work around.
- **Advanced:** Integer positions re-numbered in the same transaction, same-project move invariant, filtering and paging in the repository layer, `LIKE` wildcard escaping.
- **Where:** `task_service.move_task`, `story_service.move_story`, `story_repo.list_filtered`, `task_repo.board`, `services/ordering.py`.
- **Found:** Flask sorts JSON keys alphabetically, so the board columns arrived as Done/In Progress/To Do. Key order is now preserved.

## Phase 5: Frontend rewrite
- **Beginner:** A friendlier screen: a board where you drag cards, forms to edit everything, and a pop-up message after every action.
- **Advanced:** ES modules, one API client (CSRF header, 401 redirect), DOM built from text nodes only, accessible toast region, keyboard fallback for drag-and-drop, polling with a timeout and cancellation, no external requests (strict CSP).
- **Where:** `agileflow/web/static/js/*.js`, `css/app.css`, `web/templates/`.
- **Found by the real-browser test:** the Stories view passed an array to `Element.append()`, which prints `[object HTMLElement]` instead of the stories. No unit test could see this.

## Phase 6: Security hardening
- **Beginner:** Make sure only the right people do the right things and bad input cannot hurt us.
- **Advanced:** Per-session CSRF token (rotated at login, constant-time compare), sliding-window rate limiting, timing-safe login, CSP/nosniff/frame/referrer headers, secure cookie defaults, mandatory production secret.
- **Where:** `agileflow/security.py`, `config.py`, `docs/SECURITY.md` (OWASP mapping and honest limitations).

## Phase 7: Release
- **Beginner:** One command proves everything works, and a new teammate can set it up from the README.
- **Advanced:** Coverage gate, CI on 3.14, reproducible container, migration-drift test, API reference with examples, schema documentation with ER diagram.
- **Where:** `.github/workflows/ci.yml`, `Dockerfile`, `docker-compose.yml`, `docs/*`, `README.md`, `scripts/`.
- **Result:** 207 automated tests (99 % coverage), plus live HTTP and real-browser smoke runs.
