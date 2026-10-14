"""App configuration for the API app."""

from django.apps import AppConfig


class ApiConfig(AppConfig):
    """Configuration for :mod:`rb_backend.api`."""

    name = "rb_backend.api"
    label = "api"
    verbose_name = "Reader API"
