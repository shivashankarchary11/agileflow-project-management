# REST API documentation

Base URL: `http://127.0.0.1:5000`. All API request and response bodies are JSON. Authenticated routes use the Flask session cookie. Errors use `{"error":"message"}`.

## Authentication

| Method | Endpoint | Description |
|---|---|---|
| POST | `/auth/register` | Create account with an explicitly selected Team Lead, Member, or Viewer role |
| POST | `/auth/login` | Authenticate and create session |
| POST | `/auth/logout` | Clear current session |
| GET | `/api/me` | Return current user ID, name and workspace role |

Registration example:
```json
{"name":"Asha Rao","email":"asha@example.com","password":"strong-password","role":"Member"}
```

## Projects and membership

| Method | Endpoint | Description | Permission |
|---|---|---|---|
| GET | `/api/projects` | List projects visible to current user, including nested stories/tasks and members | Any signed-in user |
| POST | `/api/projects` | Create project | Workspace Team Lead |
| PATCH | `/api/projects/{project_id}` | Update project fields | Project Team Lead |
| DELETE | `/api/projects/{project_id}` | Delete project and descendants | Project Team Lead |
| POST | `/api/projects/{project_id}/members` | Add or update a registered user's project role | Project Team Lead |

Create project:
```json
{"name":"Website Revamp","description":"Improve the company website","status":"Active","deadline":"2026-12-15"}
```

Add member:
```json
{"email":"asha@example.com","role":"Member"}
```
Allowed project roles are `Member` and `Viewer`; the project owner is the Team Lead.

## User stories

| Method | Endpoint | Description | Permission |
|---|---|---|---|
| POST | `/api/projects/{project_id}/stories` | Create a story under a project | Team Lead or Member |
| PATCH | `/api/stories/{story_id}` | Update title, description, priority or status | Team Lead or Member |
| DELETE | `/api/stories/{story_id}` | Delete story and its tasks | Team Lead |

Create story:
```json
{"title":"As a user, I want to sign in","description":"Allow secure account access","priority":"High","status":"To Do"}
```

## Tasks

| Method | Endpoint | Description | Permission |
|---|---|---|---|
| POST | `/api/stories/{story_id}/tasks` | Create task under a story | Team Lead or Member |
| PATCH | `/api/tasks/{task_id}` | Update task title, assignee, status or due date | Team Lead or Member |
| DELETE | `/api/tasks/{task_id}` | Delete task | Team Lead |

Create task:
```json
{"title":"Build login form","assigned_to_id":2,"status":"In Progress","due_date":"2026-11-25"}
```

`assigned_to_id` is the ID of a user already added to the project (including its Team Lead); omit it or send an empty value to leave the task unassigned. For backwards compatibility, the API also accepts `assigned_to` as a display name. The API rejects assignees who are not project participants.

## Background reports

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/reports` | Queue progress report generation; returns HTTP 202 and a job ID |
| GET | `/api/jobs/{job_id}` | Read status/result of the current user's job |

Start report response:
```json
{"job_id":1,"status":"Queued","message":"Report generation started in the background."}
```

Poll the job until status is `Completed` or `Failed`. A completed response contains the report text in `result`. Job results are scoped to the user who created the job.

## Utility

| Method | Endpoint | Description | Auth |
|---|---|---|---|
| GET | `/api/health` | Basic health response | Public |

## Status codes

- `200`: successful read/update
- `201`: resource created
- `202`: asynchronous job accepted
- `400`: invalid input
- `401`: authentication required or invalid credentials
- `403`: authenticated user lacks permission
- `404`: resource not found or not visible to current user
- `409`: duplicate email/account conflict
