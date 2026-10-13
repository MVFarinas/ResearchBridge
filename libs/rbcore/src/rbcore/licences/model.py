"""Data model for licences, licence evidence and raw permissions blocks.

The vocabulary here is shared by every phase: ingestion records *evidence*
(a raw value plus the field it came from), normalisation turns evidence into a
canonical :class:`Licence`, and :mod:`rbcore.licences.permissions` turns a
licence into what ResearchBridge may do with the work (decisions.md §1.1).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class LicenceFamily(StrEnum):
    """Canonical licence families that the §1.1 gate distinguishes.

    Versions and jurisdiction ports are recorded on :class:`Licence`, not here,
    because they never change what the gate allows.
    """

    CC_BY = "cc-by"
    CC_BY_SA = "cc-by-sa"
    CC_BY_ND = "cc-by-nd"
    CC_BY_NC = "cc-by-nc"
    CC_BY_NC_SA = "cc-by-nc-sa"
    CC_BY_NC_ND = "cc-by-nc-nd"
    CC0 = "cc0"
    PUBLIC_DOMAIN = "public-domain"
    ARXIV_NONEXCLUSIVE = "arxiv-nonexclusive"
    TDM = "tdm"
    ALL_RIGHTS_RESERVED = "all-rights-reserved"
    UNKNOWN = "unknown"


# Flags per family: (attribution, share_alike, non_commercial, no_derivatives).
_FAMILY_FLAGS: dict[LicenceFamily, tuple[bool, bool, bool, bool]] = {
    LicenceFamily.CC_BY: (True, False, False, False),
    LicenceFamily.CC_BY_SA: (True, True, False, False),
    LicenceFamily.CC_BY_ND: (True, False, False, True),
    LicenceFamily.CC_BY_NC: (True, False, True, False),
    LicenceFamily.CC_BY_NC_SA: (True, True, True, False),
    LicenceFamily.CC_BY_NC_ND: (True, False, True, True),
    LicenceFamily.CC0: (False, False, False, False),
    LicenceFamily.PUBLIC_DOMAIN: (False, False, False, False),
}

# Families that grant the public a right to redistribute the work verbatim.
_OPEN_FAMILIES = frozenset(_FAMILY_FLAGS)

# Path segment used in creativecommons.org licence URLs for each CC family.
CC_URL_CODES: dict[LicenceFamily, str] = {
    LicenceFamily.CC_BY: "by",
    LicenceFamily.CC_BY_SA: "by-sa",
    LicenceFamily.CC_BY_ND: "by-nd",
    LicenceFamily.CC_BY_NC: "by-nc",
    LicenceFamily.CC_BY_NC_SA: "by-nc-sa",
    LicenceFamily.CC_BY_NC_ND: "by-nc-nd",
}


@dataclass(frozen=True, slots=True)
class Licence:
    """A canonical licence.

    Attributes:
        family: The licence family the gate reasons about.
        version: Licence version such as "4.0", or None when unknown or not
            applicable (e.g. all rights reserved).
        jurisdiction: Jurisdiction port code from the CC URL (e.g. "us",
            "igo"), or None for the international licence.
    """

    family: LicenceFamily
    version: str | None = None
    jurisdiction: str | None = None

    @property
    def attribution(self) -> bool:
        """Whether reuse must credit the original authors."""
        return _FAMILY_FLAGS.get(self.family, (False, False, False, False))[0]

    @property
    def share_alike(self) -> bool:
        """Whether adaptations must carry the same (or a compatible) licence."""
        return _FAMILY_FLAGS.get(self.family, (False, False, False, False))[1]

    @property
    def non_commercial(self) -> bool:
        """Whether the licence forbids commercial use."""
        return _FAMILY_FLAGS.get(self.family, (False, False, False, False))[2]

    @property
    def no_derivatives(self) -> bool:
        """Whether the licence forbids adaptations such as a rewrite."""
        return _FAMILY_FLAGS.get(self.family, (False, False, False, False))[3]

    @property
    def is_open(self) -> bool:
        """Whether the licence lets anyone redistribute the work verbatim."""
        return self.family in _OPEN_FAMILIES

    @property
    def is_creative_commons(self) -> bool:
        """Whether this is one of the six CC attribution licences."""
        return self.family in CC_URL_CODES

    @property
    def uri(self) -> str | None:
        """The canonical licence URL, when one exists and the version is known."""
        if self.family in CC_URL_CODES and self.version:
            port = f"{self.jurisdiction}/" if self.jurisdiction else ""
            return (
                f"https://creativecommons.org/licenses/"
                f"{CC_URL_CODES[self.family]}/{self.version}/{port}"
            )
        if self.family is LicenceFamily.CC0:
            return f"https://creativecommons.org/publicdomain/zero/{self.version or '1.0'}/"
        if self.family is LicenceFamily.ARXIV_NONEXCLUSIVE:
            return "http://arxiv.org/licenses/nonexclusive-distrib/1.0/"
        return None

    @property
    def label(self) -> str:
        """A short human-readable name, e.g. "CC BY-NC-ND 4.0"."""
        names = {
            LicenceFamily.CC0: "CC0",
            LicenceFamily.PUBLIC_DOMAIN: "Public domain",
            LicenceFamily.ARXIV_NONEXCLUSIVE: "arXiv non-exclusive distribution licence",
            LicenceFamily.TDM: "Text and data mining only (author manuscript)",
            LicenceFamily.ALL_RIGHTS_RESERVED: "All rights reserved",
            LicenceFamily.UNKNOWN: "Unknown licence",
        }
        if self.family in CC_URL_CODES:
            base = "CC " + CC_URL_CODES[self.family].upper()
        else:
            base = names[self.family]
        parts = [base]
        if self.version and self.family is not LicenceFamily.ARXIV_NONEXCLUSIVE:
            parts.append(self.version)
        if self.jurisdiction:
            parts.append(self.jurisdiction.upper())
        return " ".join(parts)


UNKNOWN_LICENCE = Licence(LicenceFamily.UNKNOWN)


class LicenceField(StrEnum):
    """Where a licence value was read from.

    Recording the field is required by the §1.1 addendum: some fields are
    authoritative, some are secondary signals, and prose is never used for
    automated decisions.
    """

    JATS_ALI_LICENSE_REF = "jats:ali:license_ref"
    JATS_LICENSE_XLINK_HREF = "jats:license/@xlink:href"
    JATS_LICENSE_TYPE = "jats:license/@license-type"
    JATS_LICENSE_P = "jats:license-p"
    PMC_LICENSE_CODE = "pmc:license_code"
    EUROPE_PMC_LICENSE = "europepmc:license"
    ARXIV_OAI_LICENSE = "arxiv-oai:license"
    BIORXIV_LICENSE = "biorxiv:license"
    CROSSREF_LICENSE = "crossref:license"
    OPENALEX_LICENSE = "openalex:license"

    @property
    def is_machine_readable(self) -> bool:
        """Whether automated gating may use values from this field.

        ``license-p`` is display prose (JATS4R: never for automated
        processing) and ``@license-type`` is an uncontrolled vocabulary
        (often just "open-access"); both go to human review instead.
        """
        return self not in {LicenceField.JATS_LICENSE_P, LicenceField.JATS_LICENSE_TYPE}

    @property
    def is_secondary(self) -> bool:
        """Whether the field is an aggregator signal that must never be the gate."""
        return self in {LicenceField.CROSSREF_LICENSE, LicenceField.OPENALEX_LICENSE}


@dataclass(frozen=True, slots=True)
class LicenceEvidence:
    """One raw licence value and the field it came from.

    Attributes:
        field: The source field.
        value: The raw value exactly as found (URI, code or prose).
        specific_use: JATS ``@specific-use`` on the element, if any (e.g.
            "textmining"), kept for reviewers.
    """

    field: LicenceField
    value: str
    specific_use: str | None = None


@dataclass(frozen=True, slots=True)
class LicenceStatement:
    """One JATS ``<license>`` element, with every licence field kept separately.

    Attributes:
        xlink_href: ``license/@xlink:href``, if present.
        ali_license_refs: Text of each ``ali:license_ref`` inside the licence
            (or directly in the permissions block), in document order.
        ali_specific_uses: ``@specific-use`` of each ``ali:license_ref``,
            aligned with ``ali_license_refs``.
        license_type: ``license/@license-type``, if present.
        prose: Flattened text of the ``license-p`` paragraphs, if any.
    """

    xlink_href: str | None = None
    ali_license_refs: tuple[str, ...] = ()
    ali_specific_uses: tuple[str | None, ...] = ()
    license_type: str | None = None
    prose: str | None = None

    def evidence(self) -> tuple[LicenceEvidence, ...]:
        """Return this statement's values as evidence, machine-readable first.

        Returns:
            Evidence in the order ali:license_ref, @xlink:href,
            @license-type, license-p.
        """
        items: list[LicenceEvidence] = []
        uses: tuple[str | None, ...] = self.ali_specific_uses or (None,) * len(
            self.ali_license_refs
        )
        for ref, use in zip(self.ali_license_refs, uses, strict=True):
            items.append(LicenceEvidence(LicenceField.JATS_ALI_LICENSE_REF, ref, use))
        if self.xlink_href:
            items.append(LicenceEvidence(LicenceField.JATS_LICENSE_XLINK_HREF, self.xlink_href))
        if self.license_type:
            items.append(LicenceEvidence(LicenceField.JATS_LICENSE_TYPE, self.license_type))
        if self.prose:
            items.append(LicenceEvidence(LicenceField.JATS_LICENSE_P, self.prose))
        return tuple(items)


@dataclass(frozen=True, slots=True)
class PermissionsBlock:
    """A raw JATS ``<permissions>`` block, for an article or a figure/table.

    Attributes:
        copyright_statement: ``copyright-statement`` text.
        copyright_years: ``copyright-year`` values.
        copyright_holders: ``copyright-holder`` values.
        licences: One statement per ``<license>`` element (plus one for any
            ``ali:license_ref`` placed directly in the block).
        free_to_read: Whether ``ali:free_to_read`` is present. This is an
            access flag, not a reuse licence, and never affects the gate.
    """

    copyright_statement: str | None = None
    copyright_years: tuple[str, ...] = ()
    copyright_holders: tuple[str, ...] = ()
    licences: tuple[LicenceStatement, ...] = field(default=())
    free_to_read: bool = False

    def evidence(self) -> tuple[LicenceEvidence, ...]:
        """Return every licence value in the block as evidence.

        Returns:
            Evidence from each licence statement, in document order.
        """
        return tuple(item for statement in self.licences for item in statement.evidence())
