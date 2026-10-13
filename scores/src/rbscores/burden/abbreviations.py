"""Abbreviation definitions found with the Schwartz-Hearst algorithm.

Implemented from the published description: A. S. Schwartz and M. A. Hearst,
"A simple algorithm for identifying abbreviation definitions in biomedical
text", Pacific Symposium on Biocomputing 8:451-462 (2003). No code was copied.

The algorithm, per sentence:

1. Find each parenthetical. If it holds at most two words and is no longer
   than the text before it, it is a candidate short form (SF) defined by the
   text before it, "long form (SF)". Otherwise the word just before the
   parenthesis is the candidate SF and the parenthetical the long form (LF),
   "SF (long form)"; that SF must contain a capital letter. Text after the
   first ", " or "; " inside the parenthesis is ignored.
2. A valid SF has a letter, starts with a letter or digit, and has 2 to 10
   letters and digits.
3. Match the SF to the LF candidate right to left: every letter or digit of
   the SF must appear in the LF, in order, and the SF's first character must
   start a word. The LF starts at the beginning of the word where that first
   character was matched.
4. Reject the pair if the LF is shorter than the SF, contains the SF as a
   word, or has more than min(|SF| + 5, 2 x |SF|) words, where |SF| counts
   the SF's letters and digits and LF words are split on spaces and hyphens.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

MAX_SHORT_FORM_CHARS: Final = 10
_LONG_FORM_WORD_SPLIT = re.compile(r"[\s\-]+")
_TRAILING_WORD = re.compile(r"(\S+)\s*$")


@dataclass(frozen=True, slots=True)
class Abbreviation:
    """An abbreviation defined in the text.

    Attributes:
        short_form: The abbreviation, e.g. "BMI".
        long_form: Its expansion, e.g. "body mass index".
        short_start: Offset of the short form in the analysed text.
        long_start: Offset of the long form in the analysed text.
    """

    short_form: str
    long_form: str
    short_start: int
    long_start: int

    @property
    def short_end(self) -> int:
        """End offset (exclusive) of the short form."""
        return self.short_start + len(self.short_form)

    @property
    def long_end(self) -> int:
        """End offset (exclusive) of the long form."""
        return self.long_start + len(self.long_form)


def find_abbreviations(sentence: str, *, offset: int = 0) -> list[Abbreviation]:
    """Find abbreviation definitions in one sentence.

    Call it once per sentence: the long-form search runs back from each
    parenthesis to the start of the text it is given.

    Args:
        sentence: The sentence text.
        offset: Added to every reported position (the sentence's offset in
            its paragraph).

    Returns:
        Definitions in the order their parentheses appear.
    """
    found: list[Abbreviation] = []
    position = 0
    while (open_index := sentence.find("(", position)) >= 0:
        close_index = _matching_close(sentence, open_index)
        if close_index < 0:
            break
        pair = _pair_at(sentence, open_index, close_index)
        if pair is not None:
            short, short_start, long_candidate, long_base = pair
            match = _match_pair(short, long_candidate)
            if match is not None:
                long_start = long_base + match
                found.append(
                    Abbreviation(
                        short_form=short,
                        long_form=long_candidate[match:],
                        short_start=offset + short_start,
                        long_start=offset + long_start,
                    )
                )
        position = close_index + 1
    return found


def _matching_close(text: str, open_index: int) -> int:
    """Find the parenthesis closing the one at ``open_index``, allowing nesting.

    Args:
        text: The text.
        open_index: Index of an opening parenthesis.

    Returns:
        Index of the matching ")", or -1 if it is never closed.
    """
    depth = 0
    for index in range(open_index, len(text)):
        if text[index] == "(":
            depth += 1
        elif text[index] == ")":
            depth -= 1
            if depth == 0:
                return index
    return -1


def _pair_at(sentence: str, open_index: int, close_index: int) -> tuple[str, int, str, int] | None:
    """Work out the candidate short form and long-form text around a parenthetical.

    Args:
        sentence: The sentence.
        open_index: Index of "(".
        close_index: Index of the matching ")".

    Returns:
        ``(short form, its index, long-form candidate, candidate's index)``,
        or None when the parenthetical cannot hold a definition.
    """
    # Keep only the part of the parenthetical before ", " or "; ".
    inner = sentence[open_index + 1 : close_index]
    for separator in (", ", "; "):
        cut = inner.find(separator)
        if cut >= 0:
            inner = inner[:cut]
    inner_start = open_index + 1 + (len(inner) - len(inner.lstrip()))
    inner = inner.strip()
    before = sentence[:open_index].rstrip()
    if len(inner) < 2 or not before:
        return None

    # "long form (SF)": a short parenthetical defined by the preceding text.
    if len(inner.split()) <= 2 and len(inner) <= len(before):
        return (inner, inner_start, before, 0) if _valid_short_form(inner) else None

    # "SF (long form)": the word before the parenthesis, which needs a capital.
    trailing = _TRAILING_WORD.search(before)
    if trailing is None:
        return None
    short = trailing.group(1)
    if not any(ch.isupper() for ch in short) or not _valid_short_form(short):
        return None
    return short, trailing.start(1), inner, inner_start


def _valid_short_form(short: str) -> bool:
    """Check the Schwartz-Hearst short-form conditions.

    Args:
        short: Candidate short form.

    Returns:
        True if it has a letter, starts with a letter or digit, and has 2 to
        :data:`MAX_SHORT_FORM_CHARS` letters and digits.
    """
    alnum = sum(1 for ch in short if ch.isalnum())
    return (
        any(ch.isalpha() for ch in short)
        and short[0].isalnum()
        and 2 <= alnum <= MAX_SHORT_FORM_CHARS
    )


def _match_pair(short: str, long_candidate: str) -> int | None:
    """Find and check the long form for a short form.

    Args:
        short: The short form.
        long_candidate: Text the long form must be a suffix of.

    Returns:
        Index in ``long_candidate`` where the long form starts, or None if
        there is no acceptable long form.
    """
    start = _best_long_form_start(short, long_candidate)
    if start is None:
        return None

    # Length and word-count checks from the paper.
    long_form = long_candidate[start:]
    short_size = sum(1 for ch in short if ch.isalnum())
    long_words = len([w for w in _LONG_FORM_WORD_SPLIT.split(long_form) if w])
    if (
        len(long_form) < len(short)
        or f"{short} " in long_form
        or long_form.endswith(short)
        or long_words > min(short_size + 5, short_size * 2)
    ):
        return None
    return start


def _best_long_form_start(short: str, long_candidate: str) -> int | None:
    """Match short-form characters right to left inside the long-form candidate.

    Args:
        short: The short form.
        long_candidate: Text before (or inside) the parenthesis.

    Returns:
        Start index of the shortest matching long form, or None.
    """
    short_index = len(short) - 1
    long_index = len(long_candidate) - 1
    while short_index >= 0:
        char = short[short_index].lower()
        if not char.isalnum():
            short_index -= 1
            continue

        # Move left to the next matching character; the SF's first character
        # must also be at the start of a word.
        while long_index >= 0 and (
            long_candidate[long_index].lower() != char
            or (short_index == 0 and long_index > 0 and long_candidate[long_index - 1].isalnum())
        ):
            long_index -= 1
        if long_index < 0:
            return None
        long_index -= 1
        short_index -= 1

    # The long form begins at the start of the word holding the first match.
    return long_candidate.rfind(" ", 0, long_index + 1) + 1
