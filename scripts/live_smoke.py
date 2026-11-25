"""Live smoke test: boots the REAL server (python wsgi.py) with the real background worker thread
and drives it over plain HTTP (CSRF protection on, throwaway database, nothing in instance/ is touched).

Scenario 1: console email backend: register, project, story, task, board move, queued emails delivered
            by the worker, asynchronous report.
Scenario 2: SMTP server unreachable: the email job retries with backoff, ends Failed, can be retried.

Usage (from the repo root, with the virtualenv active):

    python scripts/live_smoke.py
"""

import http.cookiejar
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable


class Browser:
    def __init__(self, base):
        self.base = base
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        self.csrf = None

    def page(self, path):
        with self.opener.open(self.base + path) as r:
            html = r.read().decode()
            m = re.search(r'name="csrf-token" content="([^"]+)"', html)
            if m:
                self.csrf = m.group(1)
            return r.status, html

    def call(self, method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        if method != "GET" and self.csrf:
            req.add_header("X-CSRF-Token", self.csrf)
        try:
            with self.opener.open(req) as r:
                payload = json.loads(r.read() or b"null")
                status = r.status
        except urllib.error.HTTPError as e:
            payload = json.loads(e.read() or b"null")
            status = e.code
        if isinstance(payload, dict) and "csrf_token" in payload:
            self.csrf = payload["csrf_token"]
        return status, payload


def check(label, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + (f"  [{extra}]" if extra and not cond else ""))
    if not cond:
        check.failed += 1


check.failed = 0


def wait_for(fn, timeout=20):
    end = time.time() + timeout
    while time.time() < end:
        value = fn()
        if value:
            return value
        time.sleep(0.3)
    return None


def run_server(port, extra_env):
    tmp = tempfile.mkdtemp(prefix="agileflow_smoke_")
    env = {**os.environ, "DATABASE_URL": "sqlite:///" + os.path.join(tmp, "smoke.db").replace("\\", "/"),
           "PORT": str(port), "WORKER_POLL_SECONDS": "0.2", "SECRET_KEY": "smoke-secret-key-1234567890", **extra_env}
    log_path = os.path.join(tmp, "server.log")
    log = open(log_path, "w")
    proc = subprocess.Popen([PY, "wsgi.py"], cwd=REPO, env=env, stdout=log, stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{port}"
    ok = wait_for(lambda: _up(base), 30)
    return proc, base, log, log_path, ok


def _up(base):
    try:
        with urllib.request.urlopen(base + "/api/health", timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def stop(proc, log):
    proc.terminate()
    try:
        proc.wait(10)
    except subprocess.TimeoutExpired:
        proc.kill()
    log.close()


def scenario_happy_path():
    print("\n=== Scenario 1: console email backend, real worker thread, CSRF on ===")
    proc, base, log, log_path, up = run_server(5057, {"MAIL_BACKEND": "console"})
    try:
        check("server booted (migrations auto-applied)", up)
        if not up:
            return
        lead, member = Browser(base), Browser(base)
        s, html = lead.page("/register")
        check("register page renders with CSRF token", s == 200 and lead.csrf)
        s, _ = lead.call("POST", "/auth/register", {"name": "Lena Lead", "email": "lena@example.com", "password": "password-123", "role": "Team Lead"})
        check("lead registers (201)", s == 201)
        member.page("/register")
        s, _ = member.call("POST", "/auth/register", {"name": "Max Member", "email": "max@example.com", "password": "password-123", "role": "Member"})
        check("member registers (201)", s == 201)
        member_id = member.call("GET", "/api/me")[1]["id"]

        # CSRF is enforced on the real server
        raw = Browser(base)
        s, _ = raw.call("POST", "/auth/login", {"email": "lena@example.com", "password": "password-123"})
        check("login without CSRF token is rejected (403)", s == 403)

        s, _ = lead.page("/")
        check("dashboard page renders for lead", s == 200)
        for asset in ("css/app.css", "js/app.js", "js/board.js"):
            with urllib.request.urlopen(f"{base}/static/{asset}") as r:
                check(f"static {asset} served with CSP header", r.status == 200 and "script-src 'self'" in r.headers["Content-Security-Policy"])

        s, project = lead.call("POST", "/api/projects", {"name": "Live Project", "deadline": "2031-01-01"})
        check("create project (201)", s == 201)
        pid = project["id"]
        s, _ = lead.call("POST", f"/api/projects/{pid}/members", {"email": "max@example.com", "role": "Member"})
        check("add member (201)", s == 201)
        s, story = member.call("POST", f"/api/projects/{pid}/stories", {"title": "Sign in", "priority": "High"})
        check("member creates story (201)", s == 201)
        s, t1 = member.call("POST", f"/api/stories/{story['id']}/tasks", {"title": "Login form"})
        s, t2 = lead.call("POST", f"/api/stories/{story['id']}/tasks", {"title": "Reset flow", "assigned_to_id": member_id})
        check("lead assigns a task to the member (201)", s == 201)
        s, moved = member.call("PATCH", f"/api/tasks/{t1['id']}/move", {"status": "Done"})
        check("drag-style status move works", s == 200 and moved["status"] == "Done")
        s, board = lead.call("GET", f"/api/projects/{pid}/board")
        check("board shows Done=1, To Do=1", [len(board["columns"][c]) for c in ("To Do", "In Progress", "Done")] == [1, 0, 1])

        # The REAL worker thread should deliver the queued emails in the background
        def all_emails_done():
            items = lead.call("GET", "/api/jobs")[1]["items"]
            return items and all(j["status"] == "Completed" for j in items) and items
        jobs = wait_for(all_emails_done)
        check("worker thread delivered the queued emails (jobs Completed)", bool(jobs), str(lead.call("GET", "/api/jobs")[1]))

        s, job = member.call("POST", "/api/reports", {})
        check("report accepted (202, Queued)", s == 202 and job["status"] == "Queued")
        done = wait_for(lambda: (lambda j: j if j["status"] in ("Completed", "Failed") else None)(member.call("GET", f"/api/jobs/{job['id']}")[1]))
        check("report completed in background", done and done["status"] == "Completed")
        check("report content correct", done and "Live Project" in done["result"] and "Overall completion: 50.0%" in done["result"])
    finally:
        stop(proc, log)
        text = open(log_path).read()
        emails = re.findall(r"EMAIL \(console backend\)\s+To: (\S+)\s+Subject: (.+)", text)
        print("  console emails logged by the worker:")
        for to, subject in emails:
            print(f"    -> {to}: {subject}")
        check("console backend logged 3 emails (member added, task assigned, report ready)", len(emails) == 3, str(emails))


def scenario_smtp_down():
    print("\n=== Scenario 2: SMTP server unreachable -> retries with backoff -> Failed -> manual retry ===")
    proc, base, log, log_path, up = run_server(5058, {"MAIL_BACKEND": "smtp", "SMTP_HOST": "127.0.0.1", "SMTP_PORT": "1",
                                                      "JOB_BACKOFF_BASE_SECONDS": "0.3", "SMTP_TIMEOUT_SECONDS": "2"})
    try:
        check("server booted", up)
        if not up:
            return
        lead, member = Browser(base), Browser(base)
        lead.page("/register")
        lead.call("POST", "/auth/register", {"name": "Lena Lead", "email": "lena@example.com", "password": "password-123", "role": "Team Lead"})
        member.page("/register")
        member.call("POST", "/auth/register", {"name": "Max Member", "email": "max@example.com", "password": "password-123", "role": "Member"})
        pid = lead.call("POST", "/api/projects", {"name": "P"})[1]["id"]
        s, _ = lead.call("POST", f"/api/projects/{pid}/members", {"email": "max@example.com"})
        check("add member still succeeds while mail is down (email is async)", s == 201)

        failed = wait_for(lambda: next((j for j in lead.call("GET", "/api/jobs")[1]["items"] if j["status"] == "Failed"), None))
        check("email job ends Failed after exhausting attempts", bool(failed))
        if failed:
            check("attempts == max_attempts (3)", failed["attempts"] == failed["max_attempts"] == 3, str(failed))
            print("    recorded error:", failed["error"])
            check("last error recorded (exception type + message)", ":" in failed["error"] and len(failed["error"]) > 5, failed["error"])
            s, r = lead.call("POST", f"/api/jobs/{failed['id']}/retry")
            check("manual retry accepted (202) and attempts reset", s == 202 and r["attempts"] == 0)
            again = wait_for(lambda: next((j for j in lead.call("GET", "/api/jobs")[1]["items"] if j["id"] == failed["id"] and j["status"] == "Failed"), None))
            check("still-broken mail fails again after the retry budget", bool(again))
    finally:
        stop(proc, log)
        text = open(log_path).read()
        warnings = len(re.findall(r"failed attempt \d/3, retrying", text))
        print(f"  worker log shows {warnings} 'retrying' warnings")
        check("retry warnings were logged (logging not disabled by migrations)", warnings >= 2, text[-800:])


scenario_happy_path()
scenario_smtp_down()
print("\nRESULT:", "ALL LIVE CHECKS PASSED" if not check.failed else f"{check.failed} CHECK(S) FAILED")
sys.exit(1 if check.failed else 0)
