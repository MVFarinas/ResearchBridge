"""A small rule-based sentence splitter for scientific English.

Used to count the sentences in a marked addition and as the deterministic
claim-decomposition fallback. Rules, in order:

* A boundary is ``.``, ``!`` or ``?`` (plus any closing quotes or brackets),
  then whitespace, then a capital letter, digit, or opening quote/bracket.
* No boundary inside parentheses or square brackets ("(Smith et al. 2019)").
* No boundary after a known abbreviation ("et al.", "e.g.", "Fig.", "vs.")
  or after a single capital initial ("J. Smith", "E. coli", "A. viteae").

pysbd (MIT) was evaluated and not used: version 0.3.4 has invalid escape
sequences that are syntax warnings on Python 3.12, and this project runs
tests with warnings as errors. See docs/licence-inventory.md.
"""

from __future__ import annotations

import re

# Lower-cased abbreviations (without the final period) after which a period
# does not end a sentence.
ABBREVIATIONS = frozenset(
    {
        "al",
        "approx",
        "ca",
        "cf",
        "dr",
        "e.g",
        "eq",
        "eqs",
        "etc",
        "fig",
        "figs",
        "i.e",
        "mr",
        "mrs",
        "ms",
        "no",
        "nos",
        "p",
        "pp",
        "prof",
        "ref",
        "refs",
        "resp",
        "sp",
        "spp",
        "st",
        "suppl",
        "tab",
        "u.k",
        "u.s",
        "viz",
        "vol",
        "vs",
    }
)

# Closing quotes may follow the punctuation; opening quotes may start the next
# sentence. Curly quotes are written as escapes (U+201C/D, U+2018/9).
_BOUNDARY = re.compile(r"[.!?][\"'\u201d\u2019)\]]*\s+(?=[A-Z0-9\"\u201c\u2018(\[])")
_LAST_TOKEN = re.compile(r"(\S+)$")


def sentence_spans(text: str) -> list[tuple[int, int]]:
    """Return the character spans of the sentences in ``text``.

    Args:
        text: Plain text.

    Returns:
        ``(start, end)`` offsets of each sentence, stripped of surrounding
        whitespace, in order. Empty for blank text.
    """
    spans: list[tuple[int, int]] = []
    start = 0
    for match in _BOUNDARY.finditer(text):
        end = match.start() + 1
        if not _is_boundary(text, start, end):
            continue
        # The sentence keeps its closing quotes or brackets.
        sentence_end = match.end() - (len(match.group()) - len(match.group().rstrip()))
        _append(spans, text, start, sentence_end)
        start = match.end()
    _append(spans, text, start, len(text))
    return spans


def split_sentences(text: str) -> list[str]:
    """Split text into sentences.

    Args:
        text: Plain text.

    Returns:
        The sentences, stripped, in order.
    """
    return [text[a:b] for a, b in sentence_spans(text)]


def _is_boundary(text: str, start: int, end: int) -> bool:
    """Decide whether the punctuation ending at ``end`` closes a sentence.

    Args:
        text: The whole text.
        start: Start of the current sentence.
        end: Offset just after the ``.``, ``!`` or ``?``.

    Returns:
        False inside brackets, after an abbreviation or after an initial.
    """
    segment = text[start:end]
    # Unbalanced opening brackets mean the punctuation is inside them.
    if segment.count("(") > segment.count(")") or segment.count("[") > segment.count("]"):
        return False
    if text[end - 1] != ".":
        return True
    token_match = _LAST_TOKEN.search(segment[:-1])
    token = token_match.group(1) if token_match else ""
    bare = token.lstrip("(\"'\u201c\u2018[").lower()
    if bare in ABBREVIATIONS:
        return False
    # A single capital letter: an initial or an abbreviated genus.
    return not (len(bare) == 1 and token[-1:].isupper())


def _append(spans: list[tuple[int, int]], text: str, start: int, end: int) -> None:
    """Append the stripped span ``text[start:end]`` if it is not blank.

    Args:
        spans: The list to extend.
        text: The whole text.
        start: Span start.
        end: Span end.
    """
    chunk = text[start:end]
    if not chunk.strip():
        return
    leading = len(chunk) - len(chunk.lstrip())
    trailing = len(chunk) - len(chunk.rstrip())
    spans.append((start + leading, end - trailing))
