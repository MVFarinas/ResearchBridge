"""``manage.py rebuild_search_index``: rebuild the full-text search documents.

The gate rebuilds a version's document whenever it runs, so this is needed
only for versions stored before the index existed, or after changing how
documents are built.
"""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand

from rb_backend.corpus.models import PaperVersion
from rb_backend.corpus.search_index import rebuild_all


class Command(BaseCommand):
    """Rebuild the search document of every current version."""

    help = "Rebuild the full-text search document of every current paper version."

    def handle(self, *args: Any, **options: Any) -> None:
        """Rebuild the documents and report how many.

        Args:
            *args: Unused positional arguments.
            **options: Parsed options.
        """
        # Every current version gets a document; the query applies the gate.
        versions = PaperVersion.objects.filter(is_current=True).order_by("pk").iterator()
        count = rebuild_all(versions)
        self.stdout.write(f"rebuilt {count} search documents")
