"""``manage.py ingest_pmc``: discover PMC articles and ingest them through the worker.

Examples::

    # 200 recent CC BY articles about hypertension, queued for the worker
    manage.py ingest_pmc --limit 200 --query "hypertension AND 2024[pdat]" --licence cc-by

    # PLOS articles are in PMC too; restrict by journal
    manage.py ingest_pmc --limit 50 --query '"PLoS Med"[ta]'

    # specific articles, inline (no worker), e.g. for debugging
    manage.py ingest_pmc --pmcid PMC10718527 PMC7853715 --sync

Discovery uses NCBI ESearch restricted to articles in the PMC Cloud Service
bucket (``open_access[Filter] OR author_manuscript[Filter]``, so author
manuscripts are included and the gate shows how they are refused). Without
``--sync`` each article becomes one ``rb.ingest_pmc_article`` job; run
``manage.py procrastinate worker`` to process them.
"""

from __future__ import annotations

from argparse import ArgumentParser
from collections import Counter
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from rb_backend.corpus.models import Paper
from rb_backend.ingestion.eutils import LICENCE_FILTERS, build_term, search_pmc
from rb_backend.ingestion.pipeline import ingest_pmc_article
from rb_backend.ingestion.pmc import PmcError, normalise_pmcid
from rb_backend.ingestion.runtime import get_bucket, get_fetcher, ncbi_api_key
from rb_backend.ingestion.tasks import defer_many
from rbcore.http import FetchError


class Command(BaseCommand):
    """Discover and ingest PMC articles."""

    help = "Discover PMC articles (ESearch or explicit IDs) and ingest them via the worker."

    def add_arguments(self, parser: ArgumentParser) -> None:
        """Declare the command's options.

        Args:
            parser: The argument parser.
        """
        parser.add_argument("--limit", type=int, default=None, help="maximum articles to discover")
        parser.add_argument(
            "--query", default="", help='Entrez query, e.g. "asthma AND 2024[pdat]"'
        )
        parser.add_argument(
            "--licence",
            choices=sorted(LICENCE_FILTERS),
            default="any",
            help="PMC licence filter applied in the search (the gate still decides)",
        )
        parser.add_argument("--pmcid", nargs="+", default=[], help="ingest these PMC IDs")
        parser.add_argument(
            "--skip-existing", action="store_true", help="skip articles already stored"
        )
        parser.add_argument("--sync", action="store_true", help="ingest inline, without the worker")

    def handle(self, *args: Any, **options: Any) -> None:
        """Discover the articles, then queue or ingest them.

        Args:
            *args: Unused positional arguments.
            **options: Parsed options.

        Raises:
            CommandError: For invalid options or a failed search.
        """
        pmcids = self._discover(options)
        if options["skip_existing"]:
            stored = set(Paper.objects.filter(pmcid__in=pmcids).values_list("pmcid", flat=True))
            pmcids = [pmcid for pmcid in pmcids if pmcid not in stored]
        self.stdout.write(f"{len(pmcids)} article(s) to ingest")

        if options["sync"]:
            self._ingest_inline(pmcids)
            return
        queued, already = defer_many(pmcids)
        self.stdout.write(
            f"queued {queued} job(s); {already} already queued. "
            "Run `manage.py procrastinate worker` to process them."
        )

    def _discover(self, options: dict[str, Any]) -> list[str]:
        """Turn the options into a list of PMC IDs.

        Args:
            options: Parsed options.

        Returns:
            PMC IDs, explicit ones first, without duplicates.

        Raises:
            CommandError: If neither IDs nor a positive limit is given, an ID
                is malformed, or the search fails.
        """
        try:
            explicit = [normalise_pmcid(value) for value in options["pmcid"]]
        except PmcError as exc:
            raise CommandError(str(exc)) from exc
        limit = options["limit"]
        if not explicit and (limit is None or limit <= 0):
            raise CommandError("give --pmcid or a positive --limit")
        if limit is None or limit <= 0:
            return list(dict.fromkeys(explicit))

        # Search only for what the explicit IDs do not already cover.
        wanted = max(limit - len(explicit), 0)
        found: list[str] = []
        if wanted:
            term = build_term(options["query"], licence=options["licence"])
            self.stdout.write(f"searching PMC: {term}")
            try:
                found = search_pmc(get_fetcher(), term, limit=wanted, api_key=ncbi_api_key())
            except (FetchError, RuntimeError) as exc:
                raise CommandError(f"search failed: {exc}") from exc
        return list(dict.fromkeys([*explicit, *found]))

    def _ingest_inline(self, pmcids: list[str]) -> None:
        """Ingest articles in this process and print a summary.

        Args:
            pmcids: PMC IDs.
        """
        bucket = get_bucket()
        outcomes: Counter[str] = Counter()
        statuses: Counter[str] = Counter()
        for pmcid in pmcids:
            # One failure must not stop the batch; it is reported and counted.
            try:
                report = ingest_pmc_article(pmcid, bucket=bucket)
            except (FetchError, PmcError) as exc:
                self.stderr.write(f"{pmcid}: failed: {exc}")
                outcomes["failed"] += 1
                continue
            outcomes[report.outcome.value] += 1
            if report.gate_status is not None:
                statuses[report.gate_status.value] += 1
            self.stdout.write(
                f"{pmcid}: {report.outcome.value}, gate {report.gate_status or '-'}, "
                f"licence {report.licence_family or '-'}"
            )
        self.stdout.write(f"outcomes: {dict(sorted(outcomes.items()))}")
        self.stdout.write(f"gate: {dict(sorted(statuses.items()))}")
