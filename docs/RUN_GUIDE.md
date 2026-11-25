# Run it from scratch: step by step (Windows)

No prior knowledge assumed. Follow the steps in order; each one says what it does and what you should see.

## 0. What you need installed

| Tool | Check it with | If missing |
|---|---|---|
| **Python 3.14** | `py -3.14 --version` should print `Python 3.14.x` | Install from https://www.python.org/downloads/ (tick "Add python.exe to PATH") |
| **Git** | `git --version` | https://git-scm.com/download/win |
| VS Code (optional) | | https://code.visualstudio.com |
| Node.js 22+ (optional, only for the browser smoke test) | `node --version` | https://nodejs.org |

## 1. Get the code

```cmd
git clone https://github.com/shivashankarchary11/agileflow-project-management.git
cd agileflow-project-management
git checkout phase-1-to-7-implementation
```
(`git checkout` is only needed until this branch has been merged into `main`.)

## 2. Create a private Python environment

```cmd
py -3.14 -m venv .venv
.venv\Scripts\activate
```
Your prompt now starts with `(.venv)`. It means "use the Python packages of this project only". In PowerShell, if activation is blocked, run `Set-ExecutionPolicy -Scope Process Bypass` first.

## 3. Install the packages

```cmd
python -m pip install -r requirements-dev.txt
```
Takes about a minute. (`requirements.txt` is the app only; `requirements-dev.txt` adds the test tools.)

## 4. Prove everything works (recommended)

```cmd
python -m pytest
```
Expect `207 passed` in about 15 seconds. This never touches your data.

## 5. Start the app

```cmd
python wsgi.py
```
What happens: the database file `instance\agileflow.db` is created and the tables are built automatically, the background worker starts, and the log says `Running on http://127.0.0.1:5000`. Leave this window open; press `Ctrl+C` to stop.

Open **http://127.0.0.1:5000** in your browser.

## 6. Use it

1. Click **Create an account**. Choose role **Team Lead**.
2. Click **+ New**, create a project.
3. Open the **Stories** tab: **+ New user story**, then **+ Add task** under it.
4. Open the **Board** tab: drag a card to another column. A green message pops up.
5. To try teamwork, open a **private/incognito window**, register `member@example.com` as **Team Member**. In the first window: **Team** tab, **+ Add teammate**, `member@example.com`.
6. Look at the terminal where the app runs: you will see the **emails** the app "sent" (`EMAIL (console backend)`). They are written to the log so no mail server is needed.
7. Click **Reports & jobs** (left), **Generate progress report**, wait for **Completed**, click **Download**.

## 7. Optional: send real emails

Set these in the same terminal **before** `python wsgi.py` (example uses Gmail-style SMTP; use your own server and an app password):

```cmd
set MAIL_BACKEND=smtp
set SMTP_HOST=smtp.example.com
set SMTP_PORT=587
set SMTP_USER=you@example.com
set SMTP_PASSWORD=your-app-password
set MAIL_FROM=AgileFlow ^<you@example.com^>
python wsgi.py
```
If the mail server is unreachable, nothing breaks: the email job retries 3 times (2 s, 4 s apart), then shows as **Failed** in **Reports & jobs**, with the error and a **Retry** button.

## 8. Optional: check the real server and the real browser

```cmd
python scripts\live_smoke.py
node scripts\ui_smoke\run.mjs
```
The first starts the server itself and tests it over HTTP, including a broken mail server. The second opens a hidden Edge/Chrome and clicks through the UI (47 checks). Both use a throwaway database.

## 9. Optional: Docker

```cmd
set SECRET_KEY=paste-a-long-random-string-here
docker compose up --build
```
Open http://localhost:8000. (Docker was not available on the author's machine, so the image is built in CI.)

## 10. Reset or move your data

- All data lives in the single file `instance\agileflow.db`. Stop the app and delete the file to start fresh; copy it to back up.
- `instance\agile_manager.db` (if you have it) belongs to the **old** version and is ignored. It may even contain test users from the old test-suite. You can delete it.

## Everyday commands

| I want to | Command |
|---|---|
| Start the app | `python wsgi.py` |
| Run the tests | `python -m pytest` |
| See test coverage | `python -m pytest --cov=agileflow` |
| Change the database after editing a model | `python -m flask --app wsgi db migrate -m "what changed"` then `python -m flask --app wsgi db upgrade` |
| Use another port | `set PORT=5050` then `python wsgi.py` |
| Show more detail in the log | `set LOG_LEVEL=DEBUG` |

## When something goes wrong

| Symptom | Cause and fix |
|---|---|
| `flask ...`, `pytest ...` or `ruff ...` prints nothing and does nothing | Some managed Windows machines block the small `.exe` launchers that pip creates. Use the `python -m` form instead: `python -m flask --app wsgi db upgrade`, `python -m pytest`, `python -m ruff check .` |
| `py -3.14` not recognised | Python 3.14 is not installed, or the launcher is missing. Reinstall from python.org and tick the launcher option. |
| `ImportError ... PyInit__collections_cy` | SQLAlchemy 2.1 got installed. Run `python -m pip install -r requirements.txt` (it pins 2.0.58). |
| `Address already in use` | Another program uses port 5000: `set PORT=5050`, then run again. |
| You can log in but get logged out immediately | You set `COOKIE_SECURE=1` while using plain `http://`. Unset it for local use. |
| `RuntimeError: SECRET_KEY must be set` | You set `APP_ENV=production`. Set a long random `SECRET_KEY`, or unset `APP_ENV`. |
| "Missing or invalid CSRF token" from a script | Fetch `GET /api/csrf-token` with the same cookie jar and send it as `X-CSRF-Token` (see API docs). |
| Emails do not arrive | Default backend is `console` (prints to the terminal). Set `MAIL_BACKEND=smtp` and the `SMTP_*` values. |
