"""Entry point 2: look a paper up by DOI, PMC ID, PubMed ID, arXiv ID or title (§1.5).

Outcomes:

* ``in_corpus``: the paper is in the corpus and displayable; open it.
* ``queued``: not in the corpus yet, but the primary source (the PMC
  ``license_code`` in the PMC Cloud Service metadata) permits display, so it
  was queued for the worker; poll the request's status ("being prepared").
* ``candidates``: a title was given; matching papers from the corpus and
  OpenAlex are listed, and the reader picks one (titles are never guessed).
* ``not_available``: not here and not eligible (or not in PMC's open-access
  datasets); the response links to the DOI.
* ``budget_exhausted``: today's on-demand ingestion budget is spent.
* ``unavailable``: a source needed for the check could not be reached.

Eligibility is checked at the primary source only. OpenAlex licence fields
never decide anything (decisions.md §1.1 addendum), and the licence gate runs
again on the full record when the worker ingests the article.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, time
from enum import StrEnum
from typing import Any

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from rb_backend.corpus import access
from rb_backend.corpus.models import GateStatus, Paper
from rb_backend.corpus.precedence import resolve_licence
from rb_backend.discovery.keys import paper_key
from rb_backend.discovery.links import doi_url, scholar_search_url
from rb_backend.discovery.models import LookupRequest
from rb_backend.discovery.search import SearchParams, run_search
from rb_backend.identifiers import ParsedIdentifier, normalise_doi, parse_identifier
from rb_backend.ingestion.pmc import PmcBucket, PmcError
from rb_backend.ingestion.runtime import get_bucket
from rb_backend.ingestion.tasks import job_status, queue_ingest
from rb_backend.metadata.errors import UpstreamError
from rb_backend.metadata.idconv import IdRecord, IdType, parse_record
from rb_backend.metadata.services import MetadataClients, convert_id
from rbcore.http import FetchError
from rbcore.licences import LicenceEvidence, LicenceField


class LookupOutcome(StrEnum):
    """The result of a lookup."""

    IN_CORPUS = "in_corpus"
    QUEUED = "queued"
    CANDIDATES = "candidates"
    NOT_AVAILABLE = "not_available"
    BUDGET_EXHAUSTED = "budget_exhausted"
    UNAVAILABLE = "unavailable"


class RequestStatus(StrEnum):
    """Where a queued lookup request stands."""

    PREPARING = "preparing"
    READY = "ready"
    HELD = "held_for_review"
    NOT_AVAILABLE = "not_available"
    FAILED = "failed"


_ACTIVE_JOB_STATUSES = frozenset({"todo", "doing"})
_IDTYPES: dict[str, IdType] = {"doi": "doi", "pmcid": "pmcid", "pmid": "pmid"}
_FAILED_JOB_STATUSES = frozenset({"failed", "cancelled", "aborted"})

MESSAGES = {
    "in_corpus": "This paper is in ResearchBridge.",
    "queued": (
        "This paper's licence allows ResearchBridge to show it. It is being prepared; "
        "this usually takes a minute or two."
    ),
    "candidates": "Several papers may match that title. Choose one to look it up.",
    "arxiv": ("Papers from arXiv are not added to ResearchBridge yet. You can read it on arXiv."),
    "not_in_pmc": (
        "This paper is not in PubMed Central's open-access collection, so ResearchBridge "
        "cannot show it. You can read it at the publisher."
    ),
    "not_permitted": (
        "This paper's licence does not allow ResearchBridge to show it. You can read it "
        "at the publisher."
    ),
    "held": "This paper's licence is being checked by a person before it can be shown.",
    "budget": (
        "ResearchBridge has prepared as many new papers as it can today. Please try again tomorrow."
    ),
    "unavailable": "A source needed to check this paper could not be reached. Please try again.",
}


def lookup(
    query: str,
    clients: MetadataClients,
    *,
    bucket_factory: Callable[[], PmcBucket] = get_bucket,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Look a paper up and, when eligible, queue it for ingestion.

    Args:
        query: What the reader typed.
        clients: Metadata clients (ID converter, OpenAlex).
        bucket_factory: Returns the PMC bucket client (injectable for tests).
        now: Current time.

    Returns:
        A JSON-ready dict with ``outcome``, ``message``, ``identifier`` and,
        depending on the outcome, ``paper``, ``request``, ``search`` and
        ``links``.

    Raises:
        rb_backend.identifiers.IdentifierError: If the query is unusable.
    """
    now = now or timezone.now()
    parsed = parse_identifier(query)
    base = {"identifier": {"kind": parsed.kind, "value": parsed.value}}

    # Titles list candidates; the reader chooses (no guessing which paper was meant).
    if parsed.kind == "title":
        search = run_search(SearchParams(query=parsed.value), clients, now=now)
        return {**base, **_result(LookupOutcome.CANDIDATES, "candidates"), "search": search}

    # Already in the corpus under the identifier typed.
    paper = _find_displayable(parsed)
    if paper is not None:
        return {**base, **_in_corpus(paper)}

    # arXiv is not ingested yet (Plan.md: after the MVP).
    if parsed.kind == "arxiv":
        arxiv_doi = f"10.48550/arxiv.{parsed.value}"
        return {
            **base,
            **_result(LookupOutcome.NOT_AVAILABLE, "arxiv"),
            "links": {
                "doi": doi_url(arxiv_doi),
                "arxiv": f"https://arxiv.org/abs/{parsed.value}",
                "scholar": scholar_search_url(title=None, doi=arxiv_doi),
            },
        }

    # Resolve to a PMC ID (the primary source) and look in the corpus again.
    try:
        ids = _resolve(parsed, clients, now=now)
    except UpstreamError:
        return {**base, **_result(LookupOutcome.UNAVAILABLE, "unavailable")}
    paper = _find_by_ids(ids)
    if paper is not None:
        return {**base, **_in_corpus(paper)}
    links = _links(ids)
    if ids.pmcid is None:
        return {**base, **_result(LookupOutcome.NOT_AVAILABLE, "not_in_pmc"), "links": links}
    return {**base, **_check_and_queue(parsed, ids, bucket_factory, links, now=now)}


def _check_and_queue(
    parsed: ParsedIdentifier,
    ids: IdRecord,
    bucket_factory: Callable[[], PmcBucket],
    links: dict[str, str | None],
    *,
    now: datetime,
) -> dict[str, Any]:
    """Decide eligibility of a PMC article not yet displayable, and queue it if eligible.

    Args:
        parsed: The identifier typed.
        ids: Its resolved identifiers (``pmcid`` set).
        bucket_factory: Returns the bucket client.
        links: Outbound links.
        now: Current time.

    Returns:
        The outcome fields (queued, not_available, budget_exhausted or unavailable).
    """
    pmcid = ids.pmcid or ""

    # Stored but not displayable: the gate has already spoken (or a person is checking).
    state = access.ingestion_state(pmcid)
    if state.stored and state.gate_status == GateStatus.REJECTED:
        return {**_result(LookupOutcome.NOT_AVAILABLE, "not_permitted"), "links": links}
    pending = _open_request(pmcid)
    if pending is not None:
        return {**_result(LookupOutcome.QUEUED, "queued"), "request": request_status(pending)}
    if state.stored:
        return {**_result(LookupOutcome.NOT_AVAILABLE, "held"), "links": links}

    # Eligibility at the primary source: the PMC licence code of the latest version.
    try:
        licence_code = _pmc_licence_code(bucket_factory(), pmcid)
    except (FetchError, PmcError):
        return _result(LookupOutcome.UNAVAILABLE, "unavailable")
    if licence_code is None:
        return {**_result(LookupOutcome.NOT_AVAILABLE, "not_in_pmc"), "links": links}
    decision = resolve_licence([LicenceEvidence(LicenceField.PMC_LICENSE_CODE, licence_code)])
    if decision.needs_review or not decision.permissions.can_display:
        return {
            **_result(LookupOutcome.NOT_AVAILABLE, "not_permitted"),
            "links": links,
            "licence_code": licence_code,
        }

    # Eligible: queue it, within the daily budget.
    if _requests_today(now) >= settings.RB_LOOKUP_DAILY_INGEST_LIMIT:
        return {**_result(LookupOutcome.BUDGET_EXHAUSTED, "budget"), "links": links}
    request = LookupRequest.objects.create(
        query=parsed.value,
        pmcid=pmcid,
        doi=ids.doi or "",
        licence_code=licence_code,
        job_id=queue_ingest(pmcid),
    )
    return {**_result(LookupOutcome.QUEUED, "queued"), "request": request_status(request)}


def request_status(request: LookupRequest) -> dict[str, Any]:
    """The status of a queued lookup request.

    Args:
        request: The request.

    Returns:
        ``{"id", "status", "message", "paper"}``; ``paper`` is set once the
        article is displayable.
    """
    state = access.ingestion_state(request.pmcid)
    job = job_status(request.job_id) if request.job_id is not None else None
    paper = (
        access.displayable_papers().filter(pmcid=request.pmcid).first()
        if state.displayable
        else None
    )

    # Ready beats everything; a running job beats a stored but undecided version.
    if paper is not None:
        status, message = RequestStatus.READY, MESSAGES["in_corpus"]
    elif job in _ACTIVE_JOB_STATUSES or (job is None and not state.stored):
        status, message = RequestStatus.PREPARING, MESSAGES["queued"]
    elif state.stored and state.gate_status == GateStatus.REJECTED:
        status, message = RequestStatus.NOT_AVAILABLE, MESSAGES["not_permitted"]
    elif state.stored:
        status, message = RequestStatus.HELD, MESSAGES["held"]
    elif job in _FAILED_JOB_STATUSES:
        status, message = (
            RequestStatus.FAILED,
            "Preparing this paper failed. Please try again later.",
        )
    else:
        status, message = RequestStatus.NOT_AVAILABLE, MESSAGES["not_in_pmc"]
    return {
        "id": str(request.id),
        "status": status,
        "message": message,
        "pmcid": request.pmcid,
        "created_at": request.created_at.isoformat(),
        "paper": _paper_ref(paper) if paper is not None else None,
        "links": {"doi": doi_url(request.doi or None)},
    }


def _open_request(pmcid: str) -> LookupRequest | None:
    """The latest request for an article whose job is still waiting or running.

    Args:
        pmcid: The PMC ID.

    Returns:
        The request, or None.
    """
    latest = LookupRequest.objects.filter(pmcid=pmcid).order_by("-created_at").first()
    if latest is None or latest.job_id is None:
        return None
    return latest if job_status(latest.job_id) in _ACTIVE_JOB_STATUSES else None


def _requests_today(now: datetime) -> int:
    """How many requests queued ingestion since midnight UTC.

    Args:
        now: Current time.

    Returns:
        The count.
    """
    midnight = datetime.combine(now.astimezone(UTC).date(), time.min, tzinfo=UTC)
    return LookupRequest.objects.filter(created_at__gte=midnight).count()


def _pmc_licence_code(bucket: PmcBucket, pmcid: str) -> str | None:
    """The ``license_code`` of an article's latest version in the PMC bucket.

    Args:
        bucket: The bucket client.
        pmcid: The PMC ID.

    Returns:
        The code (e.g. "CC BY", "TDM"), or None when the bucket does not list
        the article or gives no code.

    Raises:
        rbcore.http.FetchError: If the bucket cannot be reached.
        rb_backend.ingestion.pmc.PmcError: If its answer is malformed.
    """
    versions = bucket.list_versions(pmcid)
    if not versions:
        return None
    metadata, _ = bucket.metadata(versions[-1])
    return metadata.license_code


def _resolve(parsed: ParsedIdentifier, clients: MetadataClients, *, now: datetime) -> IdRecord:
    """Resolve an identifier to the article's DOI, PMC ID and PMID.

    Args:
        parsed: A DOI, PMC ID or PMID.
        clients: Metadata clients.
        now: Current time.

    Returns:
        The identifiers known (the typed one is always kept).

    Raises:
        rb_backend.metadata.errors.UpstreamError: If the ID converter fails
            with nothing cached.
    """
    typed = IdRecord(
        doi=parsed.value if parsed.kind == "doi" else None,
        pmcid=parsed.value if parsed.kind == "pmcid" else None,
        pmid=parsed.value if parsed.kind == "pmid" else None,
    )
    answer = convert_id(clients, parsed.value, _IDTYPES[parsed.kind], now=now)
    if answer.payload is None:
        return typed
    found = parse_record(answer.payload)
    return IdRecord(
        doi=normalise_doi(typed.doi or found.doi),
        pmcid=typed.pmcid or found.pmcid,
        pmid=typed.pmid or found.pmid,
    )


def _find_displayable(parsed: ParsedIdentifier) -> Paper | None:
    """A displayable corpus paper with the typed identifier.

    Args:
        parsed: The identifier.

    Returns:
        The paper, or None.
    """
    field = {"doi": "doi", "pmcid": "pmcid", "pmid": "pmid", "arxiv": "arxiv_id"}[parsed.kind]
    return access.displayable_papers().filter(**{field: parsed.value}).first()


def _find_by_ids(ids: IdRecord) -> Paper | None:
    """A displayable corpus paper with any of the given identifiers.

    Args:
        ids: The identifiers.

    Returns:
        The paper, or None.
    """
    conditions = Q()
    for field, value in (("doi", ids.doi), ("pmcid", ids.pmcid), ("pmid", ids.pmid)):
        if value:
            conditions |= Q(**{field: value})
    if not conditions:
        return None
    return access.displayable_papers().filter(conditions).first()


def _in_corpus(paper: Paper) -> dict[str, Any]:
    """The outcome fields for a corpus hit.

    Args:
        paper: The displayable paper.

    Returns:
        Outcome, message and the paper reference.
    """
    return {**_result(LookupOutcome.IN_CORPUS, "in_corpus"), "paper": _paper_ref(paper)}


def _paper_ref(paper: Paper) -> dict[str, Any]:
    """A short reference to a displayable paper.

    Args:
        paper: The paper.

    Returns:
        ``{"key", "title"}``.
    """
    version = access.displayable_version(paper)
    return {"key": paper_key(paper), "title": version.title if version else ""}


def _links(ids: IdRecord) -> dict[str, str | None]:
    """Outbound links for a paper that is not shown here.

    Args:
        ids: Its identifiers.

    Returns:
        DOI, PubMed and Google Scholar links (None where unknown).
    """
    return {
        "doi": doi_url(ids.doi),
        "pubmed": f"https://pubmed.ncbi.nlm.nih.gov/{ids.pmid}/" if ids.pmid else None,
        "scholar": scholar_search_url(title=None, doi=ids.doi),
    }


def _result(outcome: LookupOutcome, message_key: str) -> dict[str, Any]:
    """The outcome and its reader-facing message.

    Args:
        outcome: The outcome.
        message_key: Key into :data:`MESSAGES`.

    Returns:
        ``{"outcome", "message"}``.
    """
    return {"outcome": outcome, "message": MESSAGES[message_key]}
