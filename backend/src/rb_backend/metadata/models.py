"""The cache of metadata responses, with the time each was fetched."""

from __future__ import annotations

from django.db import models


class CacheSource(models.TextChoices):
    """Which request a cached response answers."""

    OPENALEX_WORK = "openalex-work", "OpenAlex work"
    OPENALEX_SEARCH = "openalex-search", "OpenAlex search"
    ICITE = "icite", "NIH iCite"
    CROSSREF = "crossref", "Crossref work"
    IDCONV = "idconv", "PMC ID converter"


class CachedResponse(models.Model):
    """One cached answer from a metadata service.

    Payloads are trimmed to the fields ResearchBridge reads, and never contain
    API keys. A payload of null records that the service had no such record
    (a cacheable "not found").

    Attributes:
        source: The kind of request.
        key: SHA-256 of the canonical request.
        request: The canonical request (no secrets), for debugging.
        payload: The trimmed JSON answer, or null for "not found".
        fetched_at: When the service answered; shown as "as of".
    """

    source = models.CharField(max_length=32, choices=CacheSource.choices)
    key = models.CharField(max_length=64)
    request = models.TextField()
    payload = models.JSONField(null=True, blank=True)
    fetched_at = models.DateTimeField()

    class Meta:
        """One row per request."""

        constraints = [
            models.UniqueConstraint(fields=["source", "key"], name="cachedresponse_unique_key"),
        ]

    def __str__(self) -> str:
        """Return ``<source>: <request>``."""
        return f"{self.source}: {self.request[:80]}"
