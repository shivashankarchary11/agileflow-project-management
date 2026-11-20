# AgileFlow — Small-Team Agile Project Management

AgileFlow is a full-stack web application for a small team (3–10 people). It models work hierarchically as **Project → User Story → Task**, supports project membership and role-based permissions, persists data in SQLite, and generates progress reports in the background.

## Features

- Account registration and login with Werkzeug password hashing.
- During registration, users choose Team Lead, Team Member, or Viewer. For this assignment demo, role selection is open; in production, Team Lead privileges should be granted through an administrator-controlled invitation or approval process.
- Team Leads create projects and invite existing users by email as Members or Viewers.
- Project members see only projects they own or have been added to.
- Team Leads and Members create stories and tasks, update statuses, and assign tasks to project members.
- Viewers have read-only project access.
- Project dashboard with project, story, task and completion summaries.
- Asynchronous progress report generation, persisted job state, status polling and one retry after a processing failure.
- JSON REST API documented in `docs/api-documentation.md`.

## Technology

| Layer | Technology |
|---|---|
| Frontend | HTML, CSS, vanilla JavaScript |
| Backend | Python 3, Flask |
| API | Flask JSON REST endpoints |
| ORM / persistence | Flask-SQLAlchemy, SQLite |
| Password storage | Werkzeug PBKDF2 password hashing |
| Async workflow | Background Python thread + persisted `background_job` record |

## Run locally (Windows)

1. Install Python 3.10 or newer.
2. Extract the ZIP and open the **inner `agile-project-manager` folder** in VS Code.
3. Open a terminal in that folder. Confirm `dir` shows `app.py` and `requirements.txt`.
4. Create a virtual environment:

   ```cmd
   py -m venv .venv
   .venv\Scripts\activate
   ```

5. Install dependencies:

   ```cmd
   python -m pip install -r requirements.txt
   ```

6. Set a local secret key (use a different random value for each deployment):

   ```cmd
   set SECRET_KEY=replace-this-with-a-long-random-secret
   ```

7. Start the server:

   ```cmd
   python app.py
   ```

8. Visit `http://127.0.0.1:5000` and choose **Create one** to register.

Choose the Team Lead role when registering the account that will create projects. Register additional users as Team Members or Viewers. The Team Lead can add them to a project from the project details panel.

The SQLite database is created automatically at `instance/agile_manager.db` on first run. Back up this file if you need to preserve local project data.

## Typical workflow

1. Register an account and explicitly select **Team Lead** as its role.
2. Register each teammate with their own email address.
3. Sign in as Team Lead, create a project, then choose **Add teammate** and enter a teammate's registered email.
4. A Team Lead or Member creates a User Story inside the project.
5. Add one or more Tasks under the story and select a project teammate as the assignee.
6. Update story/task status as work progresses. Viewers can follow progress but cannot edit.
7. Use the report action to generate a progress report asynchronously.

## Project documentation

- [Architecture and async workflow](docs/architecture.md)
- [API documentation](docs/api-documentation.md)
- [Database schema](docs/database-schema.md)
- [Design decisions, tradeoffs and security](docs/design-decisions.md)

## Tests

Install the test dependency and run the test suite:

```cmd
python -m pip install pytest
pytest -q
```

## Async workflow and limitations

`POST /api/reports` creates a `Queued` job record and starts a background thread. The worker changes the job to `Running`, computes a report for only the requesting user's accessible projects, stores the report and marks the job `Completed`. On an exception it rolls back and retries once; after the second failure it records `Failed` and the error. The frontend polls `GET /api/jobs/{job_id}`.

This in-process worker is intentionally simple for a small-team assignment. A process restart can interrupt an in-flight job, and multiple production workers would need coordination. A production deployment should use a durable queue such as Celery or RQ with Redis, bounded retries/backoff, idempotency and monitoring.

## Security notes

- Passwords are stored as hashes, never as plaintext.
- Authentication uses Flask's signed session cookie with `HttpOnly` and `SameSite=Lax` settings.
- API endpoints check authentication and project membership/role on the server; hiding a button in the frontend is not treated as authorization.
- Users explicitly select their role during registration in this demo. For production, restrict Team Lead assignment to administrator approval or secure invitations.
- Report jobs are scoped to the requesting user, and users cannot read another user's job by guessing its ID.
- Task assignees must belong to the project (or be its Team Lead).
- Input fields have basic required-value, length and enum validation; SQLAlchemy parameterizes database operations.
- For production: use a strong environment-provided `SECRET_KEY`, HTTPS, secure cookies, CSRF protection for cookie-authenticated state-changing requests, login rate limiting, audit logs, database migrations, and disable Flask debug mode. Do not expose the development server directly to the internet.

## AI usage

AI assistance was used for scaffolding, debugging support, code review suggestions and documentation drafting. The developer should run the application and tests, review the implementation, and be prepared to explain the data model, authorization checks, API routes, async worker and tradeoffs.

## What I would improve next

- Replace the in-process thread with Celery/RQ and Redis for durable background jobs.
- Add CSRF protection, rate limiting, audit logs, password reset and email invitations.
- Add activity history, comments, labels, sprint planning, search and filtering.
- Add pagination and more detailed reporting.
- Add Alembic migrations, structured logging, CI, Docker and deployment configuration.
- Consider PostgreSQL for higher concurrency and multi-instance deployments.
