"""App configuration for the corpus app."""

from django.apps import AppConfig


class CorpusConfig(AppConfig):
    """Configuration for :mod:`rb_backend.corpus`."""

    name = "rb_backend.corpus"
    label = "corpus"
    verbose_name = "Corpus and licence gate"
