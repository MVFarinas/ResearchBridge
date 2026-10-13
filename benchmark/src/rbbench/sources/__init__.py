"""Clients for the public data sources the benchmark reads.

All requests go through :class:`rbcore.http.PoliteFetcher` (rate limits,
neutral User-Agent, on-disk cache under the gitignored data directory).
Responses are untrusted data: JSON is parsed with the standard library and
XML only through :mod:`rbbench.sources.safexml` or :mod:`rbcore.jats`.
"""
