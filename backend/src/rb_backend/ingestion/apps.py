"""App configuration for the ingestion app."""

from django.apps import AppConfig


class IngestionConfig(AppConfig):
    """Configuration for :mod:`rb_backend.ingestion`."""

    name = "rb_backend.ingestion"
    label = "ingestion"
    verbose_name = "Ingestion"

    def ready(self) -> None:
        """Connect ingestion's receivers once the app registry is ready."""
        # Imported here: the receivers import models, which are not loaded earlier.
        from rb_backend.corpus.signals import review_resolved
        from rb_backend.ingestion.receivers import refresh_content_after_review

        review_resolved.connect(
            refresh_content_after_review, dispatch_uid="ingestion-refresh-content-after-review"
        )
