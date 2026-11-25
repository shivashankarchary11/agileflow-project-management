"""Allowed values used across the app (kept as plain strings so they are JSON friendly)."""

from __future__ import annotations

TEAM_LEAD = "Team Lead"
MEMBER = "Member"
VIEWER = "Viewer"

# Global role chosen at sign-up. It only decides who may *create projects*.
GLOBAL_ROLES = (TEAM_LEAD, MEMBER, VIEWER)
# Roles a Team Lead may grant when adding someone to a project.
PROJECT_MEMBER_ROLES = (MEMBER, VIEWER)

PROJECT_STATUSES = ("Active", "On Hold", "Completed")
WORK_STATUSES = ("To Do", "In Progress", "Done")  # stories and tasks
PRIORITIES = ("Low", "Medium", "High")

# Background job states
JOB_QUEUED = "Queued"
JOB_RUNNING = "Running"
JOB_COMPLETED = "Completed"
JOB_FAILED = "Failed"
JOB_STATUSES = (JOB_QUEUED, JOB_RUNNING, JOB_COMPLETED, JOB_FAILED)

JOB_PROGRESS_REPORT = "progress_report"
JOB_SEND_EMAIL = "send_email"

# Field length limits (validated, never silently truncated)
MAX_NAME = 80
MAX_EMAIL = 160
MAX_PROJECT_NAME = 120
MAX_TITLE = 160
MAX_DESCRIPTION = 2000
MIN_PASSWORD = 8
MAX_PASSWORD = 128
