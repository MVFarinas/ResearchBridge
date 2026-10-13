# ResearchBridge backend image: the Django web process (gunicorn) and, from the same image,
# the Procrastinate worker. No hosting account is configured; see docs/phase-notes/phase-2.md.
#
# Build from the repository root (the image needs libs/rbcore too):
#   docker build -f backend/Dockerfile -t researchbridge-backend .
# Run (DATABASE_URL and DJANGO_SECRET_KEY are required):
#   web:     docker run -p 8000:8000 -e DATABASE_URL=... -e DJANGO_SECRET_KEY=... researchbridge-backend
#   migrate: docker run ... researchbridge-backend django-admin migrate
#   worker:  docker run ... researchbridge-backend django-admin procrastinate worker
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DJANGO_SETTINGS_MODULE=rb_backend.settings \
    DJANGO_STATIC_ROOT=/app/staticfiles \
    RB_DATA_DIR=/app/data

WORKDIR /app

# Pinned third-party dependencies first (cached until the lock changes). The two local
# packages are listed as editables in the lock; they are installed from source below,
# and `pip check` then fails the build if the lock is missing anything.
COPY requirements/backend.txt /tmp/backend.txt
RUN grep -v '^-e ' /tmp/backend.txt > /tmp/pinned.txt \
    && pip install --no-deps -r /tmp/pinned.txt

# The shared library and the backend, without re-resolving dependencies.
COPY libs/rbcore /src/libs/rbcore
COPY backend /src/backend
RUN pip install --no-deps /src/libs/rbcore /src/backend \
    && pip check

# Static files for the admin, collected at build time (served by WhiteNoise).
RUN DJANGO_SECRET_KEY=collectstatic-only django-admin collectstatic --no-input

# Run as an unprivileged user; downloads go to /app/data (mount a volume in production).
RUN useradd --create-home --uid 10001 app && mkdir -p /app/data && chown app /app/data
USER app

EXPOSE 8000
CMD ["sh", "-c", "exec gunicorn rb_backend.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers ${WEB_CONCURRENCY:-2} --access-logfile -"]
