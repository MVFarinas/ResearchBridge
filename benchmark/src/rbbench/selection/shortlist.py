"""Build the PROPOSED candidate shortlist: two candidates per slot.

For each slot: search PubMed (journals x study type x years, PMC subset),
order the PMIDs deterministically by a seeded hash, and screen them one by one
until the slot has its candidates. Screening, cheapest checks first:

1. PubMed publication types match the slot's study type (provisional).
2. The article has a PMC copy; its newest version's metadata JSON in the PMC
   Cloud Service says open access, not an author manuscript, not retracted,
   and its ``license_code`` permits rewriting without the NC restriction.
3. The JATS downloads intact (MD5 from the metadata) and parses.
4. The JATS article type agrees with the study type, and the paper's own
   abstract names the design ("randomized", "cohort", "meta-analysis", ...),
   because publication types alone mislabel secondary analyses; the paper has an expert
   lay summary (if the slot requires one), a body of the configured length
   and, except for reviews, a Discussion or Conclusions section.
5. The §1.1 gate over the PMC ``license_code`` together with the JATS
   licence evidence passes with no review flag (:func:`benchmark_licence`).

Every screened PMID is logged with its outcome, so the shortlist can be
audited and reproduced. The licence evidence recorded for each candidate is
the primary-source field, its raw value, the URL it came from, and the date
it was retrieved.
"""

from __future__ import annotations

import csv
import hashlib
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

from rbbench.papers import benchmark_licence, body_words, find_section, lay_summaries
from rbbench.selection.classify import StudyType, classify, design_evidence
from rbbench.selection.config import SelectionConfig, Slot
from rbbench.sources import pmc
from rbbench.sources.eutils import EutilsClient, PubmedSummary
from rbcore.http import FetchError, PoliteFetcher
from rbcore.jats import JatsParseError, parse_jats
from rbcore.licences import LicenceEvidence, LicenceField, derive_permissions, normalise_licence

PROPOSED = "PROPOSED"


@dataclass(frozen=True, slots=True)
class Candidate:
    """One proposed candidate; field order is the CSV column order.

    Attributes:
        status: Always "PROPOSED": the owner approves the final 12.
        slot: Slot ID.
        option: "A" or "B" within the slot (screening order).
        study_type: The slot's study type.
        classification_basis: Evidence for the study type.
        journal: Journal (PubMed abbreviation).
        title: Article title.
        pmid: PubMed ID.
        pmcid: PMC ID.
        pmc_version: PMC Cloud Service version used.
        doi: DOI.
        pub_year: Publication year.
        pubmed_publication_types: PubMed publication types, "; "-joined.
        jats_article_type: JATS ``@article-type``.
        lay_summary: Title of the expert lay summary (e.g. "eLife digest").
        body_words: Body length in words.
        discussion_section: Title of the Discussion/Conclusions section, if any.
        licence: Normalised licence label.
        can_display: §1.1: the original may be displayed.
        can_rewrite: §1.1: a rewrite may be published.
        output_licence: Licence a rewrite must carry.
        licence_field: Primary-source field the gate rests on.
        licence_raw_value: Raw value of that field.
        licence_url: URL the value was read from.
        licence_retrieved: Date (UTC) the value was retrieved.
        jats_licence_evidence: JATS licence fields and raw values, for cross-checking.
        is_retracted: PMC ``is_retracted``.
        xml_url: HTTPS URL of the JATS in the PMC Cloud Service.
        xml_md5: MD5 of the JATS, as published in the metadata.
        selection_query: The PubMed query that found the article.
        screen_rank: Position in the slot's seeded screening order (1-based).
    """

    status: str
    slot: str
    option: str
    study_type: str
    classification_basis: str
    journal: str
    title: str
    pmid: str
    pmcid: str
    pmc_version: int
    doi: str
    pub_year: int | None
    pubmed_publication_types: str
    jats_article_type: str
    lay_summary: str
    body_words: int
    discussion_section: str
    licence: str
    can_display: bool
    can_rewrite: bool
    output_licence: str
    licence_field: str
    licence_raw_value: str
    licence_url: str
    licence_retrieved: str
    jats_licence_evidence: str
    is_retracted: bool
    xml_url: str
    xml_md5: str
    selection_query: str
    screen_rank: int

    @property
    def paper_key(self) -> str:
        """The version-qualified PMC key used by ingest, e.g. "PMC7853715.1"."""
        return f"{self.pmcid}.{self.pmc_version}"


@dataclass(frozen=True, slots=True)
class ScreeningRecord:
    """One screened PMID and what happened to it.

    Attributes:
        slot: Slot ID.
        rank: Position in the seeded order.
        pmid: PubMed ID.
        pmcid: PMC ID, if known.
        outcome: "accepted" or "rejected".
        reason: Why it was rejected (or the option letter when accepted).
    """

    slot: str
    rank: int
    pmid: str
    pmcid: str
    outcome: str
    reason: str


@dataclass(frozen=True, slots=True)
class Shortlist:
    """The result of a selection run.

    Attributes:
        candidates: Accepted candidates, by slot then option.
        screening: Every screened PMID, in order.
        unfilled: Slot IDs that ended with fewer candidates than configured.
    """

    candidates: list[Candidate]
    screening: list[ScreeningRecord]
    unfilled: list[str]


class _RejectedError(Exception):
    """Internal signal: the current PMID fails a screening check."""


def screening_order(pmids: list[str], seed: str) -> list[str]:
    """Order PMIDs by SHA-256 of ``seed:pmid``: deterministic, rank-independent.

    Args:
        pmids: PubMed IDs.
        seed: The config seed.

    Returns:
        The PMIDs in screening order (duplicates removed).
    """
    unique = sorted(set(pmids))
    return sorted(unique, key=lambda pmid: hashlib.sha256(f"{seed}:{pmid}".encode()).hexdigest())


def build_shortlist(
    config: SelectionConfig,
    eutils: EutilsClient,
    fetcher: PoliteFetcher,
    *,
    today: date | None = None,
    progress: Callable[[str], None] | None = None,
) -> Shortlist:
    """Run the selection.

    Args:
        config: The selection config.
        eutils: PubMed client.
        fetcher: Polite fetcher for the PMC Cloud Service (shares the cache).
        today: Date to judge licence dates against (default: today, UTC).
        progress: Optional callback for one-line progress messages.

    Returns:
        Candidates, the screening log and any unfilled slots.
    """
    report = progress or (lambda _message: None)
    candidates: list[Candidate] = []
    screening: list[ScreeningRecord] = []
    unfilled: list[str] = []
    used: set[str] = set()

    for slot in config.slots:
        query = config.query_for(slot)
        order = [p for p in screening_order(eutils.esearch(query), config.seed) if p not in used]
        order = order[: config.max_screen_per_slot]
        summaries = eutils.esummary(order)
        accepted: list[Candidate] = []
        report(f"{slot.id}: {len(order)} PMIDs to screen")

        for rank, pmid in enumerate(order, start=1):
            summary = summaries.get(pmid)
            try:
                if summary is None:
                    raise _RejectedError("no PubMed summary")
                candidate = _screen(config, slot, summary, fetcher, query, rank, today)
            except _RejectedError as rejected:
                pmcid = summary.pmcid if summary and summary.pmcid else ""
                screening.append(
                    ScreeningRecord(slot.id, rank, pmid, pmcid, "rejected", str(rejected))
                )
                continue
            option = chr(ord("A") + len(accepted))
            accepted.append(_with_option(candidate, option))
            used.add(pmid)
            screening.append(
                ScreeningRecord(slot.id, rank, pmid, candidate.pmcid, "accepted", option)
            )
            if len(accepted) == config.candidates_per_slot:
                break

        if len(accepted) < config.candidates_per_slot:
            unfilled.append(slot.id)
        report(f"{slot.id}: {len(accepted)} candidate(s)")
        candidates.extend(accepted)
    return Shortlist(candidates, screening, unfilled)


def _with_option(candidate: Candidate, option: str) -> Candidate:
    """Return a copy of a candidate with its option letter set.

    Args:
        candidate: The candidate.
        option: "A", "B", ...

    Returns:
        The updated candidate.
    """
    fields = asdict(candidate)
    fields["option"] = option
    return Candidate(**fields)


def _screen(
    config: SelectionConfig,
    slot: Slot,
    summary: PubmedSummary,
    fetcher: PoliteFetcher,
    query: str,
    rank: int,
    today: date | None,
) -> Candidate:
    """Screen one article; raise :class:`_RejectedError` at the first failed check.

    Args:
        config: The selection config.
        slot: The slot being filled.
        summary: The article's PubMed summary.
        fetcher: Polite fetcher for the PMC Cloud Service.
        query: The slot's PubMed query (recorded on the candidate).
        rank: Screening position.
        today: Date for licence date checks.

    Returns:
        The candidate (option letter unset).

    Raises:
        _RejectedError: With the reason, when any check fails.
    """
    lab = slot.study_type is StudyType.LAB_MECHANISTIC
    # 1. Cheap provisional check on publication types before any download.
    provisional = classify(summary.pubtypes, None, lab_query_match=lab)
    if provisional.study_type is None:
        raise _RejectedError(provisional.basis)
    if provisional.study_type is not slot.study_type:
        raise _RejectedError(
            f"classified as {provisional.study_type.value}, slot needs {slot.study_type.value}"
        )
    if summary.pmcid is None:
        raise _RejectedError("no PMC copy")

    # 2. The PMC Cloud Service metadata: the primary licence source.
    try:
        version = pmc.latest_version(fetcher, summary.pmcid)
        record = pmc.fetch_record(fetcher, summary.pmcid, version)
    except (pmc.PmcError, FetchError) as exc:
        raise _RejectedError(f"PMC Cloud Service: {exc}") from None
    if record.is_retracted:
        raise _RejectedError("retracted (PMC is_retracted)")
    if record.is_manuscript or not record.is_pmc_openaccess:
        raise _RejectedError("author manuscript or not in the PMC Open Access Subset")
    if not record.license_code:
        raise _RejectedError("no license_code in PMC metadata")
    quick = derive_permissions(normalise_licence(record.license_code))
    if not quick.can_rewrite or quick.non_commercial:
        raise _RejectedError(f"license_code {record.license_code!r} does not permit benchmark use")

    # 3. The JATS itself, integrity-checked and parsed safely.
    try:
        article = parse_jats(pmc.fetch_jats(fetcher, record))
    except (pmc.PmcError, FetchError, JatsParseError) as exc:
        raise _RejectedError(f"JATS: {exc}") from None

    # 4. Study type confirmed by the publisher, plus content requirements.
    final = classify(summary.pubtypes, article.article_type, lab_query_match=lab)
    if final.study_type is not slot.study_type:
        raise _RejectedError(final.basis)
    abstract = article.abstract.text if article.abstract else ""
    phrase = design_evidence(slot.study_type, abstract)
    if phrase is None:
        raise _RejectedError(f"abstract does not name a {slot.study_type.value} design")
    summaries = lay_summaries(article)
    if slot.require_lay_summary and not summaries:
        raise _RejectedError("no expert lay summary (eLife digest / PLOS author summary)")
    words = body_words(article)
    if not config.min_body_words <= words <= config.max_body_words:
        raise _RejectedError(f"body has {words} words, outside the configured range")
    discussion = find_section(article, "discussion")
    if discussion is None and slot.study_type is not StudyType.REVIEW:
        raise _RejectedError("no Discussion or Conclusions section")

    # 5. The §1.1 gate on the primary source plus the JATS, with no review flag.
    evidence = LicenceEvidence(LicenceField.PMC_LICENSE_CODE, record.license_code)
    gate = benchmark_licence(article, [evidence], today=today)
    if not gate.usable:
        raise _RejectedError("; ".join(gate.reasons))
    permissions = gate.decision.permissions
    jats_evidence = article.permissions.evidence() if article.permissions else ()

    return Candidate(
        status=PROPOSED,
        slot=slot.id,
        option="",
        study_type=slot.study_type.value,
        classification_basis=f"{final.basis}; abstract says {phrase!r}",
        journal=summary.journal,
        title=summary.title or record.title,
        pmid=summary.pmid,
        pmcid=record.pmcid,
        pmc_version=record.version,
        doi=record.doi or summary.doi or "",
        pub_year=summary.year,
        pubmed_publication_types="; ".join(summary.pubtypes),
        jats_article_type=article.article_type or "",
        lay_summary=(summaries[0].title or summaries[0].abstract_type) if summaries else "",
        body_words=words,
        discussion_section=(discussion.title or "") if discussion else "",
        licence=gate.decision.licence.label,
        can_display=permissions.can_display,
        can_rewrite=permissions.can_rewrite,
        output_licence=permissions.output_licence.label if permissions.output_licence else "",
        licence_field=LicenceField.PMC_LICENSE_CODE.value,
        licence_raw_value=record.license_code,
        licence_url=record.json_url,
        licence_retrieved=pmc.retrieved_on(fetcher, record.json_url).isoformat(),
        jats_licence_evidence=" | ".join(
            f"{item.field.value}={item.value}"
            + (f" (specific-use={item.specific_use})" if item.specific_use else "")
            for item in jats_evidence
            if item.field.is_machine_readable
        ),
        is_retracted=record.is_retracted,
        xml_url=record.xml_url,
        xml_md5=record.xml_md5 or "",
        selection_query=query,
        screen_rank=rank,
    )


CANDIDATE_COLUMNS = tuple(Candidate.__dataclass_fields__)
SCREENING_COLUMNS = tuple(ScreeningRecord.__dataclass_fields__)


def write_candidates(path: Path, candidates: list[Candidate]) -> None:
    """Write candidates.csv (booleans as true/false).

    Args:
        path: Destination.
        candidates: The candidates.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CANDIDATE_COLUMNS, lineterminator="\n")
        writer.writeheader()
        for candidate in candidates:
            row = asdict(candidate)
            writer.writerow(
                {k: str(v).lower() if isinstance(v, bool) else v for k, v in row.items()}
            )


def read_candidates(path: Path) -> list[Candidate]:
    """Read candidates.csv back.

    Args:
        path: The CSV written by :func:`write_candidates`.

    Returns:
        The candidates.

    Raises:
        ValueError: If a column is missing.
    """
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = set(CANDIDATE_COLUMNS) - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"{path}: missing columns {sorted(missing)}")
        return [_candidate_from_row(row) for row in reader]


def _candidate_from_row(row: dict[str, str]) -> Candidate:
    """Convert one CSV row back into a candidate, restoring the typed columns.

    Args:
        row: A row of candidates.csv.

    Returns:
        The candidate.
    """
    typed: dict[str, object] = {}
    for name, field in Candidate.__dataclass_fields__.items():
        text = row[name]
        if field.type in ("int", "int | None"):
            typed[name] = int(text) if text else None
        elif field.type == "bool":
            typed[name] = text == "true"
        else:
            typed[name] = text
    return Candidate(**typed)  # type: ignore[arg-type]


def write_screening_log(path: Path, records: list[ScreeningRecord]) -> None:
    """Write the screening log CSV.

    Args:
        path: Destination.
        records: Every screened PMID.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SCREENING_COLUMNS, lineterminator="\n")
        writer.writeheader()
        for record in records:
            writer.writerow(asdict(record))
