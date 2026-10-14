"""Cached access to every metadata service, with the clients bundled for injection.

Views and services call these functions with a :class:`MetadataClients`
bundle; :func:`default_clients` builds the real one (tests pass clients on
``httpx.MockTransport`` fetchers that serve recorded responses). How long an
answer stays fresh comes from settings: ``RB_METADATA_TTL_HOURS`` for single
records and ``RB_SEARCH_TTL_HOURS`` for searches.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from django.conf import settings

from rb_backend.metadata.cache import CacheResult, cached_json
from rb_backend.metadata.crossref import CrossrefClient
from rb_backend.metadata.fetch import metadata_fetcher
from rb_backend.metadata.icite import ICiteClient
from rb_backend.metadata.idconv import IdConverter, IdType
from rb_backend.metadata.models import CacheSource
from rb_backend.metadata.openalex import OpenAlexClient, SearchRequest, WorkIdKind
from rbcore.config import Settings


@dataclass(frozen=True, slots=True)
class MetadataClients:
    """The metadata clients a request uses.

    Attributes:
        openalex: OpenAlex.
        icite: NIH iCite.
        crossref: Crossref.
        idconv: The PMC ID converter.
    """

    openalex: OpenAlexClient
    icite: ICiteClient
    crossref: CrossrefClient
    idconv: IdConverter


def default_clients() -> MetadataClients:
    """Build the clients on the shared polite fetcher.

    Returns:
        The clients; OpenAlex gets ``OPENALEX_API_KEY`` when it is set.
    """
    fetcher = metadata_fetcher()
    return MetadataClients(
        openalex=OpenAlexClient(fetcher, api_key=Settings.from_env().openalex_api_key),
        icite=ICiteClient(fetcher),
        crossref=CrossrefClient(fetcher),
        idconv=IdConverter(fetcher),
    )


def _record_ttl() -> timedelta:
    """How long a single-record answer stays fresh.

    Returns:
        ``RB_METADATA_TTL_HOURS`` as a timedelta.
    """
    return timedelta(hours=settings.RB_METADATA_TTL_HOURS)


def openalex_work(
    clients: MetadataClients, kind: WorkIdKind, value: str, *, now: datetime | None = None
) -> CacheResult:
    """One OpenAlex work by DOI or PMID, cached.

    Args:
        clients: The clients.
        kind: "doi" or "pmid".
        value: The identifier.
        now: Current time.

    Returns:
        The cached answer (payload None when OpenAlex has no such work).
    """
    return cached_json(
        CacheSource.OPENALEX_WORK,
        f"{kind}:{value}",
        lambda: clients.openalex.work(kind, value),
        ttl=_record_ttl(),
        now=now,
    )


def openalex_search(
    clients: MetadataClients, request: SearchRequest, *, now: datetime | None = None
) -> CacheResult:
    """An OpenAlex search, cached for ``RB_SEARCH_TTL_HOURS``.

    Args:
        clients: The clients.
        request: The search.
        now: Current time.

    Returns:
        The cached answer: ``{"count", "results"}``.
    """
    return cached_json(
        CacheSource.OPENALEX_SEARCH,
        request.canonical(),
        lambda: clients.openalex.search(request),
        ttl=timedelta(hours=settings.RB_SEARCH_TTL_HOURS),
        now=now,
    )


def icite_pub(clients: MetadataClients, pmid: str, *, now: datetime | None = None) -> CacheResult:
    """One iCite record, cached.

    Args:
        clients: The clients.
        pmid: The PubMed ID.
        now: Current time.

    Returns:
        The cached answer.
    """
    return cached_json(
        CacheSource.ICITE, pmid, lambda: clients.icite.pub(pmid), ttl=_record_ttl(), now=now
    )


def crossref_work(
    clients: MetadataClients, doi: str, *, now: datetime | None = None
) -> CacheResult:
    """One Crossref record (notices only), cached.

    Args:
        clients: The clients.
        doi: A bare DOI.
        now: Current time.

    Returns:
        The cached answer.
    """
    return cached_json(
        CacheSource.CROSSREF, doi, lambda: clients.crossref.work(doi), ttl=_record_ttl(), now=now
    )


def convert_id(
    clients: MetadataClients, value: str, idtype: IdType, *, now: datetime | None = None
) -> CacheResult:
    """A PMC ID converter lookup, cached.

    Args:
        clients: The clients.
        value: The identifier.
        idtype: Its type.
        now: Current time.

    Returns:
        The cached answer.
    """
    return cached_json(
        CacheSource.IDCONV,
        f"{idtype}:{value}",
        lambda: clients.idconv.lookup(value, idtype),
        ttl=_record_ttl(),
        now=now,
    )
