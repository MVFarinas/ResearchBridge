"""Paper-level helpers over :class:`rbcore.jats.Article`, shared by selection and ingest.

* The §1.1 licence gate for benchmark use: rewriting must be permitted,
  without the non-commercial restriction, and without anything sending the
  paper to licence review.
* Lay summaries (eLife digests, PLOS author summaries): the expert reference
  that ties a paper to the PLOS/eLife lay-summary datasets.
* Section paths and word counts, for passage proposal.
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from datetime import date

from rbcore.jats import Article, Section
from rbcore.licences import LicenceDecision, LicenceEvidence, decide

# JATS @abstract-type values used for lay summaries: eLife digests are
# "executive-summary", PLOS author summaries are "summary".
LAY_SUMMARY_TYPES = frozenset({"executive-summary", "summary", "plain-language-summary"})
_DISCUSSION = re.compile(r"\b(discussion|conclusions?)\b", re.IGNORECASE)
_RESULTS = re.compile(r"\bresults?\b", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class LaySummary:
    """One lay summary found in the article's abstracts.

    Attributes:
        abstract_id: The abstract's stable ID (e.g. "abs2").
        abstract_type: The JATS ``@abstract-type``.
        title: The abstract's title (e.g. "eLife digest").
        text: Its paragraphs, blank-line separated.
    """

    abstract_id: str
    abstract_type: str
    title: str | None
    text: str


@dataclass(frozen=True, slots=True)
class BenchmarkLicence:
    """The §1.1 decision for a paper, and whether the benchmark may use it.

    Attributes:
        decision: The rbcore decision over all evidence given.
        usable: True when the paper may be rewritten, is not non-commercial,
            needs no licence review and has no unattached permissions blocks.
        reasons: Why it is not usable (empty when usable).
    """

    decision: LicenceDecision
    usable: bool
    reasons: tuple[str, ...] = field(default=())


def benchmark_licence(
    article: Article, external: Sequence[LicenceEvidence], *, today: date | None = None
) -> BenchmarkLicence:
    """Decide whether a paper's licence permits benchmark use.

    The primary-source evidence (PMC ``license_code`` or Europe PMC
    ``license``) is passed in the same :func:`rbcore.licences.decide` call as
    the JATS evidence, as rbcore recommends: PMC tags its own JATS licence
    references ``specific-use="textmining"``, and an agreeing unscoped code
    clears that review flag, while a disagreeing one fails closed.

    Args:
        article: The parsed JATS.
        external: Evidence from the primary source (never aggregator fields).
        today: Date to judge ALI licence dates against.

    Returns:
        The decision and whether the benchmark may use the paper.
    """
    jats = article.permissions.evidence() if article.permissions else ()
    decision = decide([*external, *jats], today=today)
    reasons: list[str] = []
    if not decision.permissions.can_rewrite:
        reasons.append(f"licence does not permit rewriting ({decision.licence.label})")
    if decision.permissions.non_commercial:
        reasons.append("non-commercial licence (excluded from the benchmark)")
    if decision.needs_review:
        reasons.append("licence needs review: " + "; ".join(decision.reasons))
    if article.unattached_permissions:
        reasons.append(f"{len(article.unattached_permissions)} unattached permissions block(s)")
    return BenchmarkLicence(decision=decision, usable=not reasons, reasons=tuple(reasons))


def lay_summaries(article: Article) -> list[LaySummary]:
    """Return the article's lay summaries (eLife digest, PLOS author summary).

    Args:
        article: The parsed JATS.

    Returns:
        Lay summaries in document order; empty when there is none.
    """
    return [
        LaySummary(abstract.id, abstract.sec_type or "", abstract.title, abstract.text)
        for abstract in article.abstracts
        if abstract.sec_type in LAY_SUMMARY_TYPES and abstract.text.strip()
    ]


def word_count(text: str) -> int:
    """Count whitespace-separated words.

    Args:
        text: Any text.

    Returns:
        The number of words.
    """
    return len(text.split())


def body_words(article: Article) -> int:
    """Count the words in the article body (abstracts and back matter excluded).

    Args:
        article: The parsed JATS.

    Returns:
        The body word count.
    """
    return sum(word_count(p.text) for p in article.iter_paragraphs())


def section_paths(article: Article) -> dict[str, tuple[str, ...]]:
    """Map each body paragraph ID to the titles of the sections enclosing it.

    Args:
        article: The parsed JATS.

    Returns:
        Paragraph ID -> section titles from outermost to innermost (untitled
        sections are skipped).
    """
    paths: dict[str, tuple[str, ...]] = {}

    def walk(section: Section, path: tuple[str, ...]) -> None:
        """Record the paths of one section's paragraphs, then recurse."""
        here = (*path, section.title) if section.title else path
        for paragraph in section.paragraphs:
            paths[paragraph.id] = here
        for child in section.sections:
            walk(child, here)

    walk(article.body, ())
    return paths


def top_sections(article: Article) -> Iterator[Section]:
    """Yield the body's top-level sections in order.

    Args:
        article: The parsed JATS.

    Yields:
        Each direct child section of the body.
    """
    yield from article.body.sections


def find_section(article: Article, kind: str) -> Section | None:
    """Find the first top-level section of a kind by its title or ``@sec-type``.

    Args:
        article: The parsed JATS.
        kind: "discussion" (also matches "Conclusions") or "results".

    Returns:
        The section, or None.

    Raises:
        ValueError: If ``kind`` is not recognised.
    """
    patterns = {"discussion": _DISCUSSION, "results": _RESULTS}
    if kind not in patterns:
        raise ValueError(f"unknown section kind {kind!r}")
    pattern = patterns[kind]
    for section in top_sections(article):
        if pattern.search(section.title or "") or pattern.search(section.sec_type or ""):
            return section
    return None
