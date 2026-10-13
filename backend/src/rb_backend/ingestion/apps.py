"""App configuration for the ingestion app."""

from django.apps import AppConfig


class IngestionConfig(AppConfig):
    """Configuration for :mod:`rb_backend.ingestion`."""

    name = "rb_backend.ingestion"
    label = "ingestion"
    verbose_name = "Ingestion"
