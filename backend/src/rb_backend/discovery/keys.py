"""Public paper keys: the identifier used in reader URLs (``/papers/<key>``).

A paper's key is its PMC ID when it has one (every paper ingested so far), so
URLs are stable and recognisable; otherwise ``rb-<id>``. Keys resolve only to
displayable papers, through the gated access layer.
"""

from __future__ import annotations

import re

from rb_backend.corpus import access
from rb_backend.corpus.models import Paper

_PMCID_KEY = re.compile(r"^PMC\d+$")
_INTERNAL_KEY = re.compile(r"^rb-(\d+)$")


def paper_key(paper: Paper) -> str:
    """The public key of a paper.

    Args:
        paper: The paper.

    Returns:
        ``PMC<digits>`` or ``rb-<primary key>``.
    """
    return paper.pmcid or f"rb-{paper.pk}"


def find_displayable_paper(key: str) -> Paper | None:
    """Resolve a public key to a displayable paper.

    Args:
        key: A key from :func:`paper_key` (PMC IDs are matched case-insensitively).

    Returns:
        The paper, or None when the key is malformed, unknown, or names a
        paper that may not be displayed.
    """
    text = key.strip()
    if _PMCID_KEY.match(text.upper()):
        return access.displayable_papers().filter(pmcid=text.upper()).first()
    if match := _INTERNAL_KEY.match(text):
        return access.displayable_papers().filter(pk=int(match.group(1))).first()
    return None
