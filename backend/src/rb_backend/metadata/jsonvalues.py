"""Defensive readers for values in untrusted JSON from external services.

Every client reads upstream JSON through these, so an unexpected type
becomes "absent" instead of an exception or a wrong value.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def as_mapping(value: object) -> Mapping[str, Any]:
    """The value if it is a JSON object, else an empty one.

    Args:
        value: Any decoded JSON value.

    Returns:
        A mapping.
    """
    return value if isinstance(value, Mapping) else {}


def as_list(value: object) -> list[Any]:
    """The value if it is a JSON array, else an empty list.

    Args:
        value: Any decoded JSON value.

    Returns:
        A list.
    """
    return value if isinstance(value, list) else []


def as_str(value: object) -> str | None:
    """The value as a stripped, non-empty string, if it is one.

    Args:
        value: Any decoded JSON value.

    Returns:
        The string, or None.
    """
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def as_int(value: object) -> int | None:
    """The value as an int, if it is a JSON integer (not a boolean).

    Args:
        value: Any decoded JSON value.

    Returns:
        The integer, or None.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def as_float(value: object) -> float | None:
    """The value as a float, if it is a JSON number (not a boolean).

    Args:
        value: Any decoded JSON value.

    Returns:
        The number, or None.
    """
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def as_bool(value: object) -> bool | None:
    """The value if it is a JSON boolean.

    Args:
        value: Any decoded JSON value.

    Returns:
        The boolean, or None.
    """
    return value if isinstance(value, bool) else None


def year_counts(pairs: list[tuple[int, int]]) -> list[dict[str, int]]:
    """Sort ``(year, count)`` pairs by year into JSON-ready objects.

    Args:
        pairs: Year and count pairs (years unique).

    Returns:
        ``[{"year": ..., "count": ...}, ...]`` in ascending year order.
    """
    return [{"year": year, "count": count} for year, count in sorted(pairs)]
