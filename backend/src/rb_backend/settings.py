"""Django settings for the ResearchBridge backend, read from the environment.

Every value that differs between machines comes from an environment variable
(see ``.env.example`` at the repository root); nothing secret is in code.

* ``DJANGO_DEBUG`` (default false). With debug on and no
  ``DJANGO_SECRET_KEY``, a fixed, clearly insecure development key is used;
  with debug off the key is required.
* ``DJANGO_ALLOWED_HOSTS`` and ``DJANGO_CSRF_TRUSTED_ORIGINS``: comma lists.
* ``DJANGO_SECURE_SSL_REDIRECT`` (default false) and
  ``DJANGO_TRUST_PROXY_SSL_HEADER`` (default false; set it only behind a
  platform proxy that sets ``X-Forwarded-Proto``).
* ``DJANGO_STATIC_ROOT``: where ``collectstatic`` writes (default
  ``backend/staticfiles``).
* ``RB_LOG_LEVEL``: root log level (default ``INFO``).
* ``DATABASE_URL``, or ``RB_DB_HOST``/``RB_DB_PORT``/``RB_DB_NAME``/
  ``RB_DB_USER``/``RB_DB_PASSWORD``, and ``RB_DB_CONN_MAX_AGE`` (see
  :mod:`rb_backend.envconfig`).
* ``RB_DATA_DIR``: where downloads and the HTTP cache live (gitignored).
* ``RB_RECHECK_MAX_AGE_DAYS`` and ``RB_RECHECK_BATCH_SIZE``: how often the
  worker's periodic task re-checks stored PMC articles, and how many per run.
"""

from __future__ import annotations

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

from rb_backend.envconfig import (
    database_from_env,
    get_bool,
    get_int,
    get_list,
    get_str,
    proxy_ssl_header,
)

_ENV = os.environ
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# --- Core -------------------------------------------------------------------
DEBUG = get_bool(_ENV, "DJANGO_DEBUG", default=False)

# A development key is acceptable only with debug on; production must set one.
_DEV_SECRET_KEY = "django-insecure-researchbridge-local-development-only"  # noqa: S105
SECRET_KEY = get_str(_ENV, "DJANGO_SECRET_KEY") or (_DEV_SECRET_KEY if DEBUG else "")
if not SECRET_KEY:
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set when DJANGO_DEBUG is false")

ALLOWED_HOSTS = get_list(_ENV, "DJANGO_ALLOWED_HOSTS", ["localhost", "127.0.0.1"] if DEBUG else [])
CSRF_TRUSTED_ORIGINS = get_list(_ENV, "DJANGO_CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    # Procrastinate must come before the apps whose tasks it discovers.
    "procrastinate.contrib.django",
    "rb_backend.corpus",
    "rb_backend.annotations",
    "rb_backend.ingestion",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "rb_backend.urls"
WSGI_APPLICATION = "rb_backend.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# --- Database -----------------------------------------------------------------
DATABASES = {"default": database_from_env(_ENV)}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Internationalisation -----------------------------------------------------
LANGUAGE_CODE = "en-gb"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# --- Static files (admin only for now), served by WhiteNoise in production ---
STATIC_URL = "static/"
STATIC_ROOT = Path(get_str(_ENV, "DJANGO_STATIC_ROOT", str(BASE_DIR / "staticfiles")))
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if DEBUG
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        )
    },
}

# --- Security (cookies are HTTPS-only outside development) --------------------
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
# Believe X-Forwarded-Proto only behind a platform proxy that sets it (see envconfig).
SECURE_PROXY_SSL_HEADER = proxy_ssl_header(_ENV)
SECURE_SSL_REDIRECT = get_bool(_ENV, "DJANGO_SECURE_SSL_REDIRECT", default=False)
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# --- Logging: everything to stderr, where the platform collects it ------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"plain": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "plain"}},
    "root": {"handlers": ["console"], "level": get_str(_ENV, "RB_LOG_LEVEL", "INFO")},
    "loggers": {"httpx": {"level": "WARNING"}, "httpcore": {"level": "WARNING"}},
}

# --- ResearchBridge -----------------------------------------------------------
# Downloads and the HTTP cache (gitignored; never committed). Defaults to the
# repository's data/ directory; the Docker image sets RB_DATA_DIR explicitly.
RB_DATA_DIR = Path(get_str(_ENV, "RB_DATA_DIR", str(BASE_DIR.parent / "data")))
# The worker's periodic re-check keeps PMC data current (a bucket term of use).
RB_RECHECK_MAX_AGE_DAYS = get_int(_ENV, "RB_RECHECK_MAX_AGE_DAYS", default=7)
RB_RECHECK_BATCH_SIZE = get_int(_ENV, "RB_RECHECK_BATCH_SIZE", default=500)
