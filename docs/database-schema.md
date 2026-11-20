# Database schema

Database: SQLite (`instance/agile_manager.db`). SQLAlchemy creates the tables on startup. The app contains lightweight compatibility steps for databases created by earlier versions; a production system should use Alembic migrations.

| Table | Important columns | Purpose |
|---|---|---|
| `user` | `id` PK, `name`, `email` UNIQUE, `password_hash`, `role` | Registered user and workspace role |
| `project` | `id` PK, `name`, `description`, `status`, `deadline`, `created_at`, `owner_id` FK → user | Project owned by a Team Lead |
| `project_member` | `id` PK, `project_id` FK → project, `user_id` FK → user, `role`, UNIQUE(project_id,user_id) | Membership and project-level role |
| `user_story` | `id` PK, `project_id` FK → project, `title`, `description`, `priority`, `status` | User story within a project |
| `task` | `id` PK, `story_id` FK → user_story, `title`, `assigned_to`, `assigned_to_id` FK → user, `status`, `due_date` | Task under a story; optional registered assignee |
| `background_job` | `id` PK, `job_type`, `status`, `result`, `error`, `created_at`, `user_id` FK → user | Persisted async report job and result |

## Relationships

- `user.id` 1 → many `project.owner_id` (projects owned by a Team Lead)
- `project.id` 1 → many `project_member.project_id`
- `user.id` 1 → many `project_member.user_id`
- `project.id` 1 → many `user_story.project_id`
- `user_story.id` 1 → many `task.story_id`
- `user.id` 1 → many optional `task.assigned_to_id`
- `user.id` 1 → many `background_job.user_id`

The core work hierarchy is **Project → User Story → Task**. Project membership is separate from global account role so a user can be a Member on one project and a Viewer on another.

## Enumerated values

- Workspace role: `Team Lead`, `Member`, `Viewer`
- Project role: owner (`Team Lead`), `Member`, `Viewer`
- Project status: `Active`, `On Hold`, `Completed`
- Story/task status: `To Do`, `In Progress`, `Done`
- Story priority: `Low`, `Medium`, `High`
- Background job status: `Queued`, `Running`, `Completed`, `Failed`

## Integrity and tradeoffs

SQLAlchemy relationships and foreign keys represent the hierarchy. Project and story deletion cascade to their child work items. Membership uniqueness prevents duplicate membership rows. Task assignment is checked against project membership by the API. SQLite is sufficient for a 3–10 person local demonstration; PostgreSQL is a better fit for multiple app instances and heavier concurrent writes.
