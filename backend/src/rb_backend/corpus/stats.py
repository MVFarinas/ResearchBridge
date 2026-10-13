"""Corpus statistics: counts by licence family and gate status.

Used by ``manage.py corpus_stats`` and the phase notes. Counts of what *may*
be shown use the gated querysets, so they are exactly what readers could see.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from django.db.models import Count

from rb_backend.corpus.models import (
    Figure,
    GateStatus,
    LicenceReview,
    Paper,
    PaperVersion,
    Paragraph,
    ReviewStatus,
)


def _counts(rows: Iterable[Mapping[str, Any]], key: str) -> dict[str, int]:
    """Turn ``values(key).annotate(n=Count(...))`` rows into a sorted dict.

    Args:
        rows: Rows with ``key`` and ``n``.
        key: The grouping field.

    Returns:
        Counts by value, sorted by value.
    """
    return {str(row[key]): row["n"] for row in sorted(rows, key=lambda r: str(r[key]))}


def corpus_stats() -> dict[str, Any]:
    """Compute corpus counts.

    Returns:
        A JSON-serialisable dictionary: totals, current versions by gate
        status, licence families of approved and rejected versions, open
        reviews by scope, part decisions, and what the gated querysets return.
    """
    current = PaperVersion.objects.filter(is_current=True)
    by_status_family = current.values("gate_status", "licence_family").annotate(n=Count("pk"))

    def families(status: GateStatus) -> dict[str, int]:
        """Licence family counts of current versions with one gate status."""
        return _counts(
            [r for r in by_status_family if r["gate_status"] == status], "licence_family"
        )

    return {
        "totals": {
            "papers": Paper.objects.count(),
            "current_versions": current.count(),
            "author_manuscripts": current.filter(is_manuscript=True).count(),
            "retracted_papers": Paper.objects.filter(is_retracted=True).count(),
        },
        "gate_status": _counts(
            current.values("gate_status").annotate(n=Count("pk")), "gate_status"
        ),
        "approved_by_licence": families(GateStatus.APPROVED),
        "rejected_by_licence": families(GateStatus.REJECTED),
        "review_by_proposed_licence": families(GateStatus.REVIEW),
        "open_reviews_by_scope": _counts(
            LicenceReview.objects.filter(status=ReviewStatus.OPEN)
            .values("scope")
            .annotate(n=Count("pk")),
            "scope",
        ),
        "figures_by_gate_status": _counts(
            Figure.objects.filter(version__is_current=True)
            .values("gate_status")
            .annotate(n=Count("pk")),
            "gate_status",
        ),
        "paragraphs_by_gate_status": _counts(
            Paragraph.objects.filter(version__is_current=True)
            .values("gate_status")
            .annotate(n=Count("pk")),
            "gate_status",
        ),
        "gated_querysets": {
            "displayable_papers": Paper.objects.displayable().count(),
            "rewriteable_papers": Paper.objects.rewriteable().count(),
            "displayable_figures": Figure.objects.displayable().count(),
            "displayable_paragraphs": Paragraph.objects.displayable().count(),
        },
    }
