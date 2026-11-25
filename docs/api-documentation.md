# REST API reference

Base URL: `http://127.0.0.1:5000`. Request and response bodies are JSON. Dates are `YYYY-MM-DD`; timestamps are ISO-8601 UTC ending in `Z`. Lists use `limit` (default 50, max 200) and `offset`.

## Conventions

**Authentication.** Log in with `POST /auth/login`; the server sets a signed, `HttpOnly` session cookie. Every `/api/*` route (except `/api/health` and `/api/csrf-token`) answers `401` without it.

**CSRF.** Every `POST`, `PATCH`, `DELETE` under `/api/` and `/auth/` must send the header `X-CSRF-Token`. The bundled UI reads the token from `<meta name="csrf-token">`. Other clients call `GET /api/csrf-token` (using the same cookie jar). The token **changes at login and registration**; the response of those two calls contains the new `csrf_token`.

**Errors.** Always JSON:

```json
{ "error": "Story title is required.", "code": "validation_error" }
```

| Status | `code` | Meaning |
|---|---|---|
| 400 | `validation_error` | Bad input: wrong type, too long, bad enum or date, assignee outside the project, ... |
| 401 | `unauthorized` | Not logged in, or wrong email/password (same message for both). |
| 403 | `forbidden` | Logged in and inside the project, but your role may not do this; or CSRF token missing/invalid. |
| 404 | `not_found` | Does not exist, **or you are not in that project** (existence is not revealed). |
| 409 | `conflict` | Email already registered; job is not in a state that allows the action. |
| 429 | `too_many_requests` | Login or registration throttled. |
| 500 | `internal_error` | Unexpected; details are only in the server log. |

**Roles.** Team Lead (project owner) can do everything. Member can create/edit stories and tasks. Viewer is read-only. The global role chosen at sign-up only decides who may create projects.

| Action | Team Lead | Member | Viewer |
|---|---|---|---|
| View project, stories, tasks, board | yes | yes | yes |
| Edit/delete project, manage members | yes | no | no |
| Create/edit/move stories and tasks | yes | yes | no |
| Delete stories and tasks | yes | no | no |

## Endpoint overview

| Method | Path | Who | Success |
|---|---|---|---|
| GET | `/api/health` | anyone | 200 |
| GET | `/api/csrf-token` | anyone | 200 |
| POST | `/auth/register` | anyone | 201 |
| POST | `/auth/login` | anyone | 200 |
| POST | `/auth/logout` | anyone | 200 |
| GET | `/api/me` | logged in | 200 |
| GET | `/api/projects` | logged in | 200 |
| POST | `/api/projects` | global Team Lead | 201 |
| GET | `/api/projects/{id}` | project member | 200 |
| PATCH | `/api/projects/{id}` | project Team Lead | 200 |
| DELETE | `/api/projects/{id}` | project Team Lead | 200 |
| POST | `/api/projects/{id}/members` | project Team Lead | 201 added / 200 role changed |
| DELETE | `/api/projects/{id}/members/{user_id}` | project Team Lead | 200 |
| GET | `/api/projects/{id}/stories` | project member | 200 (filters, paging) |
| POST | `/api/projects/{id}/stories` | Lead, Member | 201 |
| GET | `/api/projects/{id}/board` | project member | 200 (Kanban columns) |
| GET | `/api/stories/{id}` | project member | 200 |
| PATCH | `/api/stories/{id}` | Lead, Member | 200 |
| DELETE | `/api/stories/{id}` | Lead | 200 |
| PATCH | `/api/stories/{id}/move` | Lead, Member | 200 |
| POST | `/api/stories/{id}/tasks` | Lead, Member | 201 |
| GET | `/api/tasks/{id}` | project member | 200 |
| PATCH | `/api/tasks/{id}` | Lead, Member | 200 |
| DELETE | `/api/tasks/{id}` | Lead | 200 |
| PATCH | `/api/tasks/{id}/move` | Lead, Member | 200 |
| POST | `/api/reports` | logged in | 202 |
| GET | `/api/jobs` | logged in | 200 (your jobs) |
| GET | `/api/jobs/{id}` | job owner | 200 |
| POST | `/api/jobs/{id}/retry` | job owner | 202 |

## Authentication

### `POST /auth/register`
```json
{ "name": "Ada Lovelace", "email": "ada@example.com", "password": "at-least-8-chars", "role": "Team Lead" }
```
`role` is `Team Lead`, `Member` (default) or `Viewer`, **only honoured when `ALLOW_SELF_SELECT_ROLE=1`** (default in development). When it is `0` (default in production) the first account becomes Team Lead and everyone else a Member.
Limits: name <= 80, email valid and <= 160, password 8-128 characters. `201`:
```json
{ "message": "Account created.", "role": "Team Lead", "csrf_token": "..." }
```
`409` if the email exists (case-insensitive). The user is logged in immediately.

### `POST /auth/login`
`{ "email": "...", "password": "..." }` -> `200 {"message", "role", "csrf_token"}`. Wrong email *or* password -> `401 "Incorrect email or password."` (identical). After **5 failed attempts per minute** for the same address+email -> `429`, even with the right password; a successful login clears the counter.

### `POST /auth/logout` -> `200`. `GET /api/me` -> `{ "id", "name", "email", "role" }`.

## Projects

### `GET /api/projects?q=&limit=&offset=`
Projects you own or belong to, newest first, with counts (no nested stories):
```json
{ "items": [ { "id": 1, "name": "Apollo", "description": "", "status": "Active", "deadline": "2031-05-05",
               "owner_id": 1, "owner_name": "Lena Lead", "my_role": "Team Lead",
               "story_count": 2, "task_count": 5, "done_count": 2 } ],
  "total": 1, "limit": 50, "offset": 0 }
```
`q` is a case-insensitive substring match on the name (`%` and `_` are literal).

### `POST /api/projects`  (global Team Lead only)
`{ "name": "Apollo", "description": "", "status": "Active", "deadline": "2031-05-05" }` -> `201` project detail. Only `name` is required. `status` is `Active`, `On Hold` or `Completed`. `deadline` may be `null`/`""`.

### `GET /api/projects/{id}` -> project detail (the whole hierarchy)
```json
{ "id": 1, "name": "Apollo", "status": "Active", "deadline": "2031-05-05", "my_role": "Member",
  "capabilities": { "project.view": true, "story.create": true, "story.delete": false, "...": "..." },
  "members": [ { "id": 1, "name": "Lena Lead", "email": "...", "role": "Team Lead" },
               { "id": 2, "name": "Max Member", "email": "...", "role": "Member" } ],
  "story_count": 1, "task_count": 2, "done_count": 1,
  "stories": [ { "id": 7, "title": "Sign in", "priority": "High", "status": "To Do", "position": 0,
                 "tasks": [ { "id": 11, "title": "Login form", "status": "Done", "assigned_to_id": 2,
                              "assigned_to": "Max Member", "due_date": null, "position": 0 } ] } ] }
```
`capabilities` is what the UI uses to show or hide buttons; the server still enforces every rule.

### `PATCH /api/projects/{id}` / `DELETE /api/projects/{id}` (project Team Lead)
Partial update of `name`, `description`, `status`, `deadline`. Delete removes all stories, tasks and memberships.

### `POST /api/projects/{id}/members` (project Team Lead)
`{ "email": "max@example.com", "role": "Member" }` (`Member` or `Viewer`). The person must already have registered. `201` when added (and an email is queued), `200` when an existing member's role changed. `404` unknown email, `400` if it is the owner.

### `DELETE /api/projects/{id}/members/{user_id}`
Removes the person and **unassigns** their tasks in this project. `404` if they are not a member (the owner cannot be removed).

## User stories

`POST /api/projects/{id}/stories` body: `{ "title": "...", "description": "", "priority": "Medium", "status": "To Do" }` (`title` required, <= 160; description <= 2000). The new story is placed last. `201` story with `"tasks": []`.

`GET /api/projects/{id}/stories?status=&priority=&assignee_id=&q=&limit=&offset=` -> `{ "items": [story + tasks], "total", "limit", "offset" }`.
`status`: To Do / In Progress / Done. `priority`: Low / Medium / High. `assignee_id`: stories having a task assigned to that person. `q`: case-insensitive substring of the story title/description **or any of its task titles**. Invalid filter values -> `400`.

`GET /api/stories/{id}`, `PATCH /api/stories/{id}` (any of title, description, priority, status), `DELETE /api/stories/{id}` (Lead; deletes its tasks; remaining stories are renumbered).

`PATCH /api/stories/{id}/move` body `{ "position": 0 }` -> reorders among the project's stories (0-based; values past the end go last).

## Tasks

`POST /api/stories/{id}/tasks`
```json
{ "title": "Login form", "description": "", "status": "To Do", "due_date": "2031-06-01", "assigned_to_id": 2 }
```
Only `title` is required. `assigned_to_id` must be the project's Team Lead or one of its members, otherwise `400 "Assignee must be a member of this project."`. If assigned to someone **other than yourself**, an email is queued for them. `201`:
```json
{ "id": 11, "story_id": 7, "project_id": 1, "story_title": "Sign in", "story_priority": "High",
  "title": "Login form", "description": "", "status": "To Do", "due_date": "2031-06-01", "position": 0,
  "assigned_to_id": 2, "assigned_to": "Max Member", "created_at": "2026-11-25T10:00:00Z" }
```

`GET /api/tasks/{id}`, `PATCH /api/tasks/{id}` (title, description, status, due_date, assigned_to_id; send `"assigned_to_id": null` to unassign), `DELETE /api/tasks/{id}` (Lead).

### `PATCH /api/tasks/{id}/move`
Any combination of (at least one required):

| Field | Effect |
|---|---|
| `status` | Move to a Kanban column (`To Do`, `In Progress`, `Done`). |
| `story_id` | Move to another story **of the same project**. Another project's story (or a missing one) -> `400 "Target story must exist in the same project."` |
| `position` | 0-based place among the target story's tasks (past the end = last). |

### `GET /api/projects/{id}/board?assignee_id=&priority=&story_id=&q=`
```json
{ "project_id": 1, "total": 3,
  "columns": { "To Do": [task, ...], "In Progress": [], "Done": [task] } }
```
`priority` is the **story's** priority. `q` matches the task title or its story title.

## Background jobs and reports

### `POST /api/reports` -> `202`
Queues a progress report (covers only the projects you can see) and returns immediately:
```json
{ "id": 5, "job_id": 5, "type": "progress_report", "status": "Queued", "attempts": 0, "max_attempts": 3,
  "next_run_at": "2026-11-25T10:00:00Z", "error": "", "has_result": false, "summary": "Progress report",
  "message": "Report generation started in the background." }
```
When it completes you are also emailed. (In the test configuration only, the body `{"fail_n_times": 2}` makes the first N attempts fail on purpose so retries can be tested; it is ignored otherwise.)

### `GET /api/jobs/{id}` -> job with `result` (the report text)
`status` is `Queued`, `Running`, `Completed` or `Failed`. While retrying, `status` is `Queued`, `attempts` > 0, `error` holds the last error and `next_run_at` says when the next attempt will run. Other people's jobs -> `404`.

### `GET /api/jobs?limit=` -> `{ "items": [...] }`
Your jobs, newest first, **without** the `result` text (`has_result` says whether there is one). Includes emails you triggered (e.g. "Email to max@example.com: ...") so you can see delivery failures.

### `POST /api/jobs/{id}/retry` -> `202`
Only for `Failed` jobs (otherwise `409`). Resets `attempts` to 0 and re-queues.

## Quick tour with curl

```bash
# One cookie jar keeps the session. The CSRF token must be sent on every POST/PATCH/DELETE.
curl -c jar -b jar http://127.0.0.1:5000/api/csrf-token          # {"csrf_token": "T1"}
curl -c jar -b jar -H "X-CSRF-Token: T1" -H "Content-Type: application/json" \
     -d '{"name":"Lena","email":"lena@example.com","password":"password-123","role":"Team Lead"}' \
     http://127.0.0.1:5000/auth/register                          # returns a NEW token "T2"
curl -c jar -b jar -H "X-CSRF-Token: T2" -H "Content-Type: application/json" \
     -d '{"name":"Apollo"}' http://127.0.0.1:5000/api/projects
curl -b jar http://127.0.0.1:5000/api/projects
```
