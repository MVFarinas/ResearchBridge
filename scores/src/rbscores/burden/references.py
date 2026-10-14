"""Citation markers and references to figures and tables.

Citation markers are the external results a text leans on (decisions.md
§2.4): "as shown in [12]" asks the reader to bring a result the text does not
give. Each marker (one bracket or one parenthetical group, however many works
it lists) counts once towards the burden score. Recognised forms:

* numeric: ``[12]``, ``[3-5]``, ``[1, 4, 7]``;
* parenthetical author-year: ``(Smith, 2019)``, ``(Smith et al., 2019;
  Lee and Park 2020a)``, ``(see Smith et al., 2019)``, with name particles
  and non-English letters (``van den Ent et al., 2014``, ``Domínguez-Escobar``);
* narrative author-year: ``Smith et al. (2019)``, and eLife's unbracketed
  ``Smith et al., 2019`` and ``Day and Bentley, 1911``. The two-author form
  needs the comma before the year (eLife's house style), so "the Wnt and
  Notch 2019 consortium" is not a citation; a single author with a bare
  year, "Crick, 1984", is too easily confused with prose to count.

Superscript numbers are not recognised: JATS flattening keeps a citation's
text but not that it was superscript, and bare digits are ambiguous.

Figure and table references ("Figure 1A", "Fig. 2B-D", "Table S1") and full
bibliographic reference strings (three or more "Surname AB" authors and a
year, extended to a DOI that follows, as in an eLife Insight's "Related
research article" box) are found only so that their words are not mistaken
for terms; they add no burden.

Two kinds of personal and institutional name are skipped for the same
reason (no NER is used, see :mod:`rbscores.burden.terms`):

* attributions, "Rut Carballido-López and colleagues" (one to three
  capitalised names before "and colleagues", "and co-workers",
  "and coauthors" or "and collaborators"), and "Mao et al." without a year
  (the year-less mention of a cited work, which is not counted as a
  citation marker). A capitalised common noun at the start of a sentence
  ("Researchers and colleagues") is caught too, which costs nothing, since
  such a word is familiar and never a term;
* affiliations in parentheses, "(Université Paris-Saclay)", "(University of
  Oxford)", "(Max Planck Institute)", together with the one to three
  capitalised names right before them ("Wei Mao (Université Paris-Saclay)").
  The parenthetical must contain a capitalised institution word
  (:data:`_INSTITUTION_WORD`).

A journal's name in running text ("Now, in eLife, ...") is not found here,
because it cannot be told from a term by its shape;
:func:`find_name_mentions` finds given names (such as the document's own
journal title) instead.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

_YEAR = r"(?:19|20)\d{2}[a-z]?"
# A surname: optional lower-case particles ("van den Ent"), then a capitalised word.
_PARTICLE_WORDS = r"(?:van|von|de|der|den|del|della|di|da|du|la|le|ter|ten)"
_PARTICLES = rf"(?:{_PARTICLE_WORDS}\s+)*"
_AUTHOR = rf"{_PARTICLES}[A-Z][^\W\d_][\w'\u2019\-]*"
_AUTHOR_YEAR = rf"{_AUTHOR}(?:\s+et\s+al\.?|\s+(?:and|&)\s+{_AUTHOR})?,?\s+{_YEAR}"

_NUMERIC = re.compile(r"\[\s*\d{1,4}(?:\s*[-\u2013,]\s*\d{1,4})*\s*\]")
_PARENTHETICAL = re.compile(
    rf"\((?:see\s+|e\.g\.,?\s+)?{_AUTHOR_YEAR}(?:\s*[;,]\s*(?:{_AUTHOR_YEAR}|{_YEAR}))*\)"
)
_NARRATIVE = re.compile(rf"\b{_AUTHOR}\s+et\s+al\.?\s*\({_YEAR}\)")
# "Smith et al., 2019" (comma optional) and "Day and Bentley, 1911" (comma required).
_NARRATIVE_BARE = re.compile(rf"\b{_AUTHOR}\s+(?:et\s+al\.?,?|(?:and|&)\s+{_AUTHOR},)\s+{_YEAR}\b")

# Personal names: a capitalised word, possibly hyphenated ("Carballido-López").
_NAME_WORD = r"[A-Z][^\W\d_][\w'\u2019]*(?:-[A-Z][^\W\d_][\w'\u2019]*)?"
_PERSON = rf"(?:{_NAME_WORD}\s+){{0,2}}{_NAME_WORD}"
_ATTRIBUTION = re.compile(
    rf"(?<![\w\-]){_PERSON}(?=\s+and\s+(?:colleagues|co-?workers|co-?authors|collaborators)\b)"
)
_ET_AL = re.compile(rf"\b{_AUTHOR}\s+et\s+al\b\.?")
# "Centre" and "Center" only as "Centre for/of ...", since "(Center panel)" is a figure label.
_INSTITUTION_WORD = (
    r"(?:Universit(?:y|ies|é|ät|à|eit|at|ad)|Institut(?:e|o|es)?|Hospital|College"
    r"|Laborator(?:y|ies)|Academy|Akademie|Faculty|School\s+of|(?:Centre|Center)\s+(?:for|of))"
)
"""Capitalised words that mark a parenthetical as an affiliation."""
_AFFILIATION = re.compile(
    rf"(?:(?<![\w\-]){_PERSON}\s*)?\((?=[^()]*\b{_INSTITUTION_WORD}\b)[^()]{{1,200}}\)"
)

# A reference-list author: up to three name words or particles, a surname, initials.
_REF_NAME_WORD = rf"(?:[A-Z][^\W\d_][\w'\u2019\-]*|{_PARTICLE_WORDS})"
_REF_AUTHOR = (
    rf"(?<![\w'\u2019\-])(?:{_REF_NAME_WORD}\s+){{0,3}}[A-Z][^\W\d_][\w'\u2019\-]*\s+[A-Z]{{1,3}}\b"
)
# At most 50 authors, which bounds the backtracking on long capitalised runs.
_AUTHOR_LIST = re.compile(
    rf"{_REF_AUTHOR}(?:,\s+{_REF_AUTHOR}){{2,49}}(?:,?\s+et\s+al)?\.?\s+\(?{_YEAR}\)?"
)
_DOI = re.compile(r"\b(?:doi:?\s*|https?://(?:dx\.)?doi\.org/)10\.\d{4,9}/[^\s,;]*[^\s,;.)]")
_MAX_REFERENCE_TO_DOI_CHARS = 600
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
        for pattern in (_NUMERIC, _PARENTHETICAL, _NARRATIVE, _NARRATIVE_BARE)
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


def find_reference_strings(text: str) -> list[tuple[int, int]]:
    """Find full bibliographic references and DOIs written into running text.

    A reference starts at a list of three or more "Surname AB" authors
    followed by a year ("Mao W, Renner LD, Cornilleau C, ... 2023.") and runs
    to the end of the first DOI within :data:`_MAX_REFERENCE_TO_DOI_CHARS`
    characters, so its title, journal and article number are covered too;
    without a DOI it covers the authors and year only. Every DOI is also
    returned on its own.

    Args:
        text: Paragraph text.

    Returns:
        Non-overlapping ``(start, end)`` spans, sorted by start.
    """
    spans: list[tuple[int, int]] = []
    dois = [(m.start(), m.end()) for m in _DOI.finditer(text)]

    # Extend each author list to the DOI that closes its reference, if any.
    for match in _AUTHOR_LIST.finditer(text):
        end = match.end()
        for doi_start, doi_end in dois:
            if end <= doi_start <= match.end() + _MAX_REFERENCE_TO_DOI_CHARS:
                end = doi_end
                break
        spans.append((match.start(), end))
    return _non_overlapping(spans + dois)


def find_personal_names(text: str) -> list[tuple[int, int]]:
    """Find attributed researchers' names and parenthesised affiliations.

    Args:
        text: Paragraph text.

    Returns:
        Non-overlapping ``(start, end)`` spans, sorted by start: the names in
        "X Y and colleagues", "X et al." and "X Y (University of Z)" (with or
        without the names).
    """
    return _non_overlapping(
        (match.start(), match.end())
        for pattern in (_ATTRIBUTION, _ET_AL, _AFFILIATION)
        for match in pattern.finditer(text)
    )


def find_name_mentions(text: str, names: Iterable[str]) -> list[tuple[int, int]]:
    """Find whole-word mentions of given names, such as a journal's title.

    Args:
        text: Paragraph text.
        names: Names to look for, matched case-sensitively as whole words;
            blank names are ignored.

    Returns:
        Non-overlapping ``(start, end)`` spans, sorted by start.
    """
    spans: list[tuple[int, int]] = []
    for name in names:
        if not name.strip():
            continue
        pattern = re.compile(rf"(?<![\w\-]){re.escape(name.strip())}(?![\w\-])")
        spans.extend((m.start(), m.end()) for m in pattern.finditer(text))
    return _non_overlapping(spans)


def excluded_spans(text: str) -> list[tuple[int, int]]:
    """Return the spans that can hold neither terms nor definitions.

    Args:
        text: Paragraph text.

    Returns:
        Citation markers, display-object references, reference strings and
        personal names with affiliations, sorted by start (they may overlap
        one another).
    """
    return sorted(
        find_citations(text)
        + find_display_references(text)
        + find_reference_strings(text)
        + find_personal_names(text)
    )


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
