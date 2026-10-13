"""Ingestion's reactions to licence review resolutions.

A reviewer's decision can change what content a version may keep:

* An approval of a version whose text was removed after an earlier rejection
  means the text is needed again. Without help it would stay pending until the
  periodic re-check (up to ``RB_RECHECK_MAX_AGE_DAYS`` later), so the article
  is queued for the worker straight away.
* A rejection removes the version's text from the database (in the gate); the
  XML's copy in the local download cache is deleted here as well.

Both run only after the resolving transaction commits, so a rolled-back
resolution neither queues work nor deletes anything.
"""

from __future__ import annotations

import logging
from typing import Any

from django.db import transaction

from rb_backend.corpus.models import ContentState, GateStatus, LicenceReview, PaperVersion, Source
from rb_backend.ingestion.runtime import get_bucket
from rb_backend.ingestion.tasks import defer_ingest

logger = logging.getLogger(__name__)


def refresh_content_after_review(
    sender: type[LicenceReview],
    *,
    version: PaperVersion,
    status: GateStatus,
    **kwargs: Any,
) -> None:
    """Queue a removed version's text, or forget a rejected version's XML.

    Connected to :data:`rb_backend.corpus.signals.review_resolved` by
    :class:`rb_backend.ingestion.apps.IngestionConfig`.

    Args:
        sender: The LicenceReview model.
        version: The version whose review was resolved.
        status: Its gate status after re-evaluation.
        **kwargs: Other signal arguments (``review``, ``signal``), unused.
    """
    # Only PMC content is fetched (and cached) by this app.
    if version.source != Source.PMC:
        return

    # Rejected: nothing of its text may stay, the download cache included.
    if status == GateStatus.REJECTED:
        if version.content_url:
            url = version.content_url
            transaction.on_commit(lambda: _forget_xml(url))
        return

    # No longer rejected but its text was removed: fetch it now, not at the next re-check.
    pmcid = version.paper.pmcid
    if version.content_state == ContentState.REMOVED and version.is_current and pmcid:
        transaction.on_commit(lambda: _queue_ingest(pmcid))


def _forget_xml(url: str) -> None:
    """Delete a cached XML file.

    Args:
        url: The XML's URL.
    """
    if get_bucket().forget_xml(url):
        logger.info("deleted the cached XML of a rejected version: %s", url)


def _queue_ingest(pmcid: str) -> None:
    """Queue an article so the worker fetches its text again.

    Args:
        pmcid: The PMC ID.
    """
    queued = defer_ingest(pmcid)
    logger.info("%s approved after its text was removed; queued: %s", pmcid, queued)
