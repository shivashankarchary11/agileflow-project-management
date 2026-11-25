# Design decisions and tradeoffs

Each entry: the choice, why, and what it costs. Security-specific points are in [SECURITY.md](SECURITY.md).

## Data and domain

| Decision | Why | Tradeoff / when to revisit |
|---|---|---|
| **Relational hierarchy** `Project -> UserStory -> Task` as three tables with foreign keys and `ON DELETE CASCADE`. | Independent CRUD, clean ownership, simple "delete a project removes everything", easy reporting with grouped queries. | Tasks cannot nest (no sub-tasks) and a task belongs to exactly one story. Add a `parent_id` if sub-tasks are needed. |
| **SQLite** with WAL, foreign keys ON, busy timeout. | Zero setup, a single file, perfect for 3-10 users, allowed by the brief. | One writer at a time. Move to PostgreSQL for more users or several app servers; only the connection string and one migration run change. |
| **Alembic migrations** (Flask-Migrate) instead of `create_all()` plus hand-written `ALTER TABLE`. | Repeatable, reviewable schema changes. A test fails if models and migrations drift. | One more tool to learn; batch mode is needed for SQLite. |
| **Two role levels**: a global role (only controls *creating* projects) and a per-project role (owner = Team Lead, or Member/Viewer). | A person can lead one project and be a viewer in another. The owner needs no membership row. | Slightly more to explain than a single role. |
| **`position` integers** kept as a clean 0..n-1 sequence, re-numbered on every move/delete. | Simple, deterministic ordering that works with SQLite and is easy to test. | Re-numbering touches several rows per move (fine at this scale; use fractional/LexoRank ordering for huge lists). |
| **Dates are `DATE` columns**, timestamps are UTC. | Real validation and sorting; avoids the old free-text date that enabled XSS. | None worth noting. |
| **Assignee must belong to the project**, checked in the service. | Prevents assigning (and emailing) outsiders. | The rule is in code, not a database constraint. |
| **Non-members get 404, not 403.** | Existence of other projects is not revealed. | Slightly harder to debug "why can't I see it?"; the message says "not found". |

## Architecture

| Decision | Why | Tradeoff |
|---|---|---|
| **App factory + layers** (`api -> services -> repositories -> models`). | Business rules in one place, each layer testable alone, tests build a fresh isolated app (this fixed the old tests wiping the dev database). | More files than a single `app.py`; worth it past ~200 lines. |
| **Hand-written validators** (`api/schemas.py`) instead of pydantic/marshmallow. | No extra dependency to verify on Python 3.14; the rules are tiny and fully unit-tested. | Less declarative. Switch to pydantic if the API grows. |
| **Reject over-long input** instead of silently truncating. | The user finds out immediately; no hidden data loss. | Slightly stricter than before. |
| **Plain JSON REST**, nested detail for the hierarchy plus flat list endpoints. | Matches the brief, easy to document and test. | The project detail payload includes every story and task; paginate stories if projects get huge (the stories list already has `limit/offset`). |
| **Vanilla JavaScript ES modules**, no framework or build step. | Nothing to install, reviewable, the CSP can stay strict. | More manual DOM code; consider a framework if the UI grows much more. |
| **Drag-and-drop uses the native HTML5 API** with a "move to" select as the keyboard/touch fallback. | Accessible and dependency-free. | Native drag-and-drop is weak on touch screens; the select covers that. |

## Asynchronous work

| Decision | Why | Tradeoff |
|---|---|---|
| **Database-backed queue** (`background_job` table) plus **one worker thread** inside the web process. | Satisfies the async requirement with no extra infrastructure; jobs survive restarts; state is visible to users and testable. | Throughput is limited to one process. For heavy load use Celery/RQ with Redis (the handler functions would move over unchanged). |
| **Enqueue after commit; never send email inside a request.** | A slow or broken mail server cannot slow down or break "assign task". | The email can be delayed by a poll interval (1 s). |
| **Retries with exponential backoff**, max 3 attempts, then `Failed` with the error visible and a manual Retry. | Transient outages heal themselves; permanent ones are visible instead of looping forever. | Backoff is per job, not per recipient/server; a long outage fails several jobs (all retryable in one click each). |
| **At-least-once delivery** + stale-job recovery. | A crashed worker never loses a job. | A job may run twice in rare crash windows, so handlers must be repeatable (reports and emails are). |
| **Atomic claim** with a conditional `UPDATE`. | Several workers/processes cannot take the same job. | SQLite serialises writers anyway; on PostgreSQL use `SELECT ... FOR UPDATE SKIP LOCKED`. |
| **Email backends: console (default), SMTP, memory.** | Works with no credentials; real sending is one setting away; tests inspect messages. | No HTML email or templates yet. |
| **A test-only failure hook** instead of mocking the worker. | The real retry path is exercised end to end through the HTTP API. | The hook code ships in the app, but can only be enabled by the `testing` config. |

## Testing

| Decision | Why |
|---|---|
| **Every test gets its own in-memory database** via `create_app("testing")`. | Isolation, speed (207 tests in ~13 s), and it can never touch `instance/`. |
| **Cheap password hashing in the test config only.** | scrypt is deliberately slow; using it in 200+ tests wasted ~35 s. Production keeps scrypt. |
| **Time is injected** into the queue functions (`now=`). | Backoff and stale-recovery are tested without sleeping. |
| **Two scripts outside pytest drive the real thing**: `scripts/live_smoke.py` (real server + real worker over HTTP) and `scripts/ui_smoke` (real Edge/Chrome, 47 checks). | Unit tests cannot catch bugs like an array passed to `Element.append`; the browser run found exactly that. They are not in CI because they need a browser. |
| **Coverage gate of 85 %** (currently 99 %). | Keeps the safety net from decaying. |

## Things deliberately left out (see README "What I would build next")

Sub-tasks, comments, attachments, sprints, email invitations for people who have not registered, password reset, real-time updates (WebSocket/SSE), audit log, PostgreSQL, a durable queue service, i18n.
