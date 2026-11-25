FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=production \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt gunicorn==27.0.1

COPY . .

# Run as a non-root user; only instance/ (the SQLite file) needs to be writable.
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/instance \
    && chown -R appuser /app/instance
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status == 200 else 1)"

# Apply migrations (without starting the background worker), then serve.
# One process with several threads: the background worker thread lives in that process.
CMD ["sh", "-c", "WORKER_ENABLED=0 python -m flask --app wsgi db upgrade && exec gunicorn --bind 0.0.0.0:8000 --workers 1 --threads 4 wsgi:app"]
