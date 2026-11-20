# Design decisions, tradeoffs and security

## Design decisions

- **Relational hierarchy:** Project, UserStory and Task are separate entities with foreign-key relationships rather than embedding child objects in a project JSON blob. This supports independent CRUD operations and clear ownership.
- **Project membership:** A `project_member` join table stores project-level roles. A person can have different permissions on different projects.
- **Task assignment:** Tasks reference registered users by ID; the legacy display-name field is retained for compatibility. The API verifies that the selected assignee belongs to the project.
- **SQLite:** Chosen because the assignment targets a small team and requires easy local setup. PostgreSQL would be preferable for production concurrency and multi-instance hosting.
- **Vanilla JavaScript:** Avoids a frontend build chain and keeps the demo easy to run. React or another component framework could help as the UI grows.
- **In-process background thread:** Demonstrates asynchronous work and persisted job states without requiring Redis. It is not durable if the server stops while a job is running.

## Security considerations

- Passwords are hashed using Werkzeug's password hashing helpers.
- Flask session cookies are HttpOnly and SameSite=Lax.
- Backend routes enforce authentication and project roles; client-side controls are only a usability layer.
- Registration allows explicit selection of Team Lead, Member, or Viewer for this assignment demo. Production systems should restrict Team Lead assignment to administrator approval or invitations.
- Background report records are associated with a user, and job reads check ownership.
- Task assignees must be project participants.
- Basic validation is applied to required fields, lengths and enum values.

## Known limitations / production hardening

This assignment build is a local development application, not a hardened internet-facing service. Before public deployment, add CSRF tokens for cookie-authenticated write requests, login throttling/rate limiting, email verification and password reset, HTTPS and Secure cookies, stronger audit logging, a secret manager, Alembic migrations, structured logs, and a durable job queue. Disable debug mode and use a production WSGI server. SQLite foreign-key enforcement should also be enabled explicitly for every connection.


### Role selection
For the assignment demo, registration allows a user to select Team Lead, Team Member, or Viewer. This makes the workflow easy to demonstrate. In a production deployment, Team Lead privileges should not be self-assigned through public registration; use administrator approval or expiring invitations instead.
