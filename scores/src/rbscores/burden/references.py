"""Citation markers and references to figures and tables.

Citation markers are the external results a text leans on (decisions.md
§2.4): "as shown in [12]" asks the reader to bring a result the text does not
give. Each marker (one bracket or one parenthetical group, however many works
it lists) counts once towards the burden score. Recognised forms:

* numeric: ``[12]``, ``[3-5]``, ``[1, 4, 7]``;
* parenthetical author-year: ``(Smith, 2019)``, ``(Smith et al., 2019;
  Lee and Park 2020a)``, ``(see Smith et al., 2019)``, with name particles
  and non-English letters (``van den Ent et al., 2014``, ``Domínguez-Escobar``);
* narrative author-year: ``Smith et al. (2019)``.

Superscript numbers are not recognised: JATS flattening keeps a citation's
text but not that it was superscript, and bare digits are ambiguous.

Figure and table references ("Figure 1A", "Fig. 2B-D", "Table S1") are found
only so that their labels are not mistaken for terms; they add no burden.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

_YEAR = r"(?:19|20)\d{2}[a-z]?"
# A surname: optional lower-case particles ("van den Ent"), then a capitalised word.
_PARTICLES = r"(?:(?:van|von|de|der|den|del|della|di|da|du|la|le|ter|ten)\s+)*"
_AUTHOR = rf"{_PARTICLES}[A-Z][^\W\d_][\w'\u2019\-]*"
_AUTHOR_YEAR = rf"{_AUTHOR}(?:\s+et\s+al\.?|\s+(?:and|&)\s+{_AUTHOR})?,?\s+{_YEAR}"

_NUMERIC = re.compile(r"\[\s*\d{1,4}(?:\s*[-\u2013,]\s*\d{1,4})*\s*\]")
_PARENTHETICAL = re.compile(
    rf"\((?:see\s+|e\.g\.,?\s+)?{_AUTHOR_YEAR}(?:\s*[;,]\s*(?:{_AUTHOR_YEAR}|{_YEAR}))*\)"
)
_NARRATIVE = re.compile(rf"\b{_AUTHOR}\s+et\s+al\.?\s*\({_YEAR}\)")
_DISPLAY_OBJECT = re.compile(
    r"\b(?:Fig(?:ure)?s?\.?|Tables?|Videos?|Appendix|Box|Equations?|Eq\.)"
    r"\s*S?\d+[A-Za-z]?(?:\s*[-\u2013\u2014,]\s*S?(?:\d+[A-Za-z]?|[A-Za-z])\b)*"
)


def find_citations(text: str) -> list[tuple[int, int]]:
    """Find citation markers in a text.

    Args:
        text: Paragraph text.

    Returns:
        Non-overlapping ``(start, end)`` spans, sorted by start.
    """
    return _non_overlapping(
        (match.start(), match.end())
        for pattern in (_NUMERIC, _PARENTHETICAL, _NARRATIVE)
        for match in pattern.finditer(text)
    )


def find_display_references(text: str) -> list[tuple[int, int]]:
    """Find references to figures, tables, videos, boxes and equations.

    Args:
        text: Paragraph text.

    Returns:
        Non-overlapping ``(start, end)`` spans, sorted by start.
    """
    return _non_overlapping((m.start(), m.end()) for m in _DISPLAY_OBJECT.finditer(text))


def excluded_spans(text: str) -> list[tuple[int, int]]:
    """Return the spans that can hold neither terms nor definitions.

    Args:
        text: Paragraph text.

    Returns:
        Citation markers and display-object references, sorted by start.
    """
    return sorted(find_citations(text) + find_display_references(text))


def overlaps_any(start: int, end: int, spans: Iterable[tuple[int, int]]) -> bool:
    """Check whether a character range overlaps any of several spans.

    Args:
        start: Range start.
        end: Range end (exclusive).
        spans: ``(start, end)`` spans.

    Returns:
        True if the range shares at least one character with a span.
    """
    return any(start < span_end and span_start < end for span_start, span_end in spans)


def _non_overlapping(spans: Iterable[tuple[int, int]]) -> list[tuple[int, int]]:
    """Sort spans and drop any that overlap an earlier one.

    Args:
        spans: ``(start, end)`` spans in any order.

    Returns:
        Sorted spans, keeping the first of any overlapping group.
    """
    kept: list[tuple[int, int]] = []
    for start, end in sorted(spans):
        if kept and start < kept[-1][1]:
            continue
        kept.append((start, end))
    return kept
