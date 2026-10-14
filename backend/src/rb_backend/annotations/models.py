"""Annotation, revision, vote and report tables (decisions.md §1.3).

An :class:`Annotation` is a W3C Web Annotation scoped to one paper version and
one paragraph, with a ``provenance`` (``llm``, ``human`` or ``llm_edited``),
the ``model`` and ``prompt_version`` that produced it, and a full edit history
in :class:`AnnotationRevision`. Votes and reports are separate tables, used
from Phase 7. Nothing here generates content: Phase 3 writes LLM annotations,
Phase 7 human ones.
"""

from __future__ import annotations

import hashlib
import uuid
from typing import Any, Self

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Q

from rb_backend.annotations.w3c import validate_anchor, validate_body, validate_target
from rb_backend.corpus.models import PaperVersion, Paragraph
from rb_backend.corpus.querysets import part_displayable_q, version_displayable_q


class Provenance(models.TextChoices):
    """Who wrote an annotation (decisions.md §1.3)."""

    LLM = "llm", "LLM draft"
    HUMAN = "human", "Human-written"
    LLM_EDITED = "llm_edited", "LLM draft edited by a human"


class Motivation(models.TextChoices):
    """W3C motivations used for explanations (annotation model section 3.3.5)."""

    COMMENTING = "commenting", "Commenting"
    DESCRIBING = "describing", "Describing"
    QUESTIONING = "questioning", "Questioning"
    EDITING = "editing", "Editing"


class AnnotationQuerySet(models.QuerySet["Annotation"]):
    """Querysets of annotations with the licence-gated read method."""

    def displayable(self) -> Self:
        """Annotations whose paragraph (and version) may be displayed.

        Annotations quote the text they anchor to, so they are shown only
        where that text may be shown. An annotation whose paragraph was
        removed by a re-ingestion is withheld until it is re-anchored.

        Returns:
            The filtered queryset.
        """
        return self.filter(
            Q(paragraph__isnull=False)
            & part_displayable_q("paragraph__")
            & version_displayable_q("paper_version__")
        )

    def rewriteable(self) -> Self:
        """Annotations are not rewritten; this returns nothing.

        Defined so the gated-read check can treat every gated model alike.

        Returns:
            An empty queryset.
        """
        return self.none()


class Annotation(models.Model):
    """A W3C Web Annotation anchored to one paragraph of one paper version.

    Attributes:
        id: Public UUID (the annotation's IRI is built from it).
        paper_version: The version annotated.
        paragraph: The paragraph the selectors are relative to; null when a
            re-ingestion removed it (the annotation then needs re-anchoring).
        paragraph_stable_id: The paragraph's stable ID, kept if it goes.
        paragraph_text_sha256: Hash of the paragraph text the selectors
            were computed against, to detect drift after re-ingestion.
        target: W3C target: ``source`` plus a TextQuoteSelector and a
            TextPositionSelector (see :mod:`rb_backend.annotations.w3c`).
        body: W3C ``TextualBody``.
        motivation: W3C motivation.
        provenance: llm, human or llm_edited.
        model: Model ID that generated it (LLM provenance); never hard-coded.
        prompt_version: Prompt version that generated it (LLM provenance).
        author: The human author or editor, if any.
        verified_at: When a human verified it (clears the disclaimer).
        verified_by: Who verified it.
        superseded_by: A better annotation of the same passage, if any; the
            superseded one stays available behind the provenance filter.
        created_at: Creation time.
        updated_at: Last update time.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    paper_version = models.ForeignKey(
        PaperVersion, on_delete=models.PROTECT, related_name="annotations"
    )
    paragraph = models.ForeignKey(
        Paragraph, null=True, blank=True, on_delete=models.SET_NULL, related_name="annotations"
    )
    paragraph_stable_id = models.CharField(max_length=160)
    paragraph_text_sha256 = models.CharField(max_length=64)
    target = models.JSONField()
    body = models.JSONField()
    motivation = models.CharField(
        max_length=16, choices=Motivation.choices, default=Motivation.COMMENTING
    )
    provenance = models.CharField(max_length=16, choices=Provenance.choices)
    model = models.CharField(max_length=128, blank=True)
    prompt_version = models.CharField(max_length=64, blank=True)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="authored_annotations",
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="verified_annotations",
    )
    superseded_by = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="supersedes"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = AnnotationQuerySet.as_manager()

    class Meta:
        """Provenance rules enforced by the database."""

        ordering = ["paper_version", "paragraph_stable_id", "created_at"]
        constraints = [
            # LLM-originated annotations must say which model and prompt made them.
            models.CheckConstraint(
                condition=Q(provenance=Provenance.HUMAN) | (~Q(model="") & ~Q(prompt_version="")),
                name="annotation_llm_has_model_and_prompt",
            ),
            # A human annotation has no model or prompt.
            models.CheckConstraint(
                condition=~Q(provenance=Provenance.HUMAN) | (Q(model="") & Q(prompt_version="")),
                name="annotation_human_has_no_model",
            ),
            models.CheckConstraint(
                condition=Q(verified_by__isnull=True) | Q(verified_at__isnull=False),
                name="annotation_verifier_has_time",
            ),
        ]

    def __str__(self) -> str:
        """Return the provenance, version and paragraph."""
        return f"{self.provenance} annotation on {self.paper_version_id}/{self.paragraph_stable_id}"

    @property
    def needs_disclaimer(self) -> bool:
        """Whether the accuracy disclaimer must be shown (§1.3).

        Every LLM-originated annotation carries it until a human verifies it.
        """
        return self.provenance != Provenance.HUMAN and self.verified_at is None

    def clean(self) -> None:
        """Validate the W3C shapes and, for a new annotation, the anchoring.

        Raises:
            ValidationError: If the target or body is malformed, the
                paragraph belongs to a different version, or (on creation)
                the selectors do not match the paragraph text.
        """
        validate_target(self.target)
        validate_body(self.body)
        if self.paragraph is None:
            return
        if self.paragraph.version_id != self.paper_version_id:
            raise ValidationError("the paragraph belongs to a different paper version")
        # Anchoring is checked against the text as it is when the annotation is made.
        if self._state.adding:
            validate_anchor(self.target, self.paragraph.text)

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Validate, fill in the anchoring fields, save, and record a revision.

        Pass ``editor=<user>`` to attribute the revision to someone.

        Args:
            *args: Passed to :meth:`django.db.models.Model.save`.
            **kwargs: Passed on, except ``editor``.
        """
        editor = kwargs.pop("editor", None)
        # Remember which text the selectors were computed against.
        if self._state.adding and self.paragraph is not None:
            self.paragraph_stable_id = self.paragraph.stable_id
            self.paragraph_text_sha256 = hashlib.sha256(
                self.paragraph.text.encode("utf-8")
            ).hexdigest()
        self.clean()
        with transaction.atomic():
            super().save(*args, **kwargs)
            self._record_revision(editor)

    def _record_revision(self, editor: Any) -> None:
        """Append a revision if the content differs from the latest one.

        Args:
            editor: The user who made the change, or None.
        """
        latest = self.revisions.order_by("-number").first()
        snapshot = {
            "target": self.target,
            "body": self.body,
            "motivation": self.motivation,
            "provenance": self.provenance,
            "model": self.model,
            "prompt_version": self.prompt_version,
        }
        # Saves that change nothing in the content (e.g. verification) add no revision.
        if latest is not None and latest.snapshot() == snapshot:
            return
        AnnotationRevision.objects.create(
            annotation=self,
            number=(latest.number + 1) if latest else 1,
            editor=editor,
            **snapshot,
        )


class AnnotationRevision(models.Model):
    """One version of an annotation's content: the full edit history.

    Attributes:
        annotation: The annotation.
        number: 1 for the original, then 2, 3, ...
        target: Target at this revision.
        body: Body at this revision.
        motivation: Motivation at this revision.
        provenance: Provenance at this revision.
        model: Model ID at this revision.
        prompt_version: Prompt version at this revision.
        editor: Who made this revision, if known.
        note: Optional change note.
        created_at: When it was recorded.
    """

    annotation = models.ForeignKey(Annotation, on_delete=models.CASCADE, related_name="revisions")
    number = models.PositiveIntegerField()
    target = models.JSONField()
    body = models.JSONField()
    motivation = models.CharField(max_length=16, choices=Motivation.choices)
    provenance = models.CharField(max_length=16, choices=Provenance.choices)
    model = models.CharField(max_length=128, blank=True)
    prompt_version = models.CharField(max_length=64, blank=True)
    editor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="annotation_revisions",
    )
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """Revision numbers are unique per annotation."""

        ordering = ["annotation", "number"]
        constraints = [
            models.UniqueConstraint(
                fields=["annotation", "number"], name="annotationrevision_unique_number"
            ),
        ]

    def __str__(self) -> str:
        """Return the annotation and revision number."""
        return f"{self.annotation_id} r{self.number}"

    def snapshot(self) -> dict[str, Any]:
        """The content fields, for comparing with the annotation.

        Returns:
            Target, body, motivation, provenance, model and prompt version.
        """
        return {
            "target": self.target,
            "body": self.body,
            "motivation": self.motivation,
            "provenance": self.provenance,
            "model": self.model,
            "prompt_version": self.prompt_version,
        }


class Vote(models.Model):
    """A reader's up or down vote on an annotation (Phase 7).

    Attributes:
        annotation: The annotation.
        voter: Who voted.
        value: +1 or -1.
        created_at: When.
    """

    annotation = models.ForeignKey(Annotation, on_delete=models.CASCADE, related_name="votes")
    voter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="annotation_votes"
    )
    value = models.SmallIntegerField(choices=[(1, "Up"), (-1, "Down")])
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """One vote per reader per annotation; only +1 or -1."""

        constraints = [
            models.UniqueConstraint(fields=["annotation", "voter"], name="vote_one_per_voter"),
            models.CheckConstraint(condition=Q(value__in=[1, -1]), name="vote_value_is_unit"),
        ]

    def __str__(self) -> str:
        """Return the vote value and annotation."""
        return f"{self.value:+d} on {self.annotation_id}"


class Report(models.Model):
    """A reader's report that an annotation is wrong or inappropriate (Phase 7).

    Attributes:
        annotation: The annotation.
        reporter: Who reported it, if signed in.
        reason: Why.
        details: Free-text detail.
        status: Open, upheld or dismissed.
        resolved_by: The moderator who resolved it.
        resolved_at: When.
        created_at: When it was made.
    """

    class Reason(models.TextChoices):
        """Why an annotation was reported."""

        INACCURATE = "inaccurate", "Inaccurate"
        MISLEADING = "misleading", "Misleading or overstated"
        OFFENSIVE = "offensive", "Offensive"
        SPAM = "spam", "Spam"
        COPYRIGHT = "copyright", "Copyright concern"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        """Where a report stands."""

        OPEN = "open", "Open"
        UPHELD = "upheld", "Upheld"
        DISMISSED = "dismissed", "Dismissed"

    annotation = models.ForeignKey(Annotation, on_delete=models.CASCADE, related_name="reports")
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="annotation_reports",
    )
    reason = models.CharField(max_length=16, choices=Reason.choices)
    details = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="resolved_annotation_reports",
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """A resolved report records when it was resolved."""

        constraints = [
            models.CheckConstraint(
                condition=Q(status="open") | Q(resolved_at__isnull=False),
                name="report_resolution_has_time",
            ),
        ]

    def __str__(self) -> str:
        """Return the reason and status."""
        return f"{self.reason} report on {self.annotation_id} ({self.status})"
