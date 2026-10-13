"""Tests for citation markers and figure or table references."""

from __future__ import annotations

import pytest

from rbscores.burden.references import (
    excluded_spans,
    find_citations,
    find_display_references,
    overlaps_any,
)


def _found(text: str) -> list[str]:
    """Return the citation markers' text."""
    return [text[a:b] for a, b in find_citations(text)]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("As shown in [12], it works.", ["[12]"]),
        ("Earlier work [3-5, 9] agrees.", ["[3-5, 9]"]),
        ("It rose (Smith, 2019).", ["(Smith, 2019)"]),
        (
            "Seen before (Smith et al., 2019; Lee and Park 2020a).",
            ["(Smith et al., 2019; Lee and Park 2020a)"],
        ),
        (
            "Filaments (Jones et al., 2001; van den Ent et al., 2001; Domínguez-Escobar 2011).",
            ["(Jones et al., 2001; van den Ent et al., 2001; Domínguez-Escobar 2011)"],
        ),
        ("Smith et al. (2019) showed it.", ["Smith et al. (2019)"]),
        ("We used 12 mice (n = 12) at 37 °C (Fig. 2).", []),
        ("In 2019 (the first year) it began.", []),
    ],
)
def test_find_citations(text: str, expected: list[str]) -> None:
    """Numeric, parenthetical and narrative markers are found; other brackets are not."""
    assert _found(text) == expected


def test_display_references() -> None:
    """Figure, table and panel labels are found so they are not mistaken for terms."""
    text = "See Figure 1A, Fig. 2B\u2013D and Table S1; also Box 2 and Figure 3A, B."
    found = [text[a:b] for a, b in find_display_references(text)]
    assert found == ["Figure 1A", "Fig. 2B\u2013D", "Table S1", "Box 2", "Figure 3A, B"]


def test_excluded_spans_combines_both_and_sorts() -> None:
    """Exclusions cover citations and display references, in order."""
    text = "Table 1 shows it (Smith, 2019)."
    assert [text[a:b] for a, b in excluded_spans(text)] == ["Table 1", "(Smith, 2019)"]


def test_overlaps_any() -> None:
    """Ranges overlap when they share at least one character."""
    spans = [(5, 10)]
    assert overlaps_any(9, 12, spans)
    assert overlaps_any(0, 6, spans)
    assert not overlaps_any(10, 12, spans)
    assert not overlaps_any(0, 5, spans)
