"""Licence normalisation and the decisions.md §1.1 permission gate.

Typical use with a parsed JATS article::

    from rbcore.licences import decide, decide_figure

    article_decision = decide(article.permissions.evidence())
    if article_decision.permissions.can_rewrite:
        ...
    for figure in article.figures:
        figure_decision = decide_figure(article_decision, figure.permissions)
"""

from rbcore.licences.model import (
    UNKNOWN_LICENCE,
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
    decide_figure,
    derive_permissions,
)

__all__ = [
    "NO_PERMISSIONS",
    "UNKNOWN_LICENCE",
    "Licence",
    "LicenceDecision",
    "LicenceEvidence",
    "LicenceFamily",
    "LicenceField",
    "LicenceStatement",
    "Permissions",
    "PermissionsBlock",
    "decide",
    "decide_figure",
    "derive_permissions",
    "normalise_licence",
]
