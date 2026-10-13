"""Corpus models: papers, versions, content, licence provenance and reviews."""

from rb_backend.corpus.models.gated import GatedPermissions, GateStatus
from rb_backend.corpus.models.licensing import (
    BlockScope,
    LicenceRecord,
    LicenceReview,
    PermissionsBlockRecord,
    ReviewScope,
    ReviewStatus,
)
from rb_backend.corpus.models.papers import (
    ContentState,
    Figure,
    Paper,
    PaperVersion,
    Paragraph,
    Section,
    Source,
)
from rb_backend.corpus.models.search import SEARCH_CONFIG, SearchDocument

__all__ = [
    "SEARCH_CONFIG",
    "BlockScope",
    "ContentState",
    "Figure",
    "GateStatus",
    "GatedPermissions",
    "LicenceRecord",
    "LicenceReview",
    "Paper",
    "PaperVersion",
    "Paragraph",
    "PermissionsBlockRecord",
    "ReviewScope",
    "ReviewStatus",
    "SearchDocument",
    "Section",
    "Source",
]
