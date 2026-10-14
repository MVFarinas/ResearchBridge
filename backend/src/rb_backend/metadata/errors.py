"""Errors raised by the metadata clients."""

from __future__ import annotations


class UpstreamError(RuntimeError):
    """An external metadata service could not give an answer.

    Attributes:
        source: The service, e.g. "openalex".
        status: The HTTP status, when the failure was one.
    """

    def __init__(self, source: str, message: str, *, status: int | None = None) -> None:
        """Create the error.

        Args:
            source: The service.
            message: What went wrong (never containing a secret).
            status: The HTTP status, if any.
        """
        super().__init__(f"{source}: {message}")
        self.source = source
        self.status = status


class UpstreamRefusedError(UpstreamError):
    """The service refused the request: a key is needed, a budget is spent, or a rate limit hit."""
