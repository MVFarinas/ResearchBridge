"""Background tasks run by the Procrastinate worker (``manage.py procrastinate worker``).

* ``rb.ingest_pmc_article``: ingest or re-check one PMC article. Deferred with
  the PMC ID as queueing lock, so the same article is never queued twice.
* ``rb.recheck_stale_pmc``: periodic (daily); queues a re-check of the stored
  articles not checked for ``RB_RECHECK_MAX_AGE_DAYS`` days, at most
  ``RB_RECHECK_BATCH_SIZE`` per run. This is how the corpus stays current.

Both run on the ``ingestion`` queue. Synchronous tasks run in worker threads,
so each one closes stale database connections before and after it runs.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from datetime import timedelta
from functools import wraps

from django.conf import settings
from django.db import connections
from django.db.models import F, Q
from django.utils import timezone
from procrastinate import RetryStrategy
from procrastinate.contrib.django import app
from procrastinate.exceptions import AlreadyEnqueued

from rb_backend.corpus.models import PaperVersion, Source
from rb_backend.ingestion.pipeline import ingest_pmc_article
from rb_backend.ingestion.runtime import INGEST_LOCK, get_bucket

logger = logging.getLogger(__name__)

INGESTION_QUEUE = "ingestion"


def close_stale_connections() -> None:
    """Close unusable or expired database connections, as Django does per request.

    A connection inside an atomic block is never closed (a caller, such as a
    test or a management command, may be running the task in a transaction).
    """
    for conn in connections.all(initialized_only=True):
        if not conn.in_atomic_block:
            conn.close_if_unusable_or_obsolete()


def _with_fresh_connections[**P, R](func: Callable[P, R]) -> Callable[P, R]:
    """Close stale database connections around a task.

    Args:
        func: The task function.

    Returns:
        The wrapped function.
    """

    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        """Run the task between two connection clean-ups."""
        close_stale_connections()
        try:
            return func(*args, **kwargs)
        finally:
            close_stale_connections()

    return wrapper


@app.task(
    name="rb.ingest_pmc_article",
    queue=INGESTION_QUEUE,
    retry=RetryStrategy(max_attempts=3, linear_wait=60),
)
@_with_fresh_connections
def ingest_pmc_article_task(pmcid: str) -> None:
    """Ingest or re-check one PMC article.

    Args:
        pmcid: The PMC ID.
    """
    with INGEST_LOCK:
        report = ingest_pmc_article(pmcid, bucket=get_bucket())
    logger.info("ingested %s: %s (%s)", report.pmcid, report.outcome, report.gate_status)


def defer_ingest(pmcid: str) -> bool:
    """Queue one article for the worker unless it is already queued.

    Args:
        pmcid: The PMC ID (normalised by the caller).

    Returns:
        True if queued, False if a job for it was already waiting.
    """
    try:
        ingest_pmc_article_task.configure(queueing_lock=pmcid).defer(pmcid=pmcid)
    except AlreadyEnqueued:
        return False
    return True


def defer_many(pmcids: Iterable[str]) -> tuple[int, int]:
    """Queue several articles.

    Args:
        pmcids: PMC IDs.

    Returns:
        ``(queued, already_queued)``.
    """
    queued = skipped = 0
    for pmcid in pmcids:
        if defer_ingest(pmcid):
            queued += 1
        else:
            skipped += 1
    return queued, skipped


def stale_pmcids(*, max_age: timedelta, limit: int) -> list[str]:
    """PMC IDs of current versions not checked within ``max_age``, oldest first.

    Versions never checked come before all others (Postgres would otherwise
    sort NULLs last and starve them once the batch size is reached).

    Args:
        max_age: How old a check may be.
        limit: Maximum number of IDs.

    Returns:
        PMC IDs.
    """
    cutoff = timezone.now() - max_age
    versions = (
        PaperVersion.objects.filter(source=Source.PMC, is_current=True)
        .filter(Q(last_checked_at__lt=cutoff) | Q(last_checked_at__isnull=True))
        .order_by(F("last_checked_at").asc(nulls_first=True), "pk")
        .values_list("paper__pmcid", flat=True)[:limit]
    )
    return [pmcid for pmcid in versions if pmcid]


@app.periodic(cron="23 4 * * *", periodic_id="recheck-stale-pmc")
@app.task(name="rb.recheck_stale_pmc", queue=INGESTION_QUEUE, queueing_lock="recheck-stale-pmc")
@_with_fresh_connections
def recheck_stale_pmc_task(timestamp: int) -> None:
    """Queue re-checks of stale articles (runs daily at 04:23 UTC).

    Args:
        timestamp: The scheduled time, supplied by Procrastinate.
    """
    pmcids = stale_pmcids(
        max_age=timedelta(days=settings.RB_RECHECK_MAX_AGE_DAYS),
        limit=settings.RB_RECHECK_BATCH_SIZE,
    )
    queued, skipped = defer_many(pmcids)
    logger.info("periodic re-check at %s: queued %d, already queued %d", timestamp, queued, skipped)
