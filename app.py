from datetime import datetime, date
from threading import Thread
from time import sleep
from flask import Flask, jsonify, request, render_template, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import os
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-this-secret-before-deployment")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("COOKIE_SECURE", "0") == "1"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///agile_manager.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(160), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="Member")

class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, default="")
    status = db.Column(db.String(30), default="Active")
    deadline = db.Column(db.String(10), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    owner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    owner = db.relationship("User", foreign_keys=[owner_id])
    members = db.relationship("ProjectMember", backref="project", cascade="all, delete-orphan", lazy=True)
    stories = db.relationship("UserStory", backref="project", cascade="all, delete-orphan", lazy=True)

class ProjectMember(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="Member")
    user = db.relationship("User")
    __table_args__ = (db.UniqueConstraint("project_id", "user_id", name="uq_project_member"),)

class UserStory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False)
    title = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, default="")
    priority = db.Column(db.String(20), default="Medium")
    status = db.Column(db.String(30), default="To Do")
    tasks = db.relationship("Task", backref="story", cascade="all, delete-orphan", lazy=True)

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    story_id = db.Column(db.Integer, db.ForeignKey("user_story.id"), nullable=False)
    title = db.Column(db.String(160), nullable=False)
    assigned_to = db.Column(db.String(100), default="")
    status = db.Column(db.String(30), default="To Do")
    due_date = db.Column(db.String(10), default="")
    assigned_to_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    assignee = db.relationship("User", foreign_keys=[assigned_to_id])

class BackgroundJob(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    job_type = db.Column(db.String(40), nullable=False)
    status = db.Column(db.String(20), default="Queued")
    result = db.Column(db.Text, default="")
    error = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True, index=True)
    user = db.relationship("User")

def error(message, code=400):
    return jsonify({"error": message}), code

def project_role(project, user_id=None):
    user_id = user_id or session.get("user_id")
    if project.owner_id == user_id:
        return "Team Lead"
    membership = ProjectMember.query.filter_by(project_id=project.id, user_id=user_id).first()
    return membership.role if membership else None

def require_project_role(project, allowed):
    role = project_role(project)
    if role not in allowed:
        return error("You do not have permission to perform this action.", 403)
    return None

def resolve_assignee(project, data):
    """Resolve an assignee by user ID (preferred) or legacy display name."""
    raw_id = data.get("assigned_to_id")
    raw_name = (data.get("assigned_to") or "").strip()
    if raw_id in (None, "") and not raw_name:
        return None
    if raw_id not in (None, ""):
        try:
            user = db.session.get(User, int(raw_id))
        except (TypeError, ValueError):
            return None
    else:
        candidates = [m.user for m in project.members if m.user.name == raw_name]
        if project.owner and project.owner.name == raw_name:
            candidates.insert(0, project.owner)
        user = candidates[0] if candidates else None
    if not user:
        return None
    is_owner = user.id == project.owner_id
    is_member = ProjectMember.query.filter_by(project_id=project.id, user_id=user.id).first() is not None
    return user if is_owner or is_member else None

def project_json(p):
    stories = []
    for s in p.stories:
        stories.append({
            "id": s.id, "project_id": s.project_id, "title": s.title,
            "description": s.description, "priority": s.priority, "status": s.status,
            "tasks": [{"id": t.id, "story_id": t.story_id, "title": t.title,
                       "assigned_to": (t.assignee.name if t.assignee else t.assigned_to),
                       "assigned_to_id": t.assigned_to_id,
                       "status": t.status, "due_date": t.due_date}
                      for t in s.tasks]
        })
    members = [{"id": m.user.id, "name": m.user.name, "email": m.user.email, "role": m.role}
               for m in p.members]
    owner = p.owner or db.session.get(User, p.owner_id)
    if owner:
        members.insert(0, {"id": owner.id, "name": owner.name, "email": owner.email, "role": "Team Lead"})
    return {"id": p.id, "name": p.name, "description": p.description,
            "status": p.status, "deadline": p.deadline, "stories": stories,
            "members": members, "my_role": project_role(p)}

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            if request.path.startswith("/api/"):
                return error("Please log in to continue.", 401)
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped

@app.get("/")
@login_required
def home():
    return render_template("index.html", user_name=session.get("user_name", "User"), user_role=session.get("user_role", "Member"))

@app.get("/login")
def login():
    if session.get("user_id"):
        return redirect(url_for("home"))
    return render_template("login.html", mode="login")

@app.get("/register")
def register_page():
    if session.get("user_id"):
        return redirect(url_for("home"))
    return render_template("login.html", mode="register")

@app.post("/auth/register")
def register_user():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    if not name or not email or len(password) < 8:
        return error("Enter your name, a valid email, and a password with at least 8 characters.")
    if User.query.filter_by(email=email).first():
        return error("An account with this email already exists.", 409)
    # Role is explicitly selected at registration for this small-team assignment demo.
    # In production, Team Lead privileges should be granted by an administrator or invitation.
    requested_role = (data.get("role") or "Member").strip()
    if requested_role not in ("Team Lead", "Member", "Viewer"):
        return error("Choose Team Lead, Team Member, or Viewer.")
    role = requested_role
    user = User(name=name[:80], email=email[:160], password_hash=generate_password_hash(password), role=role)
    db.session.add(user); db.session.commit()
    session.clear(); session["user_id"] = user.id; session["user_name"] = user.name; session["user_role"] = user.role
    return jsonify({"message": "Account created.", "role": user.role}), 201

@app.post("/auth/login")
def login_user():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    user = User.query.filter_by(email=email).first()
    if not user or not check_password_hash(user.password_hash, data.get("password") or ""):
        return error("Incorrect email or password.", 401)
    session.clear(); session["user_id"] = user.id; session["user_name"] = user.name; session["user_role"] = user.role
    return jsonify({"message": "Logged in successfully.", "role": user.role})

@app.post("/auth/logout")
def logout_user():
    session.clear()
    return jsonify({"message": "Logged out."})

@app.get("/api/projects")
@login_required
def list_projects():
    uid = session["user_id"]
    projects = Project.query.filter((Project.owner_id == uid) | (Project.id.in_(db.session.query(ProjectMember.project_id).filter_by(user_id=uid)))).order_by(Project.id.desc()).all()
    return jsonify([project_json(p) for p in projects])

@app.post("/api/projects")
@login_required
def create_project():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return error("Project name is required.")
    if session.get("user_role") != "Team Lead": return error("Only a Team Lead can create projects.", 403)
    project_status = data.get("status", "Active")
    if project_status not in ("Active", "On Hold", "Completed"): return error("Invalid project status.")
    p = Project(name=name[:120], description=(data.get("description") or "")[:2000],
                status=project_status, deadline=data.get("deadline", ""), owner_id=session["user_id"])
    db.session.add(p)
    db.session.commit()
    return jsonify(project_json(p)), 201

@app.patch("/api/projects/<int:project_id>")
@login_required
def update_project(project_id):
    p = db.session.get(Project, project_id)
    if not p: return error("Project not found.", 404)
    denied = require_project_role(p, ["Team Lead"])
    if denied: return denied
    data = request.get_json(silent=True) or {}
    for key in ("name", "description", "status", "deadline"):
        if key in data: setattr(p, key, data[key])
    if not (p.name or "").strip(): return error("Project name cannot be empty.")
    if p.status not in ("Active", "On Hold", "Completed"): return error("Invalid project status.")
    db.session.commit()
    return jsonify(project_json(p))

@app.delete("/api/projects/<int:project_id>")
@login_required
def delete_project(project_id):
    p = db.session.get(Project, project_id)
    if not p: return error("Project not found.", 404)
    denied = require_project_role(p, ["Team Lead"])
    if denied: return denied
    db.session.delete(p)
    db.session.commit()
    return jsonify({"message": "Project deleted."})

@app.get("/api/me")
@login_required
def current_user():
    return jsonify({"id": session["user_id"], "name": session.get("user_name"), "role": session.get("user_role")})

@app.post("/api/projects/<int:project_id>/members")
@login_required
def add_project_member(project_id):
    project = db.session.get(Project, project_id)
    if not project: return error("Project not found.", 404)
    denied = require_project_role(project, ["Team Lead"])
    if denied: return denied
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    role = data.get("role", "Member")
    if role not in ("Member", "Viewer"): return error("Choose Member or Viewer.")
    user = User.query.filter_by(email=email).first()
    if not user: return error("No registered user found with that email. Ask them to create an account first.", 404)
    if user.id == project.owner_id: return error("The Team Lead already owns this project.")
    membership = ProjectMember.query.filter_by(project_id=project.id, user_id=user.id).first()
    if membership: membership.role = role
    else: db.session.add(ProjectMember(project_id=project.id, user_id=user.id, role=role))
    db.session.commit()
    return jsonify(project_json(project)), 201

@app.post("/api/projects/<int:project_id>/stories")
@login_required
def create_story(project_id):
    project = db.session.get(Project, project_id)
    if not project: return error("Project not found.", 404)
    denied = require_project_role(project, ["Team Lead", "Member"])
    if denied: return denied
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    if not title: return error("Story title is required.")
    priority = data.get("priority", "Medium")
    status = data.get("status", "To Do")
    if priority not in ("Low", "Medium", "High"): return error("Invalid story priority.")
    if status not in ("To Do", "In Progress", "Done"): return error("Invalid story status.")
    s = UserStory(project_id=project_id, title=title[:160],
                  description=(data.get("description") or "")[:2000],
                  priority=priority, status=status)
    db.session.add(s); db.session.commit()
    return jsonify({"id": s.id, "project_id": s.project_id, "title": s.title,
                    "description": s.description, "priority": s.priority, "status": s.status, "tasks": []}), 201

@app.patch("/api/stories/<int:story_id>")
@login_required
def update_story(story_id):
    s = db.session.get(UserStory, story_id)
    if not s: return error("User story not found.", 404)
    denied = require_project_role(s.project, ["Team Lead", "Member"])
    if denied: return denied
    data = request.get_json(silent=True) or {}
    for key in ("title", "description", "priority", "status"):
        if key in data: setattr(s, key, data[key])
    if not (s.title or "").strip(): return error("Story title cannot be empty.")
    if s.priority not in ("Low", "Medium", "High"): return error("Invalid story priority.")
    if s.status not in ("To Do", "In Progress", "Done"): return error("Invalid story status.")
    db.session.commit()
    return jsonify({"id": s.id, "project_id": s.project_id, "title": s.title,
                    "description": s.description, "priority": s.priority, "status": s.status})

@app.delete("/api/stories/<int:story_id>")
@login_required
def delete_story(story_id):
    s = db.session.get(UserStory, story_id)
    if not s: return error("User story not found.", 404)
    denied = require_project_role(s.project, ["Team Lead"])
    if denied: return denied
    db.session.delete(s); db.session.commit()
    return jsonify({"message": "Story and its tasks deleted."})

@app.post("/api/stories/<int:story_id>/tasks")
@login_required
def create_task(story_id):
    story = db.session.get(UserStory, story_id)
    if not story: return error("User story not found.", 404)
    denied = require_project_role(story.project, ["Team Lead", "Member"])
    if denied: return denied
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    if not title: return error("Task title is required.")
    assignee = resolve_assignee(story.project, data)
    if (data.get("assigned_to_id") not in (None, "") or (data.get("assigned_to") or "").strip()) and not assignee:
        return error("Assignee must be a member of this project.")
    assignee_name = assignee.name if assignee else ""
    task_status = data.get("status", "To Do")
    if task_status not in ("To Do", "In Progress", "Done"): return error("Invalid task status.")
    t = Task(story_id=story_id, title=title[:160],
             assigned_to=assignee_name[:100], assigned_to_id=assignee.id if assignee else None,
             status=task_status, due_date=data.get("due_date", ""))
    db.session.add(t); db.session.commit()
    return jsonify({"id": t.id, "story_id": t.story_id, "title": t.title,
                    "assigned_to": assignee.name if assignee else "", "assigned_to_id": t.assigned_to_id,
                    "status": t.status, "due_date": t.due_date}), 201

@app.patch("/api/tasks/<int:task_id>")
@login_required
def update_task(task_id):
    t = db.session.get(Task, task_id)
    if not t: return error("Task not found.", 404)
    denied = require_project_role(t.story.project, ["Team Lead", "Member"])
    if denied: return denied
    data = request.get_json(silent=True) or {}
    for key in ("title", "status", "due_date"):
        if key in data: setattr(t, key, data[key])
    if "assigned_to" in data or "assigned_to_id" in data:
        assignee = resolve_assignee(t.story.project, data)
        if (data.get("assigned_to_id") not in (None, "") or (data.get("assigned_to") or "").strip()) and not assignee:
            return error("Assignee must be a member of this project.")
        t.assigned_to = assignee.name if assignee else ""
        t.assigned_to_id = assignee.id if assignee else None
    if not (t.title or "").strip(): return error("Task title cannot be empty.")
    if t.status not in ("To Do", "In Progress", "Done"): return error("Invalid task status.")
    db.session.commit()
    return jsonify({"id": t.id, "story_id": t.story_id, "title": t.title,
                    "assigned_to": t.assignee.name if t.assignee else t.assigned_to,
                    "assigned_to_id": t.assigned_to_id, "status": t.status, "due_date": t.due_date})

@app.delete("/api/tasks/<int:task_id>")
@login_required
def delete_task(task_id):
    t = db.session.get(Task, task_id)
    if not t: return error("Task not found.", 404)
    denied = require_project_role(t.story.project, ["Team Lead"])
    if denied: return denied
    db.session.delete(t); db.session.commit()
    return jsonify({"message": "Task deleted."})

def generate_report(job_id):
    # Runs outside the request in a background thread; retries once on failure.
    with app.app_context():
        job = db.session.get(BackgroundJob, job_id)
        if not job: return
        job.status = "Running"; db.session.commit()
        for attempt in range(2):
            try:
                sleep(1)  # Simulates work that takes time.
                uid = job.user_id
                projects = Project.query.filter((Project.owner_id == uid) | (Project.id.in_(db.session.query(ProjectMember.project_id).filter_by(user_id=uid)))).all()
                project_ids = [p.id for p in projects]
                total_stories = UserStory.query.filter(UserStory.project_id.in_(project_ids)).count() if project_ids else 0
                story_ids = [row[0] for row in db.session.query(UserStory.id).filter(UserStory.project_id.in_(project_ids)).all()] if project_ids else []
                total_tasks = Task.query.filter(Task.story_id.in_(story_ids)).count() if story_ids else 0
                completed_tasks = Task.query.filter(Task.story_id.in_(story_ids), Task.status == "Done").count() if story_ids else 0
                lines = [f"AGILE TEAM PROGRESS REPORT", f"Generated: {datetime.utcnow().isoformat()} UTC",
                         f"Projects: {len(projects)}", f"User stories: {total_stories}",
                         f"Tasks: {total_tasks}", f"Completed tasks: {completed_tasks}",
                         f"Task completion: {(completed_tasks / total_tasks * 100):.1f}%" if total_tasks else "Task completion: 0.0%", ""]
                for p in projects:
                    lines.append(f"- {p.name}: {len(p.stories)} user stories")
                job.result = "\n".join(lines); job.status = "Completed"; job.error = ""
                db.session.commit()
                return
            except Exception as exc:
                db.session.rollback()
                job = db.session.get(BackgroundJob, job_id)
                job.error = str(exc)
                if attempt == 1:
                    job.status = "Failed"; db.session.commit()
        db.session.remove()

@app.post("/api/reports")
@login_required
def start_report():
    job = BackgroundJob(job_type="project_progress_report", status="Queued", user_id=session["user_id"])
    db.session.add(job); db.session.commit()
    Thread(target=generate_report, args=(job.id,), daemon=True).start()
    return jsonify({"job_id": job.id, "status": job.status,
                    "message": "Report generation started in the background."}), 202

@app.get("/api/jobs/<int:job_id>")
@login_required
def get_job(job_id):
    job = db.session.get(BackgroundJob, job_id)
    if not job or job.user_id != session["user_id"]: return error("Job not found.", 404)
    return jsonify({"id": job.id, "type": job.job_type, "status": job.status,
                    "result": job.result, "error": job.error,
                    "created_at": job.created_at.isoformat()})

@app.get("/api/health")
def health():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        # Lightweight migration for databases created by the earlier login-only version.
        from sqlalchemy import inspect, text
        inspector = inspect(db.engine)
        user_cols = {c["name"] for c in inspector.get_columns("user")}
        if "role" not in user_cols:
            db.session.execute(text("ALTER TABLE user ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'Member'"))
        project_cols = {c["name"] for c in inspector.get_columns("project")}
        first_user = db.session.execute(text("SELECT id FROM user ORDER BY id LIMIT 1")).scalar()
        if "owner_id" not in project_cols:
            db.session.execute(text("ALTER TABLE project ADD COLUMN owner_id INTEGER"))
            first_user = db.session.execute(text("SELECT id FROM user ORDER BY id LIMIT 1")).scalar()
            if first_user:
                db.session.execute(text("UPDATE project SET owner_id = :uid WHERE owner_id IS NULL"), {"uid": first_user})
        task_cols = {c["name"] for c in inspector.get_columns("task")}
        if "assigned_to_id" not in task_cols:
            db.session.execute(text("ALTER TABLE task ADD COLUMN assigned_to_id INTEGER"))
        job_cols = {c["name"] for c in inspector.get_columns("background_job")}
        if "user_id" not in job_cols:
            db.session.execute(text("ALTER TABLE background_job ADD COLUMN user_id INTEGER"))
            if first_user:
                db.session.execute(text("UPDATE background_job SET user_id = :uid WHERE user_id IS NULL"), {"uid": first_user})
        if User.query.count() and User.query.filter_by(role="Team Lead").count() == 0:
            first = User.query.order_by(User.id).first()
            first.role = "Team Lead"
        db.session.commit()
    app.run(debug=os.environ.get("FLASK_DEBUG", "0") == "1", port=5000)
