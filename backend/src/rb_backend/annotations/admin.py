"""Django admin for annotations: read-only until moderation arrives in Phase 7."""

from __future__ import annotations

from django.contrib import admin

from rb_backend.annotations.models import Annotation, AnnotationRevision, Report, Vote
from rb_backend.corpus.admin import ReadOnlyAdmin


class RevisionInline(admin.TabularInline):  # type: ignore[type-arg]
    """An annotation's edit history."""

    model = AnnotationRevision
    fields = ("number", "provenance", "model", "prompt_version", "editor", "created_at")
    readonly_fields = fields
    extra = 0
    can_delete = False

    def has_add_permission(self, request: object, obj: object = None) -> bool:
        """Revisions are recorded by saves, never added by hand.

        Args:
            request: The request.
            obj: Unused.

        Returns:
            False.
        """
        return False


@admin.register(Annotation)
class AnnotationAdmin(ReadOnlyAdmin):
    """Annotations with provenance, model and prompt version."""

    list_display = (
        "id",
        "paper_version",
        "paragraph_stable_id",
        "provenance",
        "model",
        "prompt_version",
        "verified_at",
        "created_at",
    )
    list_filter = ("provenance", "motivation", "model", "prompt_version")
    search_fields = ("paper_version__source_version_id", "paragraph_stable_id")
    inlines = (RevisionInline,)


@admin.register(Vote)
class VoteAdmin(ReadOnlyAdmin):
    """Votes on annotations (Phase 7)."""

    list_display = ("annotation", "voter", "value", "created_at")


@admin.register(Report)
class ReportAdmin(ReadOnlyAdmin):
    """Reports on annotations (Phase 7)."""

    list_display = ("annotation", "reason", "status", "created_at")
    list_filter = ("reason", "status")
