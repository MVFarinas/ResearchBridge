"""Validation of the W3C Web Annotation shapes ResearchBridge stores.

Targets anchor to one paragraph (the alignment unit) with both selectors the
W3C model defines for text, as decisions.md §1.3 requires::

    {
        "source": "PMC10718527.1",
        "selector": [
            {"type": "TextQuoteSelector", "exact": "MreB", "prefix": "the ", "suffix": " protein"},
            {"type": "TextPositionSelector", "start": 104, "end": 108},
        ],
    }

Positions count Unicode code points in the paragraph's stored plain text
(W3C: "characters"); a browser working in UTF-16 must convert. Bodies are
``TextualBody`` values in plain text or Markdown; HTML is refused so a body
can never smuggle markup into a page.

See https://www.w3.org/TR/annotation-model/ (sections 3.2 and 4.2).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from django.core.exceptions import ValidationError

QUOTE_SELECTOR = "TextQuoteSelector"
POSITION_SELECTOR = "TextPositionSelector"
BODY_FORMATS = frozenset({"text/plain", "text/markdown"})
# W3C purposes (section 3.3.5) that make sense for a textual body.
BODY_PURPOSES = frozenset(
    {"assessing", "commenting", "describing", "editing", "questioning", "replying", "tagging"}
)


def validate_target(target: object) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    """Check a target's shape and return its two selectors.

    Args:
        target: The decoded JSON target.

    Returns:
        ``(quote_selector, position_selector)``.

    Raises:
        ValidationError: If the target is not an object with a string
            ``source`` and exactly one valid quote selector and one valid
            position selector whose span length equals the quote's length.
    """
    if not isinstance(target, Mapping):
        raise ValidationError("target must be a JSON object")
    if not isinstance(target.get("source"), str) or not target["source"]:
        raise ValidationError("target.source must be a non-empty string")
    selectors = target.get("selector")
    if not isinstance(selectors, list):
        raise ValidationError("target.selector must be a list")

    # Exactly one of each selector type, and nothing else.
    by_type: dict[str, list[Mapping[str, Any]]] = {}
    for selector in selectors:
        if not isinstance(selector, Mapping) or not isinstance(selector.get("type"), str):
            raise ValidationError("every selector must be an object with a string type")
        by_type.setdefault(selector["type"], []).append(selector)
    if set(by_type) != {QUOTE_SELECTOR, POSITION_SELECTOR} or any(
        len(items) != 1 for items in by_type.values()
    ):
        raise ValidationError(
            f"target.selector must hold exactly one {QUOTE_SELECTOR} and one {POSITION_SELECTOR}"
        )

    quote = by_type[QUOTE_SELECTOR][0]
    position = by_type[POSITION_SELECTOR][0]
    _check_quote(quote)
    _check_position(position)
    # The two selectors must describe the same span.
    if position["end"] - position["start"] != len(quote["exact"]):
        raise ValidationError("TextPositionSelector span length differs from the quoted text")
    return quote, position


def _check_quote(quote: Mapping[str, Any]) -> None:
    """Check a TextQuoteSelector.

    Args:
        quote: The selector.

    Raises:
        ValidationError: If ``exact`` is missing or empty, or ``prefix`` or
            ``suffix`` is present but not a string.
    """
    if not isinstance(quote.get("exact"), str) or not quote["exact"]:
        raise ValidationError(f"{QUOTE_SELECTOR}.exact must be a non-empty string")
    for key in ("prefix", "suffix"):
        if key in quote and not isinstance(quote[key], str):
            raise ValidationError(f"{QUOTE_SELECTOR}.{key} must be a string")


def _check_position(position: Mapping[str, Any]) -> None:
    """Check a TextPositionSelector.

    Args:
        position: The selector.

    Raises:
        ValidationError: Unless ``0 <= start < end`` with integer offsets.
    """
    start, end = position.get("start"), position.get("end")
    # bool is an int subclass; refuse it explicitly.
    if not (
        isinstance(start, int)
        and isinstance(end, int)
        and not isinstance(start, bool)
        and not isinstance(end, bool)
    ):
        raise ValidationError(f"{POSITION_SELECTOR}.start and .end must be integers")
    if not 0 <= start < end:
        raise ValidationError(f"{POSITION_SELECTOR} needs 0 <= start < end")


def validate_anchor(target: Mapping[str, Any], text: str) -> None:
    """Check that a target's selectors match a paragraph's text.

    Args:
        target: A target that passed :func:`validate_target`.
        text: The paragraph's stored plain text.

    Raises:
        ValidationError: If the quoted text is not at the stated position,
            or the prefix or suffix does not match the surrounding text.
    """
    quote, position = validate_target(target)
    start, end = position["start"], position["end"]
    if text[start:end] != quote["exact"]:
        raise ValidationError("the quoted text is not at the stated position in the paragraph")
    prefix, suffix = quote.get("prefix", ""), quote.get("suffix", "")
    if prefix and not text[:start].endswith(prefix):
        raise ValidationError("TextQuoteSelector.prefix does not precede the quote")
    if suffix and not text[end:].startswith(suffix):
        raise ValidationError("TextQuoteSelector.suffix does not follow the quote")


def validate_body(body: object) -> None:
    """Check a body is a W3C ``TextualBody`` in plain text or Markdown.

    Args:
        body: The decoded JSON body.

    Raises:
        ValidationError: If the type, value, format, language or purpose is
            invalid.
    """
    if not isinstance(body, Mapping):
        raise ValidationError("body must be a JSON object")
    if body.get("type") != "TextualBody":
        raise ValidationError("body.type must be TextualBody")
    if not isinstance(body.get("value"), str) or not body["value"].strip():
        raise ValidationError("body.value must be a non-empty string")
    if body.get("format", "text/plain") not in BODY_FORMATS:
        raise ValidationError(f"body.format must be one of {sorted(BODY_FORMATS)}")
    if "language" in body and not isinstance(body["language"], str):
        raise ValidationError("body.language must be a string")
    if "purpose" in body and body["purpose"] not in BODY_PURPOSES:
        raise ValidationError(f"body.purpose must be one of {sorted(BODY_PURPOSES)}")
