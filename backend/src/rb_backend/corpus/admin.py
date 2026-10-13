"""Django admin for the corpus: read-mostly, plus the licence review queue.

Papers, versions, licence records and permissions blocks are read-only here:
they come from sources and the gate, and editing them by hand would break
provenance. The one write path is the licence review form, which records a
human decision through :func:`rb_backend.corpus.reviews.resolve_review` and
re-runs the gate.
"""

from __future__ import annotations

from typing import Any, ClassVar

from django import forms
from django.contrib import admin, messages
from django.db import models
from django.db.models import QuerySet
from django.http import HttpRequest

from rb_backend.corpus.models import (
    Figure,
    LicenceRecord,
    LicenceReview,
    Paper,
    PaperVersion,
    Paragraph,
    PermissionsBlockRecord,
    ReviewStatus,
)
from rb_backend.corpus.reviews import ReviewError, resolve_review
from rbcore.licences import LicenceFamily, normalise_licence


class ReadOnlyAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    """An admin that shows rows but never adds, edits or deletes them."""

    # Source URLs are https; say so explicitly (Django 6 changes the default).
    formfield_overrides: ClassVar[dict[type[models.Field[Any, Any]], dict[str, Any]]] = {
        models.URLField: {"assume_scheme": "https"}
    }

    def has_add_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        """Never add rows by hand.

        Args:
            request: The request.
            obj: Unused.

        Returns:
            False.
        """
        return False

    def has_change_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        """Never edit rows by hand (the change page still displays them).

        Args:
            request: The request.
            obj: Unused.

        Returns:
            False.
        """
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        """Never delete rows by hand.

        Args:
            request: The request.
            obj: Unused.

        Returns:
            False.
        """
        return False


class VersionInline(admin.TabularInline):  # type: ignore[type-arg]
    """A paper's versions, read-only."""

    model = PaperVersion
    fields = ("source_version_id", "is_current", "gate_status", "licence_family", "can_display")
    readonly_fields = fields
    extra = 0
    can_delete = False
    show_change_link = True

    def has_add_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        """Never add versions by hand.

        Args:
            request: The request.
            obj: Unused.

        Returns:
            False.
        """
        return False


@admin.register(Paper)
class PaperAdmin(ReadOnlyAdmin):
    """Papers and their identifiers."""

    list_display = ("__str__", "doi", "pmid", "is_retracted", "updated_at")
    list_filter = ("is_retracted",)
    search_fields = ("pmcid", "doi", "pmid", "arxiv_id", "versions__title")
    inlines = (VersionInline,)


@admin.register(PaperVersion)
class PaperVersionAdmin(ReadOnlyAdmin):
    """Paper versions with their licence decision."""

    list_display = (
        "source_version_id",
        "title",
        "is_current",
        "gate_status",
        "licence_family",
        "can_display",
        "can_rewrite",
        "content_state",
        "last_checked_at",
    )
    list_filter = (
        "gate_status",
        "licence_family",
        "is_current",
        "content_state",
        "can_rewrite",
        "is_manuscript",
        "is_retracted",
    )
    search_fields = ("source_version_id", "title", "paper__doi", "paper__pmcid")
    exclude = ("source_metadata",)


@admin.register(LicenceRecord)
class LicenceRecordAdmin(ReadOnlyAdmin):
    """Raw licence values with field, source URL and retrieval date."""

    list_display = (
        "version",
        "field",
        "short_value",
        "normalised_family",
        "specific_use",
        "retrieved_at",
        "superseded_at",
    )
    list_filter = ("field", "normalised_family")
    search_fields = ("version__source_version_id", "raw_value")

    @admin.display(description="value")
    def short_value(self, record: LicenceRecord) -> str:
        """Truncate long prose values in the list.

        Args:
            record: The record.

        Returns:
            At most 80 characters of the raw value.
        """
        return record.raw_value[:80]


@admin.register(PermissionsBlockRecord)
class PermissionsBlockAdmin(ReadOnlyAdmin):
    """JATS permissions blocks by scope and part."""

    list_display = ("version", "scope", "part_stable_id", "context", "inner", "superseded_at")
    list_filter = ("scope", "inner")
    search_fields = ("version__source_version_id", "part_stable_id", "copyright_statement")


@admin.register(Figure)
class FigureAdmin(ReadOnlyAdmin):
    """Figures and tables with their own licence decisions."""

    list_display = ("__str__", "label", "kind", "gate_status", "licence_family", "can_display")
    list_filter = ("gate_status", "kind", "has_own_permissions")
    search_fields = ("version__source_version_id", "label", "caption")


@admin.register(Paragraph)
class ParagraphAdmin(ReadOnlyAdmin):
    """Paragraphs with their licence decisions."""

    list_display = ("__str__", "kind", "gate_status", "licence_family", "has_own_permissions")
    list_filter = ("gate_status", "has_own_permissions", "kind")
    search_fields = ("version__source_version_id", "stable_id", "text")


class ReviewForm(forms.ModelForm):  # type: ignore[type-arg]
    """The reviewer's decision: approve with a licence, or reject, with a note."""

    decision = forms.ChoiceField(
        choices=[("approve", "Approve with the licence below"), ("reject", "Reject")],
        widget=forms.RadioSelect,
    )
    licence = forms.CharField(
        required=False,
        help_text="A licence URI or code, e.g. https://creativecommons.org/licenses/by/4.0/ "
        "or CC BY. Required to approve.",
    )
    note = forms.CharField(widget=forms.Textarea, help_text="Why (required).")

    class Meta:
        """No model fields are edited directly."""

        model = LicenceReview
        fields: tuple[str, ...] = ()

    def clean(self) -> dict[str, Any]:
        """Require a recognised licence for approvals.

        Returns:
            The cleaned data.

        Raises:
            forms.ValidationError: If approving without a recognised licence.
        """
        data = super().clean() or {}
        if data.get("decision") == "approve":
            value = (data.get("licence") or "").strip()
            if normalise_licence(value).family is LicenceFamily.UNKNOWN:
                raise forms.ValidationError("Enter a recognised licence URI or code to approve.")
        return data


@admin.register(LicenceReview)
class LicenceReviewAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    """The licence review queue: nothing here is ever approved automatically."""

    form = ReviewForm
    list_display = (
        "__str__",
        "version",
        "scope",
        "part",
        "status",
        "proposed_family",
        "created_at",
    )
    list_filter = ("status", "scope", "proposed_family")
    search_fields = ("version__source_version_id", "version__title")
    readonly_fields = (
        "version",
        "scope",
        "figure",
        "paragraph",
        "status",
        "reasons",
        "evidence",
        "proposed_family",
        "proposed_version",
        "proposed_jurisdiction",
        "resolved_licence",
        "resolved_family",
        "reviewer",
        "reviewer_note",
        "resolved_at",
        "created_at",
    )

    @admin.display(description="part")
    def part(self, review: LicenceReview) -> str:
        """The figure or paragraph under review.

        Args:
            review: The review.

        Returns:
            The part's stable ID, or "".
        """
        part = review.figure or review.paragraph
        return part.stable_id if part is not None else ""

    def get_queryset(self, request: HttpRequest) -> QuerySet[LicenceReview]:
        """Load related rows for the list.

        Args:
            request: The request.

        Returns:
            The queryset.
        """
        return super().get_queryset(request).select_related("version", "figure", "paragraph")

    def has_add_permission(self, request: HttpRequest) -> bool:
        """Reviews are opened by the gate, never by hand.

        Args:
            request: The request.

        Returns:
            False.
        """
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        """Reviews are part of the audit trail and are never deleted.

        Args:
            request: The request.
            obj: Unused.

        Returns:
            False.
        """
        return False

    def has_change_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        """Only open reviews can be resolved.

        Args:
            request: The request.
            obj: The review, if on its page.

        Returns:
            True for open reviews (and the list) when the user may change reviews.
        """
        if obj is not None and obj.status != ReviewStatus.OPEN:
            return False
        return super().has_change_permission(request, obj)

    def save_model(self, request: HttpRequest, obj: LicenceReview, form: Any, change: bool) -> None:
        """Resolve the review through the service instead of saving the form.

        Args:
            request: The request.
            obj: The review.
            form: The validated :class:`ReviewForm`.
            change: Always True (adding is disabled).
        """
        data = form.cleaned_data
        try:
            status = resolve_review(
                obj,
                approve=data["decision"] == "approve",
                licence_value=data.get("licence") or "",
                note=data["note"],
                reviewer=request.user if request.user.is_authenticated else None,
            )
        except ReviewError as exc:
            self.message_user(request, str(exc), level=messages.ERROR)
            return
        self.message_user(request, f"{obj.version}: gate status is now {status}.")
