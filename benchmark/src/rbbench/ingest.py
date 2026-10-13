"""Ingest: JATS -> paragraph-aligned units with stable IDs, and a proposed passage per paper.

A *unit* is one body paragraph of one paper version. Its ID is
``<paper key>#<paragraph ID>``, where the paper key is version-qualified
(``PMC7853715.1``) and the paragraph ID is rbcore's stable positional ID
(``sec2.1-p3``), so re-ingesting the same version always gives the same IDs.

A *passage* is the short run of consecutive paragraphs that is rewritten and
rated (decisions.md §1.4: about 20-30 claims per rewrite, so roughly 350-650
words). Passages are proposed by a deterministic strategy and recorded as
PROPOSED, so the owner can adjust them before any rewrite is generated.

The §1.1 gate runs twice at ingest: per paper
(:func:`rbbench.papers.benchmark_licence`, plus a refusal of retracted papers)
and per paragraph (:func:`rbcore.licences.decide_part`), and a paragraph that
may not be rewritten never enters a proposed passage. Because the owner may
edit ``passages.jsonl`` afterwards, every later step that sends source text
anywhere re-checks it with :func:`gate_violations` /
:func:`require_rewritable`, which fail closed.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from rbbench.jsonl import read_jsonl, write_jsonl
from rbbench.papers import (
    benchmark_licence,
    find_section,
    lay_summaries,
    section_paths,
    word_count,
)
from rbcore.jats import Article, Paragraph, parse_jats
from rbcore.licences import LicenceDecision, LicenceEvidence, LicenceField, decide_part

PROPOSED = "PROPOSED"
RETRACTED_REASON = "retracted (PMC is_retracted)"
DEFAULT_STRATEGIES = ("discussion", "results", "body")
MIN_PARAGRAPH_WORDS = 20


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    """One piece of primary-source licence evidence, with provenance.

    Attributes:
        field: A :class:`rbcore.licences.LicenceField` value.
        value: The raw value.
        url: Where it was read (or the manifest that recorded it).
        retrieved: Retrieval date, ISO 8601.
    """

    field: str
    value: str
    url: str
    retrieved: str

    def evidence(self) -> LicenceEvidence:
        """Return the rbcore evidence object for the gate.

        Returns:
            The evidence.
        """
        return LicenceEvidence(LicenceField(self.field), self.value)


@dataclass(frozen=True, slots=True)
class PaperSource:
    """Everything needed to ingest one paper.

    Attributes:
        paper_key: Version-qualified key, e.g. "PMC7853715.1".
        jats: The JATS bytes (untrusted; parsed by rbcore.jats).
        evidence: Primary-source licence evidence.
        retracted: Whether the primary source marks the paper retracted
            (PMC ``is_retracted``); a retracted paper is never usable.
        metadata: Extra fields carried into the paper record (slot, study
            type, journal, ...).
    """

    paper_key: str
    jats: bytes
    evidence: tuple[EvidenceRecord, ...]
    retracted: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SourceUnit:
    """One body paragraph: the alignment unit for rewriting and rating.

    Attributes:
        unit_id: ``<paper key>#<paragraph ID>``.
        paper_key: The paper.
        paragraph_id: rbcore's stable paragraph ID.
        section_path: Titles of the enclosing sections, outermost first.
        kind: rbcore paragraph kind ("p", "list-item", ...).
        text: Plain text.
        words: Word count.
        can_rewrite: §1.1 at paragraph level (article decision plus any
            paragraph-level permissions blocks).
    """

    unit_id: str
    paper_key: str
    paragraph_id: str
    section_path: tuple[str, ...]
    kind: str
    text: str
    words: int
    can_rewrite: bool

    def to_record(self) -> dict[str, Any]:
        """Return the JSON-serialisable form.

        Returns:
            A dict with ``record_type`` "unit".
        """
        return {
            "record_type": "unit",
            "unit_id": self.unit_id,
            "paper_key": self.paper_key,
            "paragraph_id": self.paragraph_id,
            "section_path": list(self.section_path),
            "kind": self.kind,
            "text": self.text,
            "words": self.words,
            "can_rewrite": self.can_rewrite,
        }

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> SourceUnit:
        """Build a unit from its JSON form.

        Args:
            record: A dict written by :meth:`to_record`.

        Returns:
            The unit.
        """
        return cls(
            unit_id=str(record["unit_id"]),
            paper_key=str(record["paper_key"]),
            paragraph_id=str(record["paragraph_id"]),
            section_path=tuple(record["section_path"]),
            kind=str(record["kind"]),
            text=str(record["text"]),
            words=int(record["words"]),
            can_rewrite=bool(record["can_rewrite"]),
        )


@dataclass(frozen=True, slots=True)
class Passage:
    """The paragraphs of one paper selected for rewriting.

    Attributes:
        passage_id: ``<paper key>:<strategy>``.
        paper_key: The paper.
        paragraph_ids: Consecutive paragraph IDs, in order.
        words: Total words.
        strategy: How the passage was chosen.
        status: "PROPOSED" until the owner approves it.
    """

    passage_id: str
    paper_key: str
    paragraph_ids: tuple[str, ...]
    words: int
    strategy: str
    status: str = PROPOSED

    def to_record(self) -> dict[str, Any]:
        """Return the JSON-serialisable form.

        Returns:
            A dict with ``record_type`` "passage".
        """
        return {
            "record_type": "passage",
            "passage_id": self.passage_id,
            "paper_key": self.paper_key,
            "paragraph_ids": list(self.paragraph_ids),
            "words": self.words,
            "strategy": self.strategy,
            "status": self.status,
        }

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> Passage:
        """Build a passage from its JSON form.

        Args:
            record: A dict written by :meth:`to_record`.

        Returns:
            The passage.
        """
        return cls(
            passage_id=str(record["passage_id"]),
            paper_key=str(record["paper_key"]),
            paragraph_ids=tuple(record["paragraph_ids"]),
            words=int(record["words"]),
            strategy=str(record["strategy"]),
            status=str(record.get("status", PROPOSED)),
        )


@dataclass(frozen=True, slots=True)
class IngestedPaper:
    """A parsed paper with its licence decision and units.

    Attributes:
        paper_key: Version-qualified key.
        title: Article title.
        doi: DOI, if any.
        journal: Journal title.
        article_type: JATS ``@article-type``.
        licence: Licence label from the decision.
        usable: Whether the §1.1 gate allows benchmark use (and the paper is
            not retracted).
        retracted: Whether the primary source marks the paper retracted.
        licence_reasons: The decision's reasons and any refusal reasons.
        evidence: Primary-source evidence used.
        lay_summaries: Expert lay summaries as (title, text) pairs.
        units: Body paragraphs in document order.
        passage: The proposed passage, or None when none qualifies.
        metadata: Extra fields from the source.
    """

    paper_key: str
    title: str
    doi: str | None
    journal: str | None
    article_type: str | None
    licence: str
    usable: bool
    retracted: bool
    licence_reasons: tuple[str, ...]
    evidence: tuple[EvidenceRecord, ...]
    lay_summaries: tuple[tuple[str, str], ...]
    units: tuple[SourceUnit, ...]
    passage: Passage | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_record(self) -> dict[str, Any]:
        """Return the JSON-serialisable paper record (units and passage are stored separately).

        Returns:
            A dict with ``record_type`` "paper".
        """
        return {
            "record_type": "paper",
            "paper_key": self.paper_key,
            "title": self.title,
            "doi": self.doi,
            "journal": self.journal,
            "article_type": self.article_type,
            "licence": self.licence,
            "usable": self.usable,
            "retracted": self.retracted,
            "licence_reasons": list(self.licence_reasons),
            "evidence": [evidence_dict(e) for e in self.evidence],
            "lay_summaries": [{"title": t, "text": x} for t, x in self.lay_summaries],
            "n_units": len(self.units),
            "passage_id": self.passage.passage_id if self.passage else None,
            "metadata": self.metadata,
        }


def evidence_dict(record: EvidenceRecord) -> dict[str, str]:
    """Return an evidence record as a plain dict.

    Args:
        record: The evidence record.

    Returns:
        Its fields.
    """
    return {
        "field": record.field,
        "value": record.value,
        "url": record.url,
        "retrieved": record.retrieved,
    }


def ingest_paper(
    source: PaperSource,
    *,
    today: date | None = None,
    min_words: int = 350,
    max_words: int = 650,
) -> IngestedPaper:
    """Parse one paper, apply the licence gate and propose its passage.

    Args:
        source: The paper's JATS and primary-source evidence.
        today: Date to judge licence dates against.
        min_words: Passage target minimum length (see :func:`propose_passage`).
        max_words: Passage upper bound.

    Returns:
        The ingested paper. Units are produced even when the paper is not
        usable, each marked ``can_rewrite=False``, so the refusal is visible.
        A retracted paper is refused whatever its licence.

    Raises:
        rbcore.jats.JatsParseError: If the JATS is malformed or unsafe.
    """
    article = parse_jats(source.jats)
    gate = benchmark_licence(article, [e.evidence() for e in source.evidence], today=today)

    # Retraction is checked here, not only at selection: a paper can be
    # retracted after the shortlist was built, and ingest feeds the rewrite.
    refusals = (*gate.reasons, *((RETRACTED_REASON,) if source.retracted else ()))
    usable = not refusals

    # Units carry the paper-level result, so a refused paper has no rewritable unit.
    units = _units(source.paper_key, article, usable, gate.decision)
    passage = (
        propose_passage(source.paper_key, article, units, min_words=min_words, max_words=max_words)
        if usable
        else None
    )
    return IngestedPaper(
        paper_key=source.paper_key,
        title=article.title or "",
        doi=article.identifiers.doi,
        journal=article.journal.title,
        article_type=article.article_type,
        licence=gate.decision.licence.label,
        usable=usable,
        retracted=source.retracted,
        licence_reasons=(*gate.decision.reasons, *refusals),
        evidence=source.evidence,
        lay_summaries=tuple((s.title or s.abstract_type, s.text) for s in lay_summaries(article)),
        units=units,
        passage=passage,
        metadata=dict(source.metadata),
    )


def _units(
    paper_key: str, article: Article, paper_usable: bool, decision: LicenceDecision
) -> tuple[SourceUnit, ...]:
    """Build the body units of one article.

    Args:
        paper_key: The paper key.
        article: The parsed article.
        paper_usable: The paper-level gate result.
        decision: The article-level :class:`rbcore.licences.LicenceDecision`.

    Returns:
        Units in document order.
    """
    paths = section_paths(article)
    units: list[SourceUnit] = []
    for paragraph in article.iter_paragraphs():
        # A paragraph inherits the article decision unless it has its own blocks.
        part = decide_part(decision, paragraph.permissions)
        rewritable = paper_usable and part.permissions.can_rewrite and not part.needs_review
        units.append(
            SourceUnit(
                unit_id=f"{paper_key}#{paragraph.id}",
                paper_key=paper_key,
                paragraph_id=paragraph.id,
                section_path=paths.get(paragraph.id, ()),
                kind=paragraph.kind,
                text=paragraph.text,
                words=word_count(paragraph.text),
                can_rewrite=rewritable,
            )
        )
    return tuple(units)


def propose_passage(
    paper_key: str,
    article: Article,
    units: Sequence[SourceUnit],
    *,
    min_words: int = 350,
    max_words: int = 650,
    strategies: Sequence[str] = DEFAULT_STRATEGIES,
) -> Passage | None:
    """Propose a passage: consecutive rewritable paragraphs from one section.

    Strategies are tried in order: "discussion" (the first Discussion or
    Conclusions section, where hedges and limitations concentrate),
    "results", then "body" (the body from the start). Within the section,
    paragraphs are taken in order (prose paragraphs of at least
    :data:`MIN_PARAGRAPH_WORDS` words that may be rewritten) until at least
    ``min_words`` are collected, never exceeding ``max_words`` unless the
    first paragraph alone does; a non-qualifying paragraph ends the run so
    the passage stays consecutive. The first strategy whose run reaches
    ``min_words`` wins; if none does, the longest run of at least
    ``min_words // 2`` words is used.

    Args:
        paper_key: The paper key.
        article: The parsed article (for the section structure).
        units: The paper's units (for the paragraph-level gate and lengths).
        min_words: Target minimum length.
        max_words: Upper bound.
        strategies: Strategies to try, in order.

    Returns:
        The passage, or None when no strategy finds a run of at least
        ``min_words // 2`` rewritable words.
    """
    rewritable = {u.paragraph_id: u for u in units if u.can_rewrite}
    runs: list[Passage] = []
    for strategy in strategies:
        section = article.body if strategy == "body" else find_section(article, strategy)
        if section is None:
            continue
        chosen = _take_run(section.iter_paragraphs(), rewritable, min_words, max_words)
        if not chosen:
            continue
        passage = Passage(
            passage_id=f"{paper_key}:{strategy}",
            paper_key=paper_key,
            paragraph_ids=tuple(chosen),
            words=sum(rewritable[pid].words for pid in chosen),
            strategy=strategy,
        )
        # A full-length run from the preferred strategy wins outright.
        if passage.words >= min_words:
            return passage
        runs.append(passage)
    # Otherwise the longest shorter run, if it is not too short to rate.
    longest = max(runs, key=lambda run: run.words, default=None)
    return longest if longest is not None and longest.words >= min_words // 2 else None


def _take_run(
    paragraphs: Iterable[Paragraph],
    rewritable: dict[str, SourceUnit],
    min_words: int,
    max_words: int,
) -> list[str]:
    """Collect the first run of consecutive qualifying paragraphs.

    Args:
        paragraphs: Candidate paragraphs in order.
        rewritable: Rewritable units by paragraph ID.
        min_words: Stop once this many words are collected.
        max_words: Never exceed this (unless the first paragraph does).

    Returns:
        Paragraph IDs of the run.
    """
    chosen: list[str] = []
    total = 0
    for paragraph in paragraphs:
        unit = rewritable.get(paragraph.id)
        qualifies = unit is not None and unit.kind == "p" and unit.words >= MIN_PARAGRAPH_WORDS
        # Skip leading non-qualifying paragraphs; a gap after the start ends the run.
        if not qualifies or unit is None:
            if chosen:
                break
            continue
        if chosen and total + unit.words > max_words:
            break
        chosen.append(paragraph.id)
        total += unit.words
        if total >= min_words:
            break
    return chosen


PAPERS_FILE = "papers.jsonl"
UNITS_FILE = "units.jsonl"
PASSAGES_FILE = "passages.jsonl"


def write_ingest(out_dir: Path, papers: Sequence[IngestedPaper]) -> None:
    """Write the ingest outputs: papers, units and proposed passages (JSON Lines).

    Args:
        out_dir: Output directory (inside the gitignored data directory).
        papers: Ingested papers.
    """
    write_jsonl(out_dir / PAPERS_FILE, (paper.to_record() for paper in papers))
    write_jsonl(out_dir / UNITS_FILE, (u.to_record() for paper in papers for u in paper.units))
    write_jsonl(
        out_dir / PASSAGES_FILE,
        (paper.passage.to_record() for paper in papers if paper.passage is not None),
    )


def load_units(out_dir: Path) -> dict[str, SourceUnit]:
    """Load units written by :func:`write_ingest`.

    Args:
        out_dir: The ingest directory.

    Returns:
        Units by unit ID.
    """
    units = (SourceUnit.from_record(r) for r in read_jsonl(out_dir / UNITS_FILE))
    return {unit.unit_id: unit for unit in units}


def load_passages(out_dir: Path) -> list[Passage]:
    """Load passages written by :func:`write_ingest`.

    Args:
        out_dir: The ingest directory.

    Returns:
        Passages in file order.
    """
    return [Passage.from_record(r) for r in read_jsonl(out_dir / PASSAGES_FILE)]


def load_usable_papers(out_dir: Path) -> set[str]:
    """Return the keys of the papers the ingest gate found usable.

    Args:
        out_dir: The ingest directory.

    Returns:
        Paper keys whose ``papers.jsonl`` record says ``usable`` true.
    """
    return {str(r["paper_key"]) for r in read_jsonl(out_dir / PAPERS_FILE) if r.get("usable")}


class LicenceGateError(ValueError):
    """Raised when source text that the §1.1 gate refused would be rewritten or shown."""


def gate_violations(
    paper_key: str,
    paragraph_ids: Sequence[str],
    units: Mapping[str, SourceUnit],
    usable_papers: Collection[str] | None = None,
) -> list[str]:
    """Check that every paragraph of a passage may be rewritten (§1.1).

    Fails closed: a paragraph without a unit, a unit with ``can_rewrite``
    false, or (when ``usable_papers`` is given) a paper the ingest gate did
    not find usable is a violation.

    Args:
        paper_key: The paper.
        paragraph_ids: The paragraphs to be rewritten or shown.
        units: Units by unit ID, from ingest.
        usable_papers: Keys of usable papers, or None to rely on the units.

    Returns:
        One message per violation; empty when everything may be rewritten.
    """
    violations: list[str] = []
    if usable_papers is not None and paper_key not in usable_papers:
        violations.append(f"paper {paper_key} is not usable (licence gate or retraction)")
    for paragraph_id in paragraph_ids:
        unit = units.get(f"{paper_key}#{paragraph_id}")
        if unit is None:
            violations.append(f"paragraph {paper_key}#{paragraph_id} has no ingested unit")
        elif not unit.can_rewrite:
            violations.append(f"paragraph {unit.unit_id} may not be rewritten")
    return violations


def require_rewritable(
    passages: Sequence[Passage],
    units: Mapping[str, SourceUnit],
    usable_papers: Collection[str] | None = None,
) -> None:
    """Refuse the whole batch if any passage touches text the gate refused.

    Args:
        passages: Passages about to be rewritten.
        units: Units by unit ID.
        usable_papers: Keys of usable papers, or None to rely on the units.

    Raises:
        LicenceGateError: Listing every violation, before anything is sent.
    """
    violations = [
        f"{passage.passage_id}: {message}"
        for passage in passages
        for message in gate_violations(
            passage.paper_key, passage.paragraph_ids, units, usable_papers
        )
    ]
    if violations:
        raise LicenceGateError("licence gate (§1.1) refused: " + "; ".join(violations))


def passage_units(passage: Passage, units: dict[str, SourceUnit]) -> list[SourceUnit]:
    """Return a passage's units in order.

    Args:
        passage: The passage.
        units: Units by unit ID.

    Returns:
        The passage's units.

    Raises:
        KeyError: If a paragraph of the passage has no unit.
    """
    return [units[f"{passage.paper_key}#{pid}"] for pid in passage.paragraph_ids]
