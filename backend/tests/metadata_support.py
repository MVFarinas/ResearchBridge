"""Test support for the metadata services: recorded responses behind a mock transport.

:class:`RecordedMetadata` answers the exact URLs listed in
``tests/fixtures/metadata/manifest.json`` with the recorded files, any other
URL with 404, and lets a test override a URL (or a whole host) with a
synthetic status or body. Every request is logged, so tests can assert what
was (and was not) fetched.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from rb_backend.metadata.crossref import CrossrefClient
from rb_backend.metadata.icite import ICiteClient
from rb_backend.metadata.idconv import IdConverter
from rb_backend.metadata.openalex import OpenAlexClient
from rb_backend.metadata.services import MetadataClients
from rbcore.http import PoliteFetcher, RateLimiter

METADATA_FIXTURES = Path(__file__).parent / "fixtures" / "metadata"
MANIFEST: dict[str, Any] = json.loads((METADATA_FIXTURES / "manifest.json").read_text())

PLOS_DOI = "10.1371/journal.pmed.1004542"
PLOS_PMID = "40173335"
PLOS_PMCID = "PMC11964404"
LANCET_DOI = "10.1016/s0140-6736(97)11096-0"
KARGER_DOI = "10.1159/000494475"


def recorded_body(name: str) -> bytes:
    """The bytes of one recorded fixture file.

    Args:
        name: File name in ``tests/fixtures/metadata``.

    Returns:
        Its content.
    """
    return (METADATA_FIXTURES / name).read_bytes()


@dataclass
class RecordedMetadata:
    """A fake metadata host serving recorded responses.

    Attributes:
        url_overrides: Synthetic responses by exact URL: ``(status, body)``.
        host_overrides: Synthetic responses for every URL of a host.
        requests: Every URL requested, in order.
    """

    url_overrides: dict[str, tuple[int, bytes]] = field(default_factory=dict)
    host_overrides: dict[str, tuple[int, bytes]] = field(default_factory=dict)
    requests: list[str] = field(default_factory=list)

    def handler(self, request: httpx.Request) -> httpx.Response:
        """Answer one request.

        Args:
            request: The request.

        Returns:
            An override, the recorded file for the URL, or 404.
        """
        url = str(request.url)
        self.requests.append(url)
        if url in self.url_overrides:
            status, body = self.url_overrides[url]
            return httpx.Response(status, content=body)
        if request.url.host in self.host_overrides:
            status, body = self.host_overrides[request.url.host]
            return httpx.Response(status, content=body)
        for entry in MANIFEST["fixtures"]:
            if httpx.URL(entry["source_url"]) == request.url:
                return httpx.Response(200, content=recorded_body(entry["file"]))
        return httpx.Response(404, content=b'{"error": "not found (synthetic test response)"}')


def make_clients(recorded: RecordedMetadata, *, openalex_key: str | None = None) -> MetadataClients:
    """Metadata clients on the recorded host, with no rate-limit delays.

    Args:
        recorded: The fake host.
        openalex_key: An OpenAlex key to send (synthetic), if any.

    Returns:
        The clients.
    """
    fetcher = PoliteFetcher(
        cache_dir=None,
        transport=httpx.MockTransport(recorded.handler),
        rate_limiter=RateLimiter({}, default_interval=0.0),
        sleep=lambda _: None,
        max_retries=0,
    )
    return MetadataClients(
        openalex=OpenAlexClient(fetcher, api_key=openalex_key),
        icite=ICiteClient(fetcher),
        crossref=CrossrefClient(fetcher),
        idconv=IdConverter(fetcher),
    )
