"""On-demand lookup requests: a paper queued for ingestion because a reader asked."""

from __future__ import annotations

import uuid

from django.db import models


class LookupRequest(models.Model):
    """A reader's request that queued a licence-eligible PMC article for ingestion.

    Only requests that queued work are stored (they count against the daily
    budget and have a status page). Nothing about the reader is stored.

    Attributes:
        id: Public UUID (the status URL uses it).
        query: What the reader typed, normalised.
        pmcid: The PMC article queued.
        doi: Its DOI, if known.
        licence_code: The PMC ``license_code`` seen at the eligibility check.
        job_id: The worker job ingesting it, if known.
        created_at: When the request was made.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    query = models.CharField(max_length=500)
    pmcid = models.CharField(max_length=32, db_index=True)
    doi = models.CharField(max_length=255, blank=True)
    licence_code = models.CharField(max_length=64)
    job_id = models.BigIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    def __str__(self) -> str:
        """Return ``<pmcid> (<created_at>)``."""
        return f"{self.pmcid} ({self.created_at:%Y-%m-%d %H:%M})"
