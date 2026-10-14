"""The reader API (Django REST framework): papers, search, lookup and credibility.

Read-only for the public except the lookup endpoint, which may queue an
eligible paper for ingestion. Every read of corpus content goes through the
licence-gated access layer (:mod:`rb_backend.corpus.access`).
"""
