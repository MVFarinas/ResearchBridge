"""Settings helpers read the environment correctly and fail loudly on bad values."""

from __future__ import annotations

import pytest
from django.core.exceptions import ImproperlyConfigured

from rb_backend.envconfig import (
    database_from_env,
    get_bool,
    get_int,
    get_list,
    get_str,
    proxy_ssl_header,
)


def test_get_str_treats_blank_as_unset() -> None:
    """Blank values (as in a copied .env.example) fall back to the default."""
    assert get_str({"X": "  "}, "X", "default") == "default"
    assert get_str({"X": " value "}, "X") == "value"


@pytest.mark.parametrize(("raw", "expected"), [("true", True), ("1", True), ("off", False)])
def test_get_bool_parses_common_spellings(raw: str, expected: bool) -> None:
    """Booleans accept the usual spellings."""
    assert get_bool({"X": raw}, "X", default=not expected) is expected


def test_get_bool_rejects_garbage() -> None:
    """An unrecognised boolean is a configuration error, not silently false."""
    with pytest.raises(ImproperlyConfigured, match="X must be a boolean"):
        get_bool({"X": "maybe"}, "X", default=False)


def test_get_int_and_list() -> None:
    """Integers and comma lists parse; bad integers raise."""
    assert get_int({}, "N", default=7) == 7
    assert get_int({"N": "12"}, "N", default=7) == 12
    with pytest.raises(ImproperlyConfigured):
        get_int({"N": "twelve"}, "N", default=7)
    assert get_list({"L": "a, b,,c "}, "L") == ["a", "b", "c"]
    assert get_list({}, "L", ["x"]) == ["x"]


def test_database_defaults_match_local_compose() -> None:
    """Without variables, the local compose database on port 5433 is used."""
    config = database_from_env({})
    assert config["ENGINE"] == "django.db.backends.postgresql"
    assert (config["HOST"], config["PORT"], config["NAME"]) == ("127.0.0.1", 5433, "researchbridge")
    assert config["CONN_MAX_AGE"] == 0


def test_database_from_rb_variables() -> None:
    """The RB_DB_* variables override the defaults."""
    config = database_from_env(
        {"RB_DB_HOST": "db", "RB_DB_PORT": "5544", "RB_DB_NAME": "rb", "RB_DB_USER": "u"}
    )
    assert (config["HOST"], config["PORT"], config["NAME"], config["USER"]) == (
        "db",
        5544,
        "rb",
        "u",
    )


def test_database_url_wins_and_is_decoded() -> None:
    """DATABASE_URL (managed platforms) wins and percent-decoding is applied."""
    config = database_from_env(
        {
            "DATABASE_URL": "postgres://user%40x:p%3Ass@host.example:6543/db%2Dname",
            "RB_DB_PORT": "1",
        }
    )
    assert config["HOST"] == "host.example"
    assert config["PORT"] == 6543
    assert config["NAME"] == "db-name"
    assert config["USER"] == "user@x"
    assert config["PASSWORD"] == "p:ss"  # noqa: S105 - synthetic test value


@pytest.mark.parametrize(
    "url", ["mysql://u:p@h/db", "postgres://u:p@h/", "postgres://u:p@h:notaport/db"]
)
def test_database_url_rejects_bad_values(url: str) -> None:
    """Non-PostgreSQL URLs, missing names and bad ports are configuration errors."""
    with pytest.raises(ImproperlyConfigured):
        database_from_env({"DATABASE_URL": url})


def test_forwarded_proto_is_trusted_only_when_enabled() -> None:
    """X-Forwarded-Proto is ignored unless a platform proxy is declared to set it."""
    assert proxy_ssl_header({}) is None
    assert proxy_ssl_header({"DJANGO_TRUST_PROXY_SSL_HEADER": "false"}) is None
    assert proxy_ssl_header({"DJANGO_TRUST_PROXY_SSL_HEADER": "true"}) == (
        "HTTP_X_FORWARDED_PROTO",
        "https",
    )
