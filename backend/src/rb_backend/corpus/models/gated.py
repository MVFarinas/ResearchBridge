"""The persisted licence decision shared by versions, paragraphs and figures.

Every gated row stores the *effective* permissions: what ResearchBridge may do
right now. They are only ever true when the gate status is ``approved``, and
the database enforces the decisions.md §1.1 table independently of the Python
code through check constraints, so a bug or a raw ``UPDATE`` cannot make a
CC BY-ND paragraph rewritable or a paper under review displayable.
"""

from __future__ import annotations

from datetime import datetime

from django.db import models
from django.db.models import Q

from rbcore.licences import Licence, LicenceFamily, LicenceField, Permissions

# Families that may be displayed at all (§1.1: open licences only).
OPEN_FAMILY_VALUES: tuple[str, ...] = tuple(
    family.value for family in LicenceFamily if Licence(family).is_open
)
# Open families that forbid derivatives (display only).
NO_DERIVATIVE_FAMILY_VALUES: tuple[str, ...] = tuple(
    family.value for family in LicenceFamily if Licence(family).no_derivatives
)

LICENCE_FAMILY_CHOICES: list[tuple[str, str]] = [
    (family.value, Licence(family).label) for family in LicenceFamily
]
LICENCE_FIELD_CHOICES: list[tuple[str, str]] = [
    (field.value, field.value) for field in LicenceField
]


class GateStatus(models.TextChoices):
    """Where a gated row stands in the licence gate."""

    PENDING = "pending", "Pending (not decided yet)"
    APPROVED = "approved", "Approved"
    REVIEW = "review", "Awaiting licence review"
    REJECTED = "rejected", "Rejected"


def gate_constraints(prefix: str) -> list[models.BaseConstraint]:
    """Build the §1.1 check constraints for one concrete gated model.

    Args:
        prefix: A unique name prefix for the constraints (the table name).

    Returns:
        Check constraints that hold for every row of the model:
        rewriting implies display; display implies an approved gate status
        and an open licence; rewriting is impossible under a no-derivatives
        licence; an output licence exists exactly when rewriting is allowed.
    """
    return [
        models.CheckConstraint(
            condition=Q(can_rewrite=False) | Q(can_display=True),
            name=f"{prefix}_rewrite_implies_display",
        ),
        models.CheckConstraint(
            condition=Q(can_display=False) | Q(gate_status=GateStatus.APPROVED),
            name=f"{prefix}_display_requires_approval",
        ),
        models.CheckConstraint(
            condition=Q(can_display=False) | Q(licence_family__in=OPEN_FAMILY_VALUES),
            name=f"{prefix}_display_requires_open_licence",
        ),
        models.CheckConstraint(
            condition=Q(can_rewrite=False) | ~Q(licence_family__in=NO_DERIVATIVE_FAMILY_VALUES),
            name=f"{prefix}_no_rewrite_under_nd",
        ),
        models.CheckConstraint(
            condition=(Q(can_rewrite=True) & ~Q(output_licence_family=""))
            | (Q(can_rewrite=False) & Q(output_licence_family="")),
            name=f"{prefix}_output_licence_iff_rewrite",
        ),
    ]


class GatedPermissions(models.Model):
    """Abstract base: a licence decision and the effective permissions.

    Attributes:
        gate_status: Approved, rejected, awaiting review, or pending.
        can_display: The original may be shown (effective; false unless
            approved).
        can_rewrite: A plain-English derivative may be published.
        non_commercial: Only non-commercial use is allowed.
        attribution_required: The authors must be credited.
        share_alike: Derivatives must carry the same licence.
        licence_family: The decided (or, under review, proposed) licence.
        licence_version: Its version, e.g. "4.0".
        licence_jurisdiction: Its jurisdiction port, e.g. "igo".
        output_licence_family: Licence a rewrite must carry ("" if none).
        output_licence_version: Its version.
        output_licence_jurisdiction: Its jurisdiction port.
        decision_source: Where the decision came from: a licence field
            such as ``pmc:license_code``, ``licence-review:<id>``, or "".
        decision_reasons: Human-readable reasons from the gate.
        decided_at: When the decision was last computed.
    """

    gate_status = models.CharField(
        max_length=16, choices=GateStatus.choices, default=GateStatus.PENDING, db_index=True
    )
    can_display = models.BooleanField(default=False)
    can_rewrite = models.BooleanField(default=False)
    non_commercial = models.BooleanField(default=False)
    attribution_required = models.BooleanField(default=False)
    share_alike = models.BooleanField(default=False)
    licence_family = models.CharField(
        max_length=32, choices=LICENCE_FAMILY_CHOICES, default=LicenceFamily.UNKNOWN.value
    )
    licence_version = models.CharField(max_length=16, blank=True)
    licence_jurisdiction = models.CharField(max_length=16, blank=True)
    output_licence_family = models.CharField(
        max_length=32, choices=LICENCE_FAMILY_CHOICES, blank=True
    )
    output_licence_version = models.CharField(max_length=16, blank=True)
    output_licence_jurisdiction = models.CharField(max_length=16, blank=True)
    decision_source = models.CharField(max_length=64, blank=True)
    decision_reasons = models.JSONField(default=list, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        """Abstract: concrete models add :func:`gate_constraints`."""

        abstract = True

    @property
    def licence(self) -> Licence:
        """The decided (or proposed) licence as an rbcore value."""
        return Licence(
            LicenceFamily(self.licence_family),
            self.licence_version or None,
            self.licence_jurisdiction or None,
        )

    @property
    def output_licence(self) -> Licence | None:
        """The licence a rewrite must carry, or None when rewriting is not allowed."""
        if not self.output_licence_family:
            return None
        return Licence(
            LicenceFamily(self.output_licence_family),
            self.output_licence_version or None,
            self.output_licence_jurisdiction or None,
        )

    @property
    def permissions(self) -> Permissions:
        """The effective permissions as an rbcore value."""
        return Permissions(
            can_display=self.can_display,
            can_rewrite=self.can_rewrite,
            output_licence=self.output_licence,
            non_commercial=self.non_commercial,
            attribution_required=self.attribution_required,
            share_alike=self.share_alike,
        )

    def set_decision(
        self,
        *,
        status: GateStatus,
        licence: Licence,
        permissions: Permissions,
        source: str,
        reasons: list[str],
        decided_at: datetime,
    ) -> None:
        """Store a gate decision on this row (without saving it).

        Permissions are stored only for approved decisions; any other status
        stores no permissions, so the row fails closed.

        Args:
            status: The gate status.
            licence: The decided or proposed licence.
            permissions: Permissions derived from the licence.
            source: Where the decision came from.
            reasons: Human-readable reasons.
            decided_at: The decision time (a timezone-aware datetime).
        """
        granted = permissions if status == GateStatus.APPROVED else None
        output = granted.output_licence if granted else None
        self.gate_status = status
        self.licence_family = licence.family.value
        self.licence_version = licence.version or ""
        self.licence_jurisdiction = licence.jurisdiction or ""
        self.can_display = bool(granted and granted.can_display)
        self.can_rewrite = bool(granted and granted.can_rewrite)
        self.non_commercial = bool(granted and granted.non_commercial)
        self.attribution_required = bool(granted and granted.attribution_required)
        self.share_alike = bool(granted and granted.share_alike)
        self.output_licence_family = output.family.value if output else ""
        self.output_licence_version = (output.version or "") if output else ""
        self.output_licence_jurisdiction = (output.jurisdiction or "") if output else ""
        self.decision_source = source
        self.decision_reasons = reasons
        self.decided_at = decided_at


# Fields written by set_decision, for bulk_update calls.
GATE_FIELDS: tuple[str, ...] = (
    "gate_status",
    "licence_family",
    "licence_version",
    "licence_jurisdiction",
    "can_display",
    "can_rewrite",
    "non_commercial",
    "attribution_required",
    "share_alike",
    "output_licence_family",
    "output_licence_version",
    "output_licence_jurisdiction",
    "decision_source",
    "decision_reasons",
    "decided_at",
)
