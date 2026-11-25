# Testing guide and scenario catalogue

## 1. Results (measured on Python 3.14.7, Windows)

| Check | Command | Result |
|---|---|---|
| Automated suite | `python -m pytest` | **207 passed** in about 13 s |
| Coverage | `python -m pytest --cov=agileflow` | **99 %** (gate in CI: 85 %) |
| Live HTTP smoke (real server + real worker thread) | `python scripts/live_smoke.py` | all checks pass (2 scenarios) |
| Real-browser UI smoke (headless Edge/Chrome) | `node scripts/ui_smoke/run.mjs` | **47 checks pass**, zero console/CSP errors |
| Lint | `ruff check .` | CI. (The ruff binary is blocked on the author's managed laptop, so pyflakes was used locally; the code has no unused imports/variables.) |

Before this work the repository had **2 tests**, which wrote to the real development database (see PROJECT_WALKTHROUGH, issue 1).

## 2. How to run

```cmd
:: one-time setup (Windows; see docs/RUN_GUIDE.md for every step)
py -3.14 -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements-dev.txt

python -m pytest                          :: everything
python -m pytest tests/unit               :: one folder
python -m pytest -k "job"                 :: by keyword
python -m pytest tests/api/test_organize.py::test_org_01_move_task_to_another_story_same_project
python -m pytest --cov=agileflow --cov-report=term-missing
```

Smoke scripts (start their own server on spare ports with a throwaway database; nothing in `instance/` is touched):

```cmd
python scripts\live_smoke.py
node scripts\ui_smoke\run.mjs            :: needs Node 22+ and Edge or Chrome (set BROWSER=... if not found)
```

## 3. Test types

| Layer | Folder | What it proves | Speed |
|---|---|---|---|
| Unit | `tests/unit/` | One rule without HTTP or a database: permission matrix, input validators, rate limiter, config, ordering | instant |
| API | `tests/api/` | Every route: status code, JSON shape, auth, validation, isolation between users | fast |
| Worker | `tests/workers/` | Queue states, retries, backoff, stale recovery, email backends, the real worker thread | fast (no sleeping; time is injected) |
| Workflow | `tests/test_workflow.py` | The whole product story in one test | fast |
| UI (server side) | `tests/e2e/` | Pages render, assets load, templates are CSP-clean, JS has no `innerHTML`, every module imports, JS syntax valid | fast |
| Live smoke | `scripts/live_smoke.py` | Real server, real thread, real HTTP, CSRF on, failing SMTP | ~30 s |
| Browser smoke | `scripts/ui_smoke/` | Real UI clicked through in a real browser | ~60 s |

Rules every test follows: it builds its own app with `create_app("testing")` (isolated in-memory SQLite); the background thread is off and tests call `run_pending()` themselves; email goes to an in-memory backend; nothing touches `instance/`.

## 4. Scenario catalogue (48 scenarios, all covered)

Test names are in the files shown (search for the ID, e.g. `test_org_01`).

### Authentication, `tests/api/test_auth.py`
| ID | Scenario | Expected |
|---|---|---|
| AUTH-01 | Register with valid data | 201, logged in |
| AUTH-02 | Duplicate email (any letter case) | 409 |
| AUTH-03 | Short password, bad email, blank/non-text name, bad role, over-long name; body not JSON | 400 |
| AUTH-04 | Login ok / wrong password / unknown email | 200 / 401 / 401 with the **same** message |
| AUTH-05 | Protected API without login; page without login | 401 JSON; redirect to /login |
| AUTH-06 | Logout, then call an API | 401 |
| (extra) | First user becomes Team Lead when role choice is off; deleted user's old cookie is rejected | |

### Projects and members, `test_projects.py`, `test_members.py`
| ID | Scenario | Expected |
|---|---|---|
| PRJ-01 | Team Lead creates a project | 201 |
| PRJ-02 | Member or Viewer creates a project | 403 |
| PRJ-03 | Blank/non-text name, bad status, bad/impossible/hostile deadline, over-long fields (POST and PATCH) | 400, never 500 |
| PRJ-04 | List shows only own or member projects; counts, search, paging | isolation |
| PRJ-05 | Non-member reads, edits, deletes, adds stories | 404 (same as a missing id) |
| PRJ-06 | Delete project cascades to stories, tasks, members | rows gone |
| MEM-01 | Add by email as Member or Viewer (case-insensitive) | 201 |
| MEM-02 | Unknown email / the owner / invalid role / bad email; non-lead tries | 404 / 400 / 400 / 403 |
| MEM-03 | Re-adding changes the role | 200 (not 201) |
| MEM-04 | Remove a member; their tasks become unassigned; they lose access | 200 |

### Stories and tasks, `test_stories.py`, `test_tasks.py`
| ID | Scenario | Expected |
|---|---|---|
| STY-01 | Lead and Member create; positions are 0,1,2 | 201 |
| STY-02 | Viewer creates or updates | 403 (can still read) |
| STY-03 | Invalid priority/status/title (POST and PATCH) | 400 |
| STY-04 | Only the Lead deletes; cascades to tasks; others renumbered | 200 / 403 |
| TSK-01 | Create with a valid assignee, due date | 201 |
| TSK-02 | Assignee outside the project / unknown / non-numeric | 400 |
| TSK-03 | Bad due-date formats (`01-06-2030`, `20300601`, ...) | 400 |
| TSK-04 | Status To Do, In Progress, Done persists | 200 |
| TSK-05 | Reassign, unassign | 200 |

### Organise, `test_organize.py`
| ID | Scenario | Expected |
|---|---|---|
| ORG-01 | Move a task to another story of the same project; both stories renumbered | 200 |
| ORG-02 | Move across projects (or to a missing story) | 400, task unchanged |
| ORG-03 | Reorder tasks and stories; past-the-end clamps | positions updated |
| ORG-04 | Filter stories by status, priority, assignee, text; combinations; paging; wildcard characters are literal; bad values | correct subset / 400 |
| ORG-05 | Board groups tasks into To Do / In Progress / Done (+ filters) | 3 columns |

### Async jobs and email, `test_job_queue.py`, `test_jobs_api.py`, `test_email_and_notifications.py`
| ID | Scenario | Expected |
|---|---|---|
| JOB-01 | Report Queued, then Completed; content correct; scoped to your projects; "ready" email queued | counts, overdue |
| JOB-02 | Handler fails once | retried, Completed, attempts = 2 |
| JOB-03 | Handler always fails | Failed, attempts = 3, error stored |
| JOB-04 | Backoff grows | `next_run_at` +2 s then +4 s; not claimable early |
| JOB-05 | Worker died (stale Running) | re-queued; healthy jobs untouched |
| JOB-06 | Another user's job | 404 |
| JOB-07 | Retry a failed job; only Failed can be retried | attempts reset / 409 |
| (extra) | Claim is exclusive; future jobs wait; oldest first; unknown job type fails cleanly; long errors truncated; hook failure does not undo a job; **the real worker thread processes a job** | |
| EML-01 | Assign a task to someone else: exactly one email; none for self/nobody; reassign only when it changes; adding a member emails them once | queued, then delivered |
| EML-02 | SMTP down: retries, ends Failed, error visible to the person who triggered it, retry after the server returns | |
| EML-03 | Console, memory and SMTP backends; unknown backend rejected | |

### Security and system, `test_security.py`, `test_system.py`, `tests/e2e/`
| ID | Scenario | Expected |
|---|---|---|
| SEC-01 | POST without / with wrong / old CSRF token; token rotates; GET unaffected | 403 / 403 / 403 / 2xx |
| SEC-02 | 6th failed login in a minute; per-account; success resets; registration throttled | 429 |
| SEC-03 | `<script>` / `<img onerror>` in names, titles, deadline; page escapes user name; JS never uses `innerHTML` | stored as text, rendered inert |
| SEC-04 | CSP, nosniff, frame deny, referrer, no-store; HSTS only on https; cookie flags; JSON 404/405/500 | headers present |
| SYS-01 | A test run leaves the dev database untouched; each app gets its own empty DB | file unchanged |
| SYS-02 | `/api/health` | 200 |
| SYS-03 | Python 3.14 enforced in pyproject, `.python-version`, Dockerfile, CI, and the tests themselves | enforced |
| (extra) | SQLite foreign keys are ON; **migrations produce exactly the model schema**; migrating does not disable logging | |
| E2E-01 | Register, project, story, task, drag a card, toast | `tests/e2e/` (server side) + `scripts/ui_smoke` (real browser) |

## 5. Manual test script (5 minutes)

Run `python wsgi.py` and use two browser windows (one private).

1. Window A: **Create an account**, role **Team Lead**. Window B: register `member@example.com` as **Team Member**.
2. A: **+ New** project "Demo". **Team** tab, **+ Add teammate**, `member@example.com`. Toast: "Teammate added". *(Terminal shows the console email.)*
3. B: reload, open "Demo". **Stories** tab, **+ New user story**, then **+ Add task** (assign to yourself).
4. A: **Stories**, **+ Add task**, **assign to the member**. Terminal prints "New task" email.
5. B: **Board** tab, **drag** a card from To Do to In Progress. Toast "Moved to In Progress". Use the card's select to move it to Done. Progress bar changes.
6. Type in the search box: the board filters. **Clear** restores it. Try the priority and assignee filters.
7. **Stories** tab: **Edit** a story and a task (change title, due date, assignee, or move the task to another story). Use the up/down arrows to reorder.
8. Register a **Viewer**, add them to the project: no add/edit/delete buttons, status selects are disabled.
9. **Reports & jobs** (sidebar): **Generate progress report**. The row goes Queued, Running, Completed; click **Download**.
10. Failure demo: stop the server, set `MAIL_BACKEND=smtp` and `SMTP_HOST=127.0.0.1` `SMTP_PORT=1`, restart, add a teammate. In **Reports & jobs** the email job retries, then shows **Failed** with the error and a **Retry** button.
11. As a user outside the project, call `PATCH /api/projects/1`: **404** (not 403).
12. Try `<script>alert(1)</script>` as a project name: it is shown as text.

## 6. What is *not* automated

- Visual layout and responsiveness (checked by eye).
- Real SMTP delivery (needs credentials; the protocol steps are tested with a fake SMTP server).
- Touch-screen drag and drop (the select fallback is tested instead).
- Load/concurrency beyond the worker-claim logic.
- The Docker image build (no Docker on the author's machine; CI builds it).
