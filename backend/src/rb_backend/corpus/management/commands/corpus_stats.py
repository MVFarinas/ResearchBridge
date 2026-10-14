"""``manage.py corpus_stats``: counts by licence and gate status (``--json`` for JSON)."""

from __future__ import annotations

import json
from argparse import ArgumentParser
from typing import Any

from django.core.management.base import BaseCommand

from rb_backend.corpus.stats import corpus_stats


class Command(BaseCommand):
    """Print corpus counts by licence family and gate status."""

    help = "Print corpus counts by licence family and gate status."

    def add_arguments(self, parser: ArgumentParser) -> None:
        """Declare the command's options.

        Args:
            parser: The argument parser.
        """
        parser.add_argument("--json", action="store_true", help="print JSON")

    def handle(self, *args: Any, **options: Any) -> None:
        """Compute and print the statistics.

        Args:
            *args: Unused positional arguments.
            **options: Parsed options.
        """
        stats = corpus_stats()
        if options["json"]:
            self.stdout.write(json.dumps(stats, indent=2, sort_keys=True))
            return
        for section, values in stats.items():
            self.stdout.write(f"{section}: {values}")
