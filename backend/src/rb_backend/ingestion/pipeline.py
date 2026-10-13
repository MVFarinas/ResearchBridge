"""Ingest one PMC article: metadata, licence provenance, full text, gate.

:func:`ingest_pmc_article` is idempotent and is also the re-check: running it
again for a stored article re-reads the bucket listing and the metadata (never
cached), records whether the licence code and retraction flag still say the
same, re-parses the XML only if its MD5 or the parser changed, and recomputes
the gate. That is how the corpus stays current, as the PMC Cloud Service terms
ask of redistributors.

Order of work for the latest version of an article:

1. List the versions in the bucket; the highest is current. If none is listed
   any more, a stored current version is marked withdrawn and sent to licence
   review, so a human decides whether to keep it (it stops being displayable).
2. Fetch its JSON metadata.
3. If the ``license_code`` alone refuses the paper (``TDM`` author
   manuscripts), the XML is never downloaded. Otherwise fetch the XML
   (MD5-checked) if it is new or changed, and parse it with rbcore. Text
   removed after an earlier rejection is fetched again once the gate stops
   rejecting the version.
4. In one transaction: upsert the paper and version, record the
   ``license_code`` (with history) and ``is_retracted``, store the content and
   every ``<permissions>`` block (or purge stored text the code now refuses),
   and recompute the licence gate for the version and its parts. A version
   the gate rejects loses its stored text in the same step.

Network requests happen before the transaction. Because the evidence and the
decision drawn from it are written together, a crash can never leave a
version approved on licence records it no longer has; the next run resumes.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum

from django.db import transaction
from django.utils import timezone

import rbcore
from rb_backend.corpus.gate import evaluate_version
from rb_backend.corpus.models import ContentState, GateStatus, Paper, PaperVersion, Source
from rb_backend.corpus.precedence import DEFINITE_REFUSALS, resolve_licence
from rb_backend.corpus.retention import purge_content
from rb_backend.identifiers import normalise_doi
from rb_backend.ingestion.pmc import PmcBucket, PmcError, PmcMetadata, normalise_pmcid
from rb_backend.ingestion.store import store_article, sync_source_records
from rbcore.http import FetchError
from rbcore.jats import Article, JatsParseError, parse_jats
from rbcore.licences import LicenceEvidence, LicenceField

logger = logging.getLogger(__name__)

RETRACTION_SOURCE_PMC = "pmc:is_retracted"
PARSER_VERSION = f"rbcore-{rbcore.__version__}"


class IngestOutcome(StrEnum):
    """What one ingestion run did."""

    NOT_IN_BUCKET = "not-in-bucket"
    WITHDRAWN = "withdrawn"
    CREATED = "created"
    UPDATED = "updated"
    UNCHANGED = "unchanged"


@dataclass(frozen=True, slots=True)
class IngestReport:
    """The result of ingesting (or re-checking) one article.

    Attributes:
        pmcid: The PMC ID.
        version_id: The current version ingested (or found withdrawn), if any.
        outcome: Created, updated, unchanged, withdrawn or not in the bucket.
        gate_status: The version's gate status afterwards.
        licence_family: The decided (or proposed) licence family.
        content_parsed: Whether the XML was (re)parsed in this run.
    """

    pmcid: str
    version_id: str | None
    outcome: IngestOutcome
    gate_status: GateStatus | None = None
    licence_family: str | None = None
    content_parsed: bool = False


@dataclass(frozen=True, slots=True)
class _Content:
    """A downloaded XML document and the result of parsing it.

    Attributes:
        data: The XML bytes (MD5-checked by the bucket client).
        article: The parsed article, or None if parsing failed.
        error: Why parsing failed ("" if it succeeded).
    """

    data: bytes
    article: Article | None
    error: str = ""


def ingest_pmc_article(
    pmcid: str,
    *,
    bucket: PmcBucket,
    now: datetime | None = None,
    today: date | None = None,
) -> IngestReport:
    """Ingest or re-check one article from the PMC Cloud Service.

    Args:
        pmcid: PMC ID, with or without the ``PMC`` prefix.
        bucket: The bucket client.
        now: Timestamp to record (default: now).
        today: Date for licence dates (default: today, UTC).

    Returns:
        What happened.

    Raises:
        rb_backend.ingestion.pmc.PmcError: For malformed bucket responses or
            an XML whose MD5 does not match (the task is retried).
        rbcore.http.FetchError: If a request fails (the task is retried).
    """
    pmcid = normalise_pmcid(pmcid)
    now = now or timezone.now()
    versions = bucket.list_versions(pmcid)
    if not versions:
        return _record_unlisted(pmcid, now=now, today=today)

    # Network first: metadata, then the XML only if it is needed and allowed.
    version_id = versions[-1]
    metadata, raw = bucket.metadata(version_id)
    metadata_url = bucket.metadata_url(version_id)
    refused = _code_refuses(metadata)
    try:
        content = None if refused else _fetch_content(version_id, metadata, bucket)
    except (FetchError, PmcError):
        # Record what is known (the gate keeps a new version pending) so the
        # re-check finds it again, then let the worker retry the task.
        _write(metadata, raw, metadata_url, refused=refused, content=None, now=now, today=today)
        raise

    report = _write(
        metadata, raw, metadata_url, refused=refused, content=content, now=now, today=today
    )

    # Text removed on an earlier rejection is needed again as soon as the new
    # evidence stops the gate rejecting the version (it stays pending meanwhile).
    if content is None and not refused and report.gate_status != GateStatus.REJECTED:
        content = _fetch_content(version_id, metadata, bucket)
        if content is not None:
            report = _write(
                metadata, raw, metadata_url, refused=False, content=content, now=now, today=today
            )
    logger.info(
        "%s: %s, gate %s (%s)",
        version_id,
        report.outcome,
        report.gate_status,
        report.licence_family,
    )
    return report


def _record_unlisted(pmcid: str, *, now: datetime, today: date | None) -> IngestReport:
    """Handle an article the bucket does not list: not there yet, or withdrawn.

    A stored current version is marked withdrawn (the first time only, so the
    review evidence stays stable), its check time is recorded, and the gate
    is recomputed, which sends it to licence review.

    Args:
        pmcid: The normalised PMC ID.
        now: Check time.
        today: Date for licence dates.

    Returns:
        ``not-in-bucket`` if nothing is stored, otherwise ``withdrawn``.
    """
    with transaction.atomic():
        version = PaperVersion.objects.filter(
            source=Source.PMC, paper__pmcid=pmcid, is_current=True
        ).first()
        # Never ingested: ESearch can know an ID before the bucket holds it.
        if version is None:
            logger.info("%s is not in the PMC bucket (yet)", pmcid)
            return IngestReport(pmcid, None, IngestOutcome.NOT_IN_BUCKET)

        # Stored but no longer listed: record it and let the gate fail closed.
        if version.source_withdrawn_at is None:
            version.source_withdrawn_at = now
        version.last_checked_at = now
        version.save(update_fields=["source_withdrawn_at", "last_checked_at", "updated_at"])
        status = evaluate_version(version, today=today, now=now)

    logger.warning("%s is no longer listed in the PMC bucket; gate %s", pmcid, status)
    return IngestReport(
        pmcid, version.source_version_id, IngestOutcome.WITHDRAWN, status, version.licence_family
    )


def _fetch_content(version_id: str, metadata: PmcMetadata, bucket: PmcBucket) -> _Content | None:
    """Download and parse the XML if the stored version needs it.

    Args:
        version_id: The bucket version ID, e.g. ``PMC10718527.1``.
        metadata: Its fresh metadata.
        bucket: The bucket client.

    Returns:
        The downloaded content, or None if the stored content is current.

    Raises:
        rb_backend.ingestion.pmc.PmcError: No XML URL, or an MD5 mismatch.
        rbcore.http.FetchError: If the download fails.
    """
    stored = PaperVersion.objects.filter(source=Source.PMC, source_version_id=version_id).first()
    if stored is not None and not _needs_content(stored, metadata):
        return None
    data = bucket.article_xml(metadata)
    try:
        return _Content(data, parse_jats(data))
    except JatsParseError as exc:
        # A parse failure is recorded; the gate sends the version to review.
        logger.warning("%s: JATS parse error: %s", version_id, exc)
        return _Content(data, None, f"JATS parse error: {exc}")


def _write(
    metadata: PmcMetadata,
    raw: bytes,
    metadata_url: str,
    *,
    refused: bool,
    content: _Content | None,
    now: datetime,
    today: date | None,
) -> IngestReport:
    """Store the fetched evidence and recompute the gate, in one transaction.

    Args:
        metadata: Parsed metadata.
        raw: The metadata bytes.
        metadata_url: Where they were fetched from.
        refused: Whether the licence code alone refuses the version.
        content: Downloaded content to store, or None.
        now: Retrieval time.
        today: Date for licence dates.

    Returns:
        The report for this run.
    """
    with transaction.atomic():
        # Metadata, licence code and retraction.
        version, created, changed = _upsert_version(metadata, raw, metadata_url, now)

        # A refusal by the licence code means no full text is kept at all.
        if refused and version.content_state != ContentState.SKIPPED:
            purge_content(version, superseded_at=now)
            _set_content_state(version, ContentState.SKIPPED, "")
            changed = True
        elif content is not None:
            _store_content(version, metadata, content, now)

        # The gate, from the stored records only, before anything commits.
        status = evaluate_version(version, today=today, now=now)

    if created:
        outcome = IngestOutcome.CREATED
    elif changed or content is not None:
        outcome = IngestOutcome.UPDATED
    else:
        outcome = IngestOutcome.UNCHANGED
    return IngestReport(
        metadata.pmcid,
        version.source_version_id,
        outcome,
        status,
        version.licence_family,
        content is not None and content.article is not None,
    )


def _code_refuses(metadata: PmcMetadata) -> bool:
    """Whether the PMC licence code alone is a definite refusal (e.g. ``TDM``).

    Args:
        metadata: The version's metadata.

    Returns:
        True if the code decides "no display, no rewrite" without review.
    """
    if not metadata.license_code:
        return False
    decision = resolve_licence(
        [LicenceEvidence(LicenceField.PMC_LICENSE_CODE, metadata.license_code)]
    )
    return decision.licence.family in DEFINITE_REFUSALS and not decision.needs_review


def _needs_content(version: PaperVersion, metadata: PmcMetadata) -> bool:
    """Whether the XML must be (re)fetched and parsed.

    Args:
        version: The stored version.
        metadata: Its fresh metadata.

    Returns:
        True if never parsed, failed before, the XML's MD5 changed, or the
        parser changed. Text removed because the gate rejected the version is
        fetched again only once the gate no longer rejects it (for example
        after a reviewer approves it).
    """
    changed = (
        version.content_md5 != (metadata.xml_md5 or "") or version.parser_version != PARSER_VERSION
    )
    if version.content_state == ContentState.REMOVED:
        return changed or version.gate_status != GateStatus.REJECTED
    return version.content_state != ContentState.PARSED or changed


def _upsert_version(
    metadata: PmcMetadata, raw: bytes, metadata_url: str, now: datetime
) -> tuple[PaperVersion, bool, bool]:
    """Create or update the paper and version rows from fresh metadata.

    Args:
        metadata: Parsed metadata.
        raw: The metadata bytes (hashed to detect changes).
        metadata_url: Where they were fetched from.
        now: Retrieval time.

    Returns:
        The version, whether it was created, and whether anything changed.
    """
    paper = _upsert_paper(metadata)
    digest = hashlib.sha256(raw).hexdigest()
    version, created = PaperVersion.objects.get_or_create(
        source=Source.PMC,
        source_version_id=metadata.version_id,
        defaults={
            "paper": paper,
            "version_number": metadata.version,
            "metadata_url": metadata_url,
        },
    )
    changed = created or version.metadata_sha256 != digest

    # Refresh the source's own fields every time; they are cheap and authoritative.
    version.title = version.title or metadata.title
    version.citation = metadata.citation
    version.is_pmc_openaccess = metadata.is_pmc_openaccess
    version.is_manuscript = metadata.is_manuscript
    version.is_historical_ocr = metadata.is_historical_ocr
    version.is_retracted = metadata.is_retracted
    version.metadata_url = metadata_url
    version.metadata_sha256 = digest
    version.source_metadata = dict(metadata.raw)
    version.content_url = metadata.xml_url or ""
    version.metadata_retrieved_at = now
    version.last_checked_at = now
    # Listed again (or for the first time): any earlier withdrawal no longer holds.
    changed |= version.source_withdrawn_at is not None
    version.source_withdrawn_at = None
    version.save()

    # Exactly one current version: this one, the latest in the bucket.
    PaperVersion.objects.filter(paper=paper, is_current=True).exclude(pk=version.pk).update(
        is_current=False
    )
    if not version.is_current:
        version.is_current = True
        version.save(update_fields=["is_current", "updated_at"])

    # The licence code, with history (field, value, source URL, retrieval date).
    evidence = (
        [LicenceEvidence(LicenceField.PMC_LICENSE_CODE, metadata.license_code)]
        if metadata.license_code
        else []
    )
    changed |= sync_source_records(
        version,
        [LicenceField.PMC_LICENSE_CODE],
        evidence,
        source_url=metadata_url,
        retrieved_at=now,
    )
    _record_retraction(paper, metadata.is_retracted, now)
    return version, created, changed


def _upsert_paper(metadata: PmcMetadata) -> Paper:
    """Find or create the paper by PMC ID and fill in missing identifiers.

    Args:
        metadata: Parsed metadata.

    Returns:
        The paper.
    """
    doi = normalise_doi(metadata.doi)
    paper, _ = Paper.objects.get_or_create(pmcid=metadata.pmcid)
    # A DOI already held by another paper is never taken over; log it for a human.
    if doi and not paper.doi:
        if Paper.objects.filter(doi=doi).exclude(pk=paper.pk).exists():
            logger.warning("%s: DOI %s already belongs to another paper", metadata.pmcid, doi)
        else:
            paper.doi = doi
    if metadata.pmid and not paper.pmid:
        paper.pmid = metadata.pmid
    paper.save()
    return paper


def _record_retraction(paper: Paper, is_retracted: bool, now: datetime) -> None:
    """Apply PMC's ``is_retracted`` flag to the paper.

    PMC gives no retraction date, so ``retraction_date`` stays empty and
    ``retraction_recorded_at`` says when ResearchBridge learnt of it. A flag
    PMC later withdraws is cleared only if PMC was the source that set it.

    Args:
        paper: The paper.
        is_retracted: The current version's flag.
        now: Current time.
    """
    if is_retracted and not paper.is_retracted:
        paper.is_retracted = True
        paper.retraction_source = RETRACTION_SOURCE_PMC
        paper.retraction_recorded_at = now
        paper.save(update_fields=["is_retracted", "retraction_source", "retraction_recorded_at"])
    elif not is_retracted and paper.retraction_source == RETRACTION_SOURCE_PMC:
        paper.is_retracted = False
        paper.retraction_source = ""
        paper.retraction_recorded_at = None
        paper.save(update_fields=["is_retracted", "retraction_source", "retraction_recorded_at"])


def _store_content(
    version: PaperVersion, metadata: PmcMetadata, content: _Content, now: datetime
) -> None:
    """Store a version's parsed XML, or record why parsing failed.

    Runs inside the caller's transaction.

    Args:
        version: The version.
        metadata: Its metadata.
        content: The downloaded (and parsed, if possible) XML.
        now: Retrieval time.
    """
    if content.article is None:
        _set_content_state(version, ContentState.FAILED, content.error)
        return
    store_article(version, content.article, source_url=metadata.xml_url or "", retrieved_at=now)
    version.content_md5 = metadata.xml_md5 or ""
    version.content_sha256 = hashlib.sha256(content.data).hexdigest()
    version.content_retrieved_at = now
    version.parser_version = PARSER_VERSION
    version.content_state = ContentState.PARSED
    version.content_error = ""
    version.save()


def _set_content_state(version: PaperVersion, state: ContentState, error: str) -> None:
    """Record a version's content state.

    Args:
        version: The version.
        state: The new state.
        error: Why fetching or parsing failed ("" otherwise).
    """
    version.content_state = state
    version.content_error = error
    version.save(update_fields=["content_state", "content_error", "updated_at"])
