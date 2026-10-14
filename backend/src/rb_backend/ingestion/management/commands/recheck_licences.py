"""``manage.py recheck_licences``: re-check stored papers' licences.

Two modes:

* default: re-fetch each stored PMC article's listing and metadata (the
  licence code, the retraction flag, new versions, changed XML) through the
  worker, which also recomputes the gate. Use ``--sync`` to do it inline.
* ``--offline``: recompute every stored decision from the stored records
  only, with today's date (no network). Useful after an embargo date passes,
  after a change to the gate code, or to verify the stored decisions.

Examples::

    manage.py recheck_licences --offline
    manage.py recheck_licences --older-than-days 7 --limit 500
    manage.py recheck_licences --pmcid PMC10718527 --sync
"""

from __future__ import annotations

from argparse import ArgumentParser
from collections import Counter
from datetime import timedelta
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from rb_backend.corpus.gate import evaluate_version
from rb_backend.corpus.models import PaperVersion, Source
from rb_backend.ingestion.pipeline import ingest_pmc_article
from rb_backend.ingestion.pmc import PmcError, normalise_pmcid
from rb_backend.ingestion.runtime import get_bucket
from rb_backend.ingestion.tasks import defer_many, stale_pmcids
from rbcore.http import FetchError


class Command(BaseCommand):
    """Re-check the licences of stored papers."""

    help = "Re-check stored papers' licences at the source (or offline from stored records)."

    def add_arguments(self, parser: ArgumentParser) -> None:
        """Declare the command's options.

        Args:
            parser: The argument parser.
        """
        parser.add_argument(
            "--offline", action="store_true", help="recompute from stored records, no network"
        )
        parser.add_argument("--pmcid", nargs="+", default=[], help="only these PMC IDs")
        parser.add_argument(
            "--older-than-days",
            type=int,
            default=0,
            help="only articles not checked for this many days (default: all)",
        )
        parser.add_argument("--limit", type=int, default=100_000, help="maximum articles")
        parser.add_argument(
            "--sync", action="store_true", help="re-check inline, without the worker"
        )

    def handle(self, *args: Any, **options: Any) -> None:
        """Run the re-check.

        Args:
            *args: Unused positional arguments.
            **options: Parsed options.

        Raises:
            CommandError: If a PMC ID is malformed.
        """
        try:
            pmcids = [normalise_pmcid(value) for value in options["pmcid"]]
        except PmcError as exc:
            raise CommandError(str(exc)) from exc

        if options["offline"]:
            self._recompute(pmcids, options["limit"])
            return

        targets = pmcids or stale_pmcids(
            max_age=timedelta(days=max(options["older_than_days"], 0)), limit=options["limit"]
        )
        if options["sync"]:
            self._recheck_inline(targets)
            return
        queued, already = defer_many(targets)
        self.stdout.write(f"queued {queued} re-check(s); {already} already queued")

    def _recompute(self, pmcids: list[str], limit: int) -> None:
        """Recompute stored decisions from stored records.

        Args:
            pmcids: Restrict to these PMC IDs (empty: all).
            limit: Maximum versions.
        """
        versions = PaperVersion.objects.filter(source=Source.PMC, is_current=True)
        if pmcids:
            versions = versions.filter(paper__pmcid__in=pmcids)
        changed = 0
        statuses: Counter[str] = Counter()
        for version in versions.order_by("pk")[:limit]:
            before = version.gate_status
            after = evaluate_version(version)
            statuses[after.value] += 1
            if after != before:
                changed += 1
                self.stdout.write(f"{version.source_version_id}: {before} -> {after}")
        self.stdout.write(f"recomputed: {dict(sorted(statuses.items()))}; {changed} changed")

    def _recheck_inline(self, pmcids: list[str]) -> None:
        """Re-ingest articles in this process.

        Args:
            pmcids: PMC IDs.
        """
        bucket = get_bucket()
        outcomes: Counter[str] = Counter()
        for pmcid in pmcids:
            # Keep going on failure; report and count it.
            try:
                report = ingest_pmc_article(pmcid, bucket=bucket)
            except (FetchError, PmcError) as exc:
                self.stderr.write(f"{pmcid}: failed: {exc}")
                outcomes["failed"] += 1
                continue
            outcomes[report.outcome.value] += 1
        self.stdout.write(f"re-checked: {dict(sorted(outcomes.items()))}")
