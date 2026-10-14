"""Resolve licence reviews: the only way a human decision enters the gate.

A reviewer approves a review with a licence (a URI or code, normalised by
rbcore and required to be recognised) or rejects it, always with a written
justification. The version is then re-evaluated, which applies the
resolution for as long as the evidence it was given for stays the same, and
:data:`rb_backend.corpus.signals.review_resolved` is sent.
"""

from __future__ import annotations

from datetime import datetime

from django.contrib.auth.models import AbstractBaseUser
from django.db import transaction
from django.utils import timezone

from rb_backend.corpus.gate import evaluate_version
from rb_backend.corpus.models import GateStatus, LicenceReview, ReviewStatus
from rb_backend.corpus.signals import review_resolved
from rbcore.licences import LicenceFamily, normalise_licence


class ReviewError(ValueError):
    """Raised when a review cannot be resolved as requested."""


def resolve_review(
    review: LicenceReview,
    *,
    approve: bool,
    licence_value: str,
    note: str,
    reviewer: AbstractBaseUser | None,
    now: datetime | None = None,
) -> GateStatus:
    """Approve or reject an open review and re-evaluate its version.

    Args:
        review: The review; it must be open.
        approve: True to approve with ``licence_value``, False to reject.
        licence_value: A licence URI or code (approvals only), e.g.
            ``https://creativecommons.org/licenses/by/4.0/`` or ``CC BY``.
        note: The reviewer's justification (required).
        reviewer: The user resolving it.
        now: Resolution time (default: now).

    Returns:
        The version's gate status after re-evaluation.

    Raises:
        ReviewError: If the review is not open, the note is blank, or an
            approval names no recognised licence.
    """
    if review.status != ReviewStatus.OPEN:
        raise ReviewError(f"licence review #{review.pk} is {review.status}, not open")
    if not note.strip():
        raise ReviewError("a justification note is required")

    with transaction.atomic():
        # Record the human decision exactly as made.
        review.reviewer_note = note.strip()
        review.reviewer = reviewer  # type: ignore[assignment]
        review.resolved_at = now or timezone.now()
        if approve:
            licence = normalise_licence(licence_value)
            if licence.family is LicenceFamily.UNKNOWN:
                raise ReviewError(f"{licence_value!r} is not a recognised licence URI or code")
            review.status = ReviewStatus.APPROVED
            review.resolved_licence = licence_value.strip()
            review.resolved_family = licence.family.value
            review.resolved_version = licence.version or ""
            review.resolved_jurisdiction = licence.jurisdiction or ""
        else:
            review.status = ReviewStatus.REJECTED
        review.save()
        # Re-run the gate so the resolution takes effect everywhere.
        status = evaluate_version(review.version, now=review.resolved_at)

        # Let the content side react (fetch removed text again, or drop a
        # rejected version's cached copy) without the gate depending on it.
        review_resolved.send(
            sender=LicenceReview, review=review, version=review.version, status=status
        )
        return status
