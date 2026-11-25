# AgileFlow: Testing Guide and Scenario Catalogue

## 1. Baseline (measured, Phase 0)

| Item | Result |
|---|---|
| Python | 3.14.7 (Windows, fresh `.venv`) |
| Command | `python -m pytest -q -p no:cacheprovider -W default` |
| Result | **2 passed** in about 6 s |
| Warnings | `datetime.utcnow()` is deprecated (3 occurrences; fixed in Phase 1) |
| Dependency gotcha | With the old unpinned `requirements.txt`, pip installed SQLAlchemy 2.1.9, and **every import failed** (`ImportError: ... PyInit__collections_cy`). Pinning `SQLAlchemy==2.0.58` fixed it. |
| Isolation bug | The tests wrote to the real `instance/agile_manager.db` (the file appeared after the run, with the 2 test users). See section 5. |

### What the 2 existing tests do (`tests/test_workflow.py`)

1. `test_project_story_task_roles_and_report`: registers a Team Lead and a Member, Lead creates a project and adds the Member, Member creates a story and a task assigned to themselves (hard-coded `assigned_to_id: 2`), then generates a report and polls until `Completed` and checks the project name is in the result.
2. `test_viewer_cannot_create_story`: a Viewer who was added to a project gets `403` when creating a story.

## 2. How to run

```cmd
py -3.14 -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python -m pytest -q
```

Useful variants (available once the later phases land):

| Goal | Command |
|---|---|
| One scenario family | `python -m pytest -q -k "JOB"` |
| Coverage gate (Phase 7) | `python -m pytest --cov=agileflow --cov-fail-under=85` |
| Lint (Phase 1+) | `ruff check .` |
| UI smoke (Phase 5+) | `python -m pytest tests/e2e -q` |

## 3. Test types and where they live (target layout)

| Layer | Folder | What it proves | Speed |
|---|---|---|---|
| Unit | `tests/unit/` | One business rule in a service or policy, without HTTP (e.g. "a Viewer may not create a story") | very fast |
| API | `tests/api/` | Every route: status code, JSON shape, auth, validation | fast |
| Worker | `tests/workers/` | Job queue states, retry/backoff, email backends, stale-lock recovery | fast, no real sleeping (time is injected) |
| E2E | `tests/e2e/` | A real browser clicks through the main flow | slow, runs in CI |

Rules for all tests: each test builds its own app via `create_app("testing")` with a throwaway database; no test may touch `instance/`; the email backend is the in-memory one; the background worker thread is off and tests call `run_pending()` themselves.

## 4. Scenario catalogue

**Status key:** `covered` = an existing test exercises it now (partly or fully); otherwise the phase that will add the test.

### Authentication
| ID | Scenario | Expected | Status |
|---|---|---|---|
| AUTH-01 | Register with valid data | 201, session set | covered (indirectly) |
| AUTH-02 | Register with a duplicate email | 409 | Phase 2 |
| AUTH-03 | Password under 8 chars, or malformed email | 400 | Phase 2 |
| AUTH-04 | Login ok / wrong password / unknown email | 200 / 401 / 401 with the same message | Phase 2 |
| AUTH-05 | Protected API without login | 401 JSON | Phase 2 |
| AUTH-06 | Logout, then call an API | 401 | Phase 2 |

### Projects and members
| ID | Scenario | Expected | Status |
|---|---|---|---|
| PRJ-01 | Team Lead creates a project | 201 | covered |
| PRJ-02 | Member or Viewer creates a project | 403 | Phase 2 |
| PRJ-03 | Blank name, bad status, non-string name | 400 (never 500) | Phase 2 |
| PRJ-04 | Project list shows only own or member projects | isolation | Phase 2 |
| PRJ-05 | A non-member reads or edits a project | 404 | Phase 2 |
| PRJ-06 | Delete project cascades to stories, tasks, members | rows gone | Phase 2 |
| MEM-01 | Add by email as Member or Viewer | 201 | covered |
| MEM-02 | Unknown email / the owner / invalid role | 404 / 400 / 400 | Phase 2 |
| MEM-03 | Re-adding changes the role | 200 | Phase 2 |
| MEM-04 | Remove a member; their tasks become unassigned | 200 | Phase 2 |

### Stories and tasks
| ID | Scenario | Expected | Status |
|---|---|---|---|
| STY-01 | Lead and Member create a story | 201 | covered (Member) |
| STY-02 | Viewer creates or updates a story | 403 | covered (create) |
| STY-03 | Invalid priority or status | 400 | Phase 2 |
| STY-04 | Only the Team Lead can delete a story; cascades to tasks | 200 / 403 | Phase 2 |
| TSK-01 | Create a task with a valid assignee | 201 | covered |
| TSK-02 | Assignee outside the project | 400 | Phase 2 |
| TSK-03 | Bad due-date format | 400 | Phase 2 |
| TSK-04 | Status goes To Do, In Progress, Done and persists | 200 | Phase 2 |
| TSK-05 | Reassign and unassign | 200 | Phase 2 |

### Organise (Kanban, filters, reorder)
| ID | Scenario | Expected | Status |
|---|---|---|---|
| ORG-01 | Move a task to another story in the same project | 200 | Phase 4 |
| ORG-02 | Move a task across projects | 400 | Phase 4 |
| ORG-03 | Reorder stories and tasks | positions updated | Phase 4 |
| ORG-04 | Filter by status, priority, assignee, and text `q` | correct subset | Phase 4 |
| ORG-05 | Board endpoint groups tasks by status | 3 columns | Phase 4 |

### Async jobs and email
| ID | Scenario | Expected | Status |
|---|---|---|---|
| JOB-01 | Report goes Queued, Running, Completed | result contains counts | covered |
| JOB-02 | Handler fails once | retried, then Completed, attempts = 2 | Phase 3 |
| JOB-03 | Handler always fails | Failed, `last_error` set | Phase 3 |
| JOB-04 | Backoff grows between attempts | `next_run_at` increases | Phase 3 |
| JOB-05 | Stale Running job at startup | re-queued | Phase 3 |
| JOB-06 | Read another user's job | 404 | Phase 3 |
| JOB-07 | Retry a failed job | new attempt | Phase 3 |
| EML-01 | Assigning a task enqueues one email | 1 `send_email` job | Phase 3 |
| EML-02 | SMTP failure | retried, then Failed | Phase 3 |
| EML-03 | Console and memory backends | message captured | Phase 3 |

### Security and system
| ID | Scenario | Expected | Status |
|---|---|---|---|
| SEC-01 | State-changing request without CSRF token | 403 | Phase 6 |
| SEC-02 | 6th login attempt within a minute | 429 | Phase 6 |
| SEC-03 | `<script>` in names, deadline, titles | rendered inert | Phase 2 and 5 |
| SEC-04 | Security headers present (CSP etc.) | headers set | Phase 6 |
| SYS-01 | A test run leaves the dev DB untouched | file unchanged | Phase 1 |
| SYS-02 | `/api/health` | 200 | Phase 1 |
| SYS-03 | `requires-python` and CI both say 3.14 | enforced | Phase 1 and 7 |
| E2E-01 | Register, project, story, task, drag card, toast shown | passes | Phase 5 |

**Coverage today:** 7 of 48 scenarios have a test. The other 41 are assigned to phases above.

## 5. Manual test script (5 minutes, works today)

Use two browser windows (one normal, one private).

1. Window A: open http://127.0.0.1:5000, **Create one**, register `lead@example.com`, role **Team Lead**.
2. Window B: register `member@example.com`, role **Member**.
3. Window A: **New project**, then open it, then **Add teammate** with `member@example.com`.
4. Window B: refresh, so the project appears. Add a story, then a task assigned to yourself.
5. Change the task status to **Done**. The progress bar on the project card should move.
6. Window A: **Generate report**. Expect a toast, a short wait, then a `.txt` download.
7. Register a third user as **Viewer**, have the Lead add them as Viewer. Confirm the status dropdowns are disabled and "Add story" is missing.
8. As a user who is not in the project, send `PATCH /api/projects/1` (for example from the browser console with `fetch`). Today you get **403**; after Phase 2 you get **404**, so project IDs are not leaked.

## 6. Known test-suite problems (fixed in later phases)

- **DB isolation (Phase 1):** `conftest`/`test_workflow.py` set `SQLALCHEMY_DATABASE_URI` after `SQLAlchemy(app)` was built, so the setting is ignored and `drop_all()` hits `instance/agile_manager.db`. If you have real data in that file, back it up before running the suite.
- **Hard-coded id:** `assigned_to_id: 2` assumes row order; later tests read the id from the API response.
- **Real sleeping:** the report test polls up to 3 s. Phase 3 replaces this with direct `run_pending()` calls.
- **No failure-path test** for the background job, and no negative tests (400/403/404/409) apart from one 403.
