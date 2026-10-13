"""Licence provenance: raw licence records, JATS permissions blocks, the review queue.

Provenance is stored, not just conclusions (decisions.md §1.1 and its
addendum): every licence value keeps its raw text, the field it came from, the
URL of the document it was read from and when it was retrieved. Records are
never edited in place: when a source changes, the old record is marked
superseded and a new one is written, so the history of a paper's licence can
be audited.

JATS ``<permissions>`` blocks are stored whole (:class:`PermissionsBlockRecord`
with its :class:`LicenceRecord` children), so the exact
:class:`rbcore.licences.PermissionsBlock` can be rebuilt and the gate
recomputed later without re-downloading the article.
"""

from __future__ import annotations

from typing import Self

from django.conf import settings
from django.db import models
from django.db.models import Q

from rb_backend.corpus.models.gated import LICENCE_FAMILY_CHOICES, LICENCE_FIELD_CHOICES
from rb_backend.corpus.models.papers import Figure, PaperVersion, Paragraph
from rbcore.licences import LicenceEvidence, LicenceField


class BlockScope(models.TextChoices):
    """What a JATS permissions block applies to."""

    ARTICLE = "article", "Article"
    FIGURE = "figure", "Figure or table"
    PARAGRAPH = "paragraph", "Paragraph"
    UNATTACHED = "unattached", "Attached to nothing the parser models"


class PermissionsBlockQuerySet(models.QuerySet["PermissionsBlockRecord"]):
    """Querysets of permissions blocks."""

    def active(self) -> Self:
        """Blocks that have not been superseded by a newer copy of the XML.

        Returns:
            The filtered queryset.
        """
        return self.filter(superseded_at__isnull=True)


class LicenceRecordQuerySet(models.QuerySet["LicenceRecord"]):
    """Querysets of licence records."""

    def active(self) -> Self:
        """Records that have not been superseded by a changed source.

        Returns:
            The filtered queryset.
        """
        return self.filter(superseded_at__isnull=True)


class PermissionsBlockRecord(models.Model):
    """One JATS ``<permissions>`` block, attached to the article or a part.

    Attributes:
        version: The paper version whose XML contained the block.
        scope: Article, figure, paragraph, or unattached.
        figure: The figure or table it applies to (figure scope).
        paragraph: The paragraph it applies to (paragraph scope).
        part_stable_id: The part's stable ID, kept if the part row goes.
        position: Order among the blocks of the same part.
        context: Element the block was attached to (rbcore
            ``PermissionsBlock.context``), e.g. "fig" or "graphic".
        inner: True when the block licenses an object nested inside the part
            (it can only narrow the part's decision).
        statement_count: Number of ``<license>`` statements, including
            empty ones, so the block is rebuilt exactly.
        copyright_statement: ``copyright-statement`` text.
        copyright_years: ``copyright-year`` values.
        copyright_holders: ``copyright-holder`` values.
        free_to_read: ``ali:free_to_read`` present (access, not reuse).
        free_to_read_start_date: Its raw start date.
        free_to_read_end_date: Its raw end date.
        source_url: URL of the XML the block was read from.
        retrieved_at: When that XML was retrieved.
        superseded_at: When a newer copy of the XML replaced this block.
    """

    version = models.ForeignKey(
        PaperVersion, on_delete=models.CASCADE, related_name="permission_blocks"
    )
    scope = models.CharField(max_length=16, choices=BlockScope.choices)
    figure = models.ForeignKey(
        Figure, null=True, blank=True, on_delete=models.SET_NULL, related_name="permission_blocks"
    )
    paragraph = models.ForeignKey(
        Paragraph,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="permission_blocks",
    )
    part_stable_id = models.CharField(max_length=160, blank=True)
    position = models.PositiveIntegerField(default=0)
    context = models.CharField(max_length=64, blank=True)
    inner = models.BooleanField(default=False)
    statement_count = models.PositiveIntegerField(default=0)
    copyright_statement = models.TextField(blank=True)
    copyright_years = models.JSONField(default=list, blank=True)
    copyright_holders = models.JSONField(default=list, blank=True)
    free_to_read = models.BooleanField(default=False)
    free_to_read_start_date = models.CharField(max_length=64, blank=True)
    free_to_read_end_date = models.CharField(max_length=64, blank=True)
    source_url = models.URLField(max_length=1000)
    retrieved_at = models.DateTimeField()
    superseded_at = models.DateTimeField(null=True, blank=True)

    objects = PermissionsBlockQuerySet.as_manager()

    class Meta:
        """Article blocks have no part; part blocks name their part's stable ID."""

        ordering = ["version", "scope", "part_stable_id", "position"]
        constraints = [
            models.CheckConstraint(
                condition=~Q(scope=BlockScope.ARTICLE) | Q(part_stable_id=""),
                name="permissionsblock_article_has_no_part",
            ),
            models.CheckConstraint(
                condition=~Q(scope__in=[BlockScope.FIGURE, BlockScope.PARAGRAPH])
                | ~Q(part_stable_id=""),
                name="permissionsblock_part_has_stable_id",
            ),
        ]

    def __str__(self) -> str:
        """Return the scope, part and context."""
        part = f" {self.part_stable_id}" if self.part_stable_id else ""
        return f"{self.version_id} {self.scope}{part} ({self.context or 'no context'})"


class LicenceRecord(models.Model):
    """One raw licence value, the field it came from, and where and when.

    Attributes:
        version: The paper version it describes.
        block: The JATS permissions block it belongs to (JATS fields only).
        statement_index: Which ``<license>`` in the block (JATS fields only).
        position: Order within the statement, or within the source document.
        field: The licence field (rbcore ``LicenceField`` value).
        raw_value: The value exactly as found.
        normalised_family: rbcore's normalisation of the value ("unknown"
            for prose and unrecognised values).
        normalised_version: Normalised licence version.
        normalised_jurisdiction: Normalised jurisdiction port.
        specific_use: JATS ``@specific-use``.
        start_date: NISO ALI ``@start_date`` (raw).
        end_date: ``@end_date`` (raw).
        source_url: URL of the document the value was read from.
        retrieved_at: When the value was first retrieved.
        last_confirmed_at: When a later fetch last found the same value.
        superseded_at: When a changed source replaced this value.
    """

    version = models.ForeignKey(
        PaperVersion, on_delete=models.CASCADE, related_name="licence_records"
    )
    block = models.ForeignKey(
        PermissionsBlockRecord,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="records",
    )
    statement_index = models.PositiveIntegerField(null=True, blank=True)
    position = models.PositiveIntegerField(default=0)
    field = models.CharField(max_length=64, choices=LICENCE_FIELD_CHOICES)
    raw_value = models.TextField()
    normalised_family = models.CharField(max_length=32, choices=LICENCE_FAMILY_CHOICES)
    normalised_version = models.CharField(max_length=16, blank=True)
    normalised_jurisdiction = models.CharField(max_length=16, blank=True)
    specific_use = models.CharField(max_length=64, blank=True)
    start_date = models.CharField(max_length=64, blank=True)
    end_date = models.CharField(max_length=64, blank=True)
    source_url = models.URLField(max_length=1000)
    retrieved_at = models.DateTimeField()
    last_confirmed_at = models.DateTimeField()
    superseded_at = models.DateTimeField(null=True, blank=True)

    objects = LicenceRecordQuerySet.as_manager()

    class Meta:
        """JATS values live in a block; values from other sources never do."""

        ordering = ["version", "block", "statement_index", "position"]
        constraints = [
            models.CheckConstraint(
                condition=(Q(field__startswith="jats:") & Q(block__isnull=False))
                | (~Q(field__startswith="jats:") & Q(block__isnull=True)),
                name="licencerecord_jats_iff_block",
            ),
        ]

    def __str__(self) -> str:
        """Return ``field=value``."""
        return f"{self.field}={self.raw_value[:60]!r}"

    @property
    def licence_field(self) -> LicenceField:
        """The field as an rbcore enum."""
        return LicenceField(self.field)

    def as_evidence(self) -> LicenceEvidence:
        """Return this record as rbcore licence evidence.

        Returns:
            The evidence, with empty optional attributes turned back into None.
        """
        return LicenceEvidence(
            field=self.licence_field,
            value=self.raw_value,
            specific_use=self.specific_use or None,
            start_date=self.start_date or None,
            end_date=self.end_date or None,
        )


class ReviewScope(models.TextChoices):
    """What a licence review is about."""

    VERSION = "version", "Whole paper version"
    FIGURE = "figure", "Figure or table"
    PARAGRAPH = "paragraph", "Paragraph"


class ReviewStatus(models.TextChoices):
    """Where a licence review stands."""

    OPEN = "open", "Open"
    APPROVED = "approved", "Approved with a licence"
    REJECTED = "rejected", "Rejected"
    SUPERSEDED = "superseded", "Superseded (the evidence changed)"


class LicenceReview(models.Model):
    """A licence decision a human must make; never auto-approved.

    A review is tied to the exact evidence and reasons it was opened for
    (``evidence_fingerprint``). A resolution applies only while that
    fingerprint still matches: if a source changes, or a licence date passes,
    the gate opens a new review instead of reusing the old answer.

    Attributes:
        version: The paper version.
        scope: Version, figure or paragraph.
        figure: The figure (figure scope); cleared if the figure row is
            deleted, so a resolved review outlives the text it was about.
        paragraph: The paragraph (paragraph scope); cleared likewise.
        part_stable_id: The part's stable ID (part scopes), kept when the
            part row goes; reviews are matched to parts by it.
        status: Open, approved, rejected or superseded.
        reasons: Why the gate could not decide automatically.
        evidence: Snapshot of the licence evidence the reviewer must judge.
        evidence_fingerprint: SHA-256 over scope, evidence and reasons.
        proposed_family: The highest-precedence machine-readable licence, if
            any (a suggestion, never applied without a reviewer).
        proposed_version: Its version.
        proposed_jurisdiction: Its jurisdiction port.
        resolved_licence: What the reviewer entered (a licence URI or code).
        resolved_family: Its normalised family (approved reviews).
        resolved_version: Its version.
        resolved_jurisdiction: Its jurisdiction port.
        reviewer: Who resolved it.
        reviewer_note: The reviewer's justification.
        resolved_at: When it was resolved.
        created_at: When it was opened.
        updated_at: Last update time.
    """

    version = models.ForeignKey(
        PaperVersion, on_delete=models.CASCADE, related_name="licence_reviews"
    )
    scope = models.CharField(max_length=16, choices=ReviewScope.choices)
    figure = models.ForeignKey(
        Figure, null=True, blank=True, on_delete=models.SET_NULL, related_name="licence_reviews"
    )
    paragraph = models.ForeignKey(
        Paragraph,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="licence_reviews",
    )
    part_stable_id = models.CharField(max_length=160, blank=True)
    status = models.CharField(
        max_length=16, choices=ReviewStatus.choices, default=ReviewStatus.OPEN, db_index=True
    )
    reasons = models.JSONField(default=list)
    evidence = models.JSONField(default=list)
    evidence_fingerprint = models.CharField(max_length=64)
    proposed_family = models.CharField(max_length=32, choices=LICENCE_FAMILY_CHOICES, blank=True)
    proposed_version = models.CharField(max_length=16, blank=True)
    proposed_jurisdiction = models.CharField(max_length=16, blank=True)
    resolved_licence = models.CharField(max_length=255, blank=True)
    resolved_family = models.CharField(max_length=32, choices=LICENCE_FAMILY_CHOICES, blank=True)
    resolved_version = models.CharField(max_length=16, blank=True)
    resolved_jurisdiction = models.CharField(max_length=16, blank=True)
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="licence_reviews",
    )
    reviewer_note = models.TextField(blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """One open review per scope; scopes name their part; approvals name a licence.

        A part-scope review always keeps its part's stable ID. Only a closed
        one may lose its part row (the text was removed or re-parsed without
        it); an open review is superseded before its part is deleted.
        """

        ordering = ["-created_at"]
        verbose_name = "licence review"
        constraints = [
            models.UniqueConstraint(
                fields=["version", "scope", "part_stable_id"],
                condition=Q(status=ReviewStatus.OPEN),
                name="licencereview_one_open_per_scope",
            ),
            models.CheckConstraint(
                condition=(
                    Q(scope=ReviewScope.VERSION)
                    & Q(figure__isnull=True)
                    & Q(paragraph__isnull=True)
                    & Q(part_stable_id="")
                )
                | (
                    Q(scope=ReviewScope.FIGURE)
                    & Q(paragraph__isnull=True)
                    & ~Q(part_stable_id="")
                    & (Q(figure__isnull=False) | ~Q(status=ReviewStatus.OPEN))
                )
                | (
                    Q(scope=ReviewScope.PARAGRAPH)
                    & Q(figure__isnull=True)
                    & ~Q(part_stable_id="")
                    & (Q(paragraph__isnull=False) | ~Q(status=ReviewStatus.OPEN))
                ),
                name="licencereview_scope_matches_part",
            ),
            models.CheckConstraint(
                condition=~Q(status=ReviewStatus.APPROVED) | ~Q(resolved_family=""),
                name="licencereview_approval_names_licence",
            ),
        ]

    def __str__(self) -> str:
        """Return the review number, scope and status."""
        return f"Licence review #{self.pk} ({self.scope}, {self.status})"
