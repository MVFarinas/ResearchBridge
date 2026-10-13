"""The validation status of the scores, attached to every output.

Kept in one place so that a later, validated release changes the status in
exactly one module (and records the final definitions in decisions.md,
superseding the §2.4 drafts).
"""

from typing import Final

PROVISIONAL: Final = True
"""True until both scores are validated against human judgements."""

METHOD_VERSION: Final = "rbscores-0.1-provisional"
"""Identifies the score definitions; bump it whenever a definition changes."""

PROVISIONAL_NOTICE: Final = (
    "PROVISIONAL: these readability and prior-knowledge burden scores are draft "
    "definitions (decisions.md §2.4). They have not been validated against lay "
    "readers' judgements and must not be shown to readers as a measure of difficulty."
)
"""Human-readable notice included in every score report."""
