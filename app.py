"""Backwards-compatible shim: ``python app.py`` still starts the app.

The application now lives in the ``agileflow`` package (see docs/architecture.md).
"""

from wsgi import app, main  # noqa: F401  (``app`` is re-exported for tools that import app:app)

if __name__ == "__main__":
    main()
