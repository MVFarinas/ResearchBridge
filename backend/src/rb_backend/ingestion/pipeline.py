"""Ingest one PMC article: metadata, licence provenance, full text, gate.

:func:`ingest_pmc_article` is idempotent and is also the re-check: running it
again for a stored article re-reads the bucket listing and the metadata (never
cached), records whether the licence code and retraction flag still say the
same, re-parses the XML only if its MD5 or the parser changed, and recomputes
the gate. That is how the corpus stays current, as the PMC Cloud Service terms
ask of redistributors.

Order of work for the latest version of an article:

1. List the versions in the bucket; the highest is current.
2. Fetch its JSON metadata; upsert the paper and version; record the
   ``license_code`` (with history) and ``is_retracted``.
3. If the code alone refuses the paper (``TDM`` author manuscripts), stop:
   the XML is never downloaded and any stored text is purged.
4. Otherwise fetch the XML (MD5-checked), parse it with rbcore and store the
   content and every ``<permissions>`` block.
5. Recompute the licence gate for the version and its parts.

Network requests happen outside database transactions; each write phase is
atomic, so an interrupted run leaves consistent rows and the next run resumes.
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
from rb_backend.ingestion.pmc import PmcBucket, PmcMetadata, normalise_pmcid
from rb_backend.ingestion.store import purge_content, store_article, sync_source_records
from rbcore.jats import JatsParseError, parse_jats
from rbcore.licences import LicenceEvidence, LicenceField

logger = logging.getLogger(__name__)

RETRACTION_SOURCE_PMC = "pmc:is_retracted"
PARSER_VERSION = f"rbcore-{rbcore.__version__}"


class IngestOutcome(StrEnum):
    """What one ingestion run did."""

    NOT_IN_BUCKET = "not-in-bucket"
    CREATED = "created"
    UPDATED = "updated"
    UNCHANGED = "unchanged"


@dataclass(frozen=True, slots=True)
class IngestReport:
    """The result of ingesting (or re-checking) one article.

    Attributes:
        pmcid: The PMC ID.
        version_id: The current version ingested, if any.
        outcome: Created, updated, unchanged or not in the bucket.
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
    versions = bucket.list_versions(pmcid)
    if not versions:
        logger.info("%s is not in the PMC bucket (yet)", pmcid)
        return IngestReport(pmcid, None, IngestOutcome.NOT_IN_BUCKET)

    version_id = versions[-1]
    metadata, raw = bucket.metadata(version_id)
    now = now or timezone.now()

    # Step 2: metadata, licence code and retraction, atomically.
    with transaction.atomic():
        version, created, metadata_changed = _upsert_version(
            metadata, raw, bucket.metadata_url(version_id), now
        )

    # Step 3: a refusal by the licence code means the full text is never fetched.
    refused = _code_refuses(metadata)
    content_parsed = False
    if refused:
        if version.content_state != ContentState.SKIPPED:
            with transaction.atomic():
                purge_content(version, superseded_at=now)
                _set_content_state(version, ContentState.SKIPPED, "")
            metadata_changed = True
    elif _needs_content(version, metadata):
        # Step 4: download outside any transaction, then store atomically.
        _fetch_and_store(version, metadata, bucket, now)
        content_parsed = True

    # Step 5: the gate, from the stored records only.
    status = evaluate_version(version, today=today, now=now)
    if created:
        outcome = IngestOutcome.CREATED
    elif metadata_changed or content_parsed:
        outcome = IngestOutcome.UPDATED
    else:
        outcome = IngestOutcome.UNCHANGED
    logger.info("%s: %s, gate %s (%s)", version_id, outcome, status, version.licence_family)
    return IngestReport(pmcid, version_id, outcome, status, version.licence_family, content_parsed)


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
        parser changed.
    """
    return (
        version.content_state != ContentState.PARSED
        or version.content_md5 != (metadata.xml_md5 or "")
        or version.parser_version != PARSER_VERSION
    )


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


def normalise_doi(value: str | None) -> str | None:
    """Lower-case a DOI and strip any resolver prefix.

    Args:
        value: A DOI or DOI URL, or None.

    Returns:
        The bare, lower-cased DOI, or None.
    """
    if not value:
        return None
    text = value.strip()
    for prefix in ("https://doi.org/", "http://doi.org/", "https://dx.doi.org/", "doi:"):
        if text.lower().startswith(prefix):
            text = text[len(prefix) :]
    return text.lower() or None


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


def _fetch_and_store(
    version: PaperVersion, metadata: PmcMetadata, bucket: PmcBucket, now: datetime
) -> None:
    """Download, parse and store a version's XML, or record why parsing failed.

    Args:
        version: The version.
        metadata: Its metadata.
        bucket: The bucket client.
        now: Retrieval time.

    Raises:
        rb_backend.ingestion.pmc.PmcError: No XML URL, or an MD5 mismatch.
        rbcore.http.FetchError: If the download fails.
    """
    data = bucket.article_xml(metadata)
    try:
        article = parse_jats(data)
    except JatsParseError as exc:
        # A parse failure is recorded; the gate sends the version to review.
        with transaction.atomic():
            _set_content_state(version, ContentState.FAILED, f"JATS parse error: {exc}")
        logger.warning("%s: JATS parse error: %s", version.source_version_id, exc)
        return

    with transaction.atomic():
        store_article(version, article, source_url=metadata.xml_url or "", retrieved_at=now)
        version.content_md5 = metadata.xml_md5 or ""
        version.content_sha256 = hashlib.sha256(data).hexdigest()
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
