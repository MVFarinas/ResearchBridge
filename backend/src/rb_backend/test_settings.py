"""Settings for the test suite: the normal settings plus a test-only secret key.

pytest-django loads this module (see ``pyproject.toml``). The database is the
same local Postgres as development (pytest-django creates and drops a separate
``test_<name>`` database), because the licence gate relies on PostgreSQL check
constraints and partial unique indexes that must be tested for real.
"""

import os

os.environ.setdefault("DJANGO_SECRET_KEY", "test-only-insecure-key-never-used-outside-tests")

from rb_backend.settings import *  # noqa: F403

# Plain static storage: tests never run collectstatic.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
# Fast password hashing for tests that create users.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
