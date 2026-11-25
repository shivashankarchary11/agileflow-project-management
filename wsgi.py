"""Entry point.

    python wsgi.py                      # development server (applies DB migrations first)
    python -m flask --app wsgi db upgrade         # apply DB migrations only
    gunicorn wsgi:app                   # production-style server
"""

import os

from agileflow import create_app

app = create_app()


def main() -> None:
    from flask_migrate import upgrade

    with app.app_context():
        upgrade()  # create/update tables so a fresh clone just works
    app.run(
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "5000")),
        debug=os.environ.get("FLASK_DEBUG", "0") == "1",
    )


if __name__ == "__main__":
    main()
