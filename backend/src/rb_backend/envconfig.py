"""Read Django settings values from environment variables.

Small, dependency-free helpers so that ``settings.py`` stays declarative and
the parsing rules are unit-tested. Every function takes the environment as a
mapping, so tests never touch ``os.environ``.

Database configuration comes from ``DATABASE_URL`` when it is set (what managed
platforms such as Render and Railway provide), and otherwise from the
``RB_DB_*`` variables that the local ``docker-compose.yml`` uses.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import unquote, urlsplit

from django.core.exceptions import ImproperlyConfigured

# Values accepted as true or false for boolean variables (compared lower-cased).
_TRUE = frozenset({"1", "true", "yes", "on"})
_FALSE = frozenset({"0", "false", "no", "off"})

# Local development defaults, matching docker-compose.yml and .env.example.
DEV_DB_HOST = "127.0.0.1"
DEV_DB_PORT = 5433
DEV_DB_NAME = "researchbridge"
DEV_DB_USER = "researchbridge"
DEV_DB_PASSWORD = "researchbridge-dev-only"  # noqa: S105 - public local-only credential


def get_str(env: Mapping[str, str], name: str, default: str = "") -> str:
    """Return a stripped variable, or the default when it is unset or blank.

    Args:
        env: The environment mapping.
        name: Variable name.
        default: Value to use when the variable is unset or blank.

    Returns:
        The value.
    """
    value = env.get(name, "").strip()
    return value or default


def get_bool(env: Mapping[str, str], name: str, *, default: bool) -> bool:
    """Parse a boolean variable.

    Args:
        env: The environment mapping.
        name: Variable name.
        default: Value to use when the variable is unset or blank.

    Returns:
        The parsed value.

    Raises:
        ImproperlyConfigured: If the value is not a recognised boolean.
    """
    raw = get_str(env, name).lower()
    if not raw:
        return default
    if raw in _TRUE:
        return True
    if raw in _FALSE:
        return False
    raise ImproperlyConfigured(f"{name} must be a boolean (true/false), got {raw!r}")


def get_int(env: Mapping[str, str], name: str, *, default: int) -> int:
    """Parse an integer variable.

    Args:
        env: The environment mapping.
        name: Variable name.
        default: Value to use when the variable is unset or blank.

    Returns:
        The parsed value.

    Raises:
        ImproperlyConfigured: If the value is not an integer.
    """
    raw = get_str(env, name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ImproperlyConfigured(f"{name} must be an integer, got {raw!r}") from exc


def get_list(env: Mapping[str, str], name: str, default: list[str] | None = None) -> list[str]:
    """Parse a comma-separated list variable, dropping empty items.

    Args:
        env: The environment mapping.
        name: Variable name.
        default: Value to use when the variable is unset or blank.

    Returns:
        The items, stripped.
    """
    raw = get_str(env, name)
    if not raw:
        return list(default or [])
    return [item.strip() for item in raw.split(",") if item.strip()]


def database_from_env(env: Mapping[str, str]) -> dict[str, Any]:
    """Build Django's ``DATABASES["default"]`` entry from the environment.

    ``DATABASE_URL`` (``postgres://user:password@host:port/name``) wins when
    set; otherwise ``RB_DB_HOST``, ``RB_DB_PORT``, ``RB_DB_NAME``,
    ``RB_DB_USER`` and ``RB_DB_PASSWORD`` are used, with the local compose
    defaults. ``RB_DB_CONN_MAX_AGE`` sets persistent connection lifetime.

    Args:
        env: The environment mapping.

    Returns:
        The database settings dictionary.

    Raises:
        ImproperlyConfigured: If ``DATABASE_URL`` is not a PostgreSQL URL or
            a port is not a valid integer.
    """
    url = get_str(env, "DATABASE_URL")
    if url:
        config = _parse_database_url(url)
    else:
        config = {
            "HOST": get_str(env, "RB_DB_HOST", DEV_DB_HOST),
            "PORT": get_int(env, "RB_DB_PORT", default=DEV_DB_PORT),
            "NAME": get_str(env, "RB_DB_NAME", DEV_DB_NAME),
            "USER": get_str(env, "RB_DB_USER", DEV_DB_USER),
            "PASSWORD": get_str(env, "RB_DB_PASSWORD", DEV_DB_PASSWORD),
        }
    return {
        "ENGINE": "django.db.backends.postgresql",
        **config,
        "CONN_MAX_AGE": get_int(env, "RB_DB_CONN_MAX_AGE", default=0),
    }


def _parse_database_url(url: str) -> dict[str, Any]:
    """Split a PostgreSQL URL into Django database settings.

    Args:
        url: A ``postgres://`` or ``postgresql://`` URL.

    Returns:
        HOST, PORT, NAME, USER and PASSWORD (percent-decoded).

    Raises:
        ImproperlyConfigured: If the scheme is not PostgreSQL, the database
            name is missing, or the port is invalid.
    """
    parts = urlsplit(url)
    if parts.scheme not in {"postgres", "postgresql"}:
        raise ImproperlyConfigured("DATABASE_URL must start with postgres:// or postgresql://")
    name = unquote(parts.path.lstrip("/"))
    if not name:
        raise ImproperlyConfigured("DATABASE_URL must name a database")
    try:
        port = parts.port or 5432
    except ValueError as exc:
        raise ImproperlyConfigured("DATABASE_URL has an invalid port") from exc
    return {
        "HOST": parts.hostname or "",
        "PORT": port,
        "NAME": name,
        "USER": unquote(parts.username or ""),
        "PASSWORD": unquote(parts.password or ""),
    }
