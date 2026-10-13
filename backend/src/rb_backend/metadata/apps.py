"""App configuration for the metadata app."""

from django.apps import AppConfig


class MetadataConfig(AppConfig):
    """Configuration for :mod:`rb_backend.metadata`."""

    name = "rb_backend.metadata"
    label = "metadata"
    verbose_name = "Scholarly metadata"
