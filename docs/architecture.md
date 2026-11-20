# Architecture

## Overview

AgileFlow uses a small, layered web architecture:

```text
Browser (HTML / CSS / vanilla JavaScript)
              |
              | JSON over HTTP
              v
        Flask application
       /       |        \
 Auth/API   Authorization  Report endpoint
       \       |        /
              v
      SQLAlchemy ORM
              |
              v
          SQLite DB

POST /api/reports --> persisted job --> background thread --> report result
```

## Main request flow

1. A user registers or logs in through `/auth/register` or `/auth/login`.
2. Flask verifies credentials and stores the authenticated user ID in a signed session.
3. The frontend calls `/api/me` and `/api/projects` to load the current identity and accessible projects.
4. Each project API checks both authentication and the user's project-level role.
5. SQLAlchemy persists the project, stories, tasks, memberships and report jobs in SQLite.

## Authorization model

- **Team Lead**: project owner; can edit/delete the project, manage membership, and create/update/delete stories and tasks.
- **Member**: can view the project, create/update stories and tasks, and assign tasks to project participants.
- **Viewer**: read-only project access.

During registration, users select Team Lead, Member, or Viewer. The backend—not the browser—enforces permissions. For production, Team Lead assignment should require administrator approval or an invitation.

## Hierarchical model

A Project has many User Stories. A User Story belongs to one Project and has many Tasks. A Task belongs to exactly one User Story. A project also has a Team Lead owner and zero or more project memberships. A task can optionally be assigned to a registered project participant.

## Asynchronous workflow

`POST /api/reports` persists a `BackgroundJob` with status `Queued`, then starts a background thread. The worker marks it `Running`, computes totals for projects visible to the requesting user, stores the text report and marks the job `Completed`. The client polls `GET /api/jobs/{job_id}`. The worker retries once after an exception and then stores a `Failed` state and error message.

The job record includes the requesting user ID. This both scopes the report and prevents another user from reading its result. The worker is intentionally in-process for a small local assignment; it is not durable across process restarts.

## Failure handling

- API validation errors return a JSON error and an appropriate HTTP status.
- Database exceptions should be handled by the request/worker transaction; the worker rolls back before retrying.
- A report job ends in `Completed` or `Failed`, so the client does not poll forever after a handled failure.
- A production implementation should add bounded exponential backoff, dead-letter handling, structured logs and operational monitoring.
