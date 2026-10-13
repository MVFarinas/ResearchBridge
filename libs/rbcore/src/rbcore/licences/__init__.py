"""Licence normalisation and the decisions.md §1.1 permission gate.

Typical use with a parsed JATS article::

    from rbcore.licences import decide, decide_part

    article_decision = decide(article.permissions.evidence())
    if article_decision.permissions.can_rewrite:
        ...
    for figure in article.figures:
        figure_decision = decide_part(article_decision, figure.permissions)
    for paragraph in article.iter_paragraphs():
        paragraph_decision = decide_part(article_decision, paragraph.permissions)
"""

from rbcore.licences.model import (
    UNKNOWN_LICENCE,
    AliLicenceRef,
    Licence,
    LicenceEvidence,
    LicenceFamily,
    LicenceField,
    LicenceStatement,
    PermissionsBlock,
)
from rbcore.licences.normalise import normalise_licence
from rbcore.licences.permissions import (
    NO_PERMISSIONS,
    LicenceDecision,
    Permissions,
    decide,
    decide_part,
    derive_permissions,
)

__all__ = [
    "NO_PERMISSIONS",
    "UNKNOWN_LICENCE",
    "AliLicenceRef",
    "Licence",
    "LicenceDecision",
    "LicenceEvidence",
    "LicenceFamily",
    "LicenceField",
    "LicenceStatement",
    "Permissions",
    "PermissionsBlock",
    "decide",
    "decide_part",
    "derive_permissions",
    "normalise_licence",
]
