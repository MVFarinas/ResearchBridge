"""What has been generated for a paper: rewrite, summary and LLM annotations.

The generation pipeline (Plan.md Phase 3) does not exist yet, so nothing has
been generated for any paper; the reader shows honest empty states. These
functions are the single place that says so, and the place Phase 3 changes
when generated content is stored.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any


class GenerationStatus(StrEnum):
    """Whether a generated item exists for a paper."""

    AVAILABLE = "available"
    NOT_GENERATED = "not_generated"
    NOT_PERMITTED = "not_permitted"


def rewrite_status(*, can_rewrite: bool, is_retracted: bool) -> dict[str, Any]:
    """The state of a paper's plain-English rewrite.

    Args:
        can_rewrite: Whether the licence gate allows a rewrite (read through
            the gated access layer by the caller).
        is_retracted: Whether the paper is retracted (never rewritten).

    Returns:
        ``{"status", "reason"}``.
    """
    if is_retracted:
        return {
            "status": GenerationStatus.NOT_PERMITTED,
            "reason": "This paper has been retracted, so no plain-English version is produced.",
        }
    if not can_rewrite:
        return {
            "status": GenerationStatus.NOT_PERMITTED,
            "reason": (
                "The paper's licence does not allow derivative works, so only the original "
                "is shown, with explanations."
            ),
        }
    return {
        "status": GenerationStatus.NOT_GENERATED,
        "reason": "A plain-English version has not been generated yet.",
    }


def summary_status() -> dict[str, Any]:
    """The state of a paper's appraisal summary.

    Summaries state facts about a paper, so any displayable paper may have
    one; none has been generated yet.

    Returns:
        ``{"status", "reason"}``.
    """
    return {
        "status": GenerationStatus.NOT_GENERATED,
        "reason": "An appraisal summary has not been generated yet.",
    }
