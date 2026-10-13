"""Signals the corpus app sends so other apps can act on its decisions.

The corpus app owns the licence gate and must not depend on how content is
fetched; the ingestion app listens here instead (see
:mod:`rb_backend.ingestion.receivers`).
"""

from __future__ import annotations

from django.dispatch import Signal

# Sent by :func:`rb_backend.corpus.reviews.resolve_review` once the version has
# been re-evaluated, inside the same transaction. Keyword arguments:
# ``review`` (the resolved LicenceReview), ``version`` (its PaperVersion) and
# ``status`` (the version's GateStatus afterwards).
review_resolved = Signal()
