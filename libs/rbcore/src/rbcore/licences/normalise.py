"""Normalise raw licence URIs and codes into canonical :class:`Licence` values.

Handles:

* Creative Commons URLs in every version (1.0-4.0) and jurisdiction port,
  over http or https, with or without ``www.``, ``legalcode`` or ``deed.xx``
  suffixes, and the British spelling ``licences`` seen in real data.
* CC0 and the Public Domain Mark (``/publicdomain/zero/``, ``/publicdomain/mark/``).
* arXiv licence URIs, including the non-exclusive distribution licence and the
  "assumed" licence for 1991-2003 papers.
* Codes from PMC (``CC BY-NC-ND``, ``CC0``, ``TDM``), Europe PMC (``cc by``),
  bioRxiv (``cc_by_nc_nd``, ``cc0_ng``, ``cc_no``) and SPDX (``CC-BY-4.0``).

Anything not recognised normalises to ``UNKNOWN``, which the gate treats as
"no display, no rewrite" (fail closed). This module never interprets prose.
"""

from __future__ import annotations

import re
from urllib.parse import urlsplit

from rbcore.licences.model import UNKNOWN_LICENCE, Licence, LicenceFamily

# Creative Commons licence codes as they appear in URLs and codes. CC 1.0
# spelled the NC-ND combination "by-nd-nc", so both orders are accepted.
_CC_CODES: dict[str, LicenceFamily] = {
    "by": LicenceFamily.CC_BY,
    "by-sa": LicenceFamily.CC_BY_SA,
    "by-nd": LicenceFamily.CC_BY_ND,
    "by-nc": LicenceFamily.CC_BY_NC,
    "by-nc-sa": LicenceFamily.CC_BY_NC_SA,
    "by-nc-nd": LicenceFamily.CC_BY_NC_ND,
    "by-nd-nc": LicenceFamily.CC_BY_NC_ND,
}

# Non-CC codes, after lower-casing and turning spaces/underscores into hyphens.
_OTHER_CODES: dict[str, LicenceFamily] = {
    "cc0": LicenceFamily.CC0,
    "cc-zero": LicenceFamily.CC0,
    "cc0-ng": LicenceFamily.CC0,  # bioRxiv: CC0 for US government works
    "public-domain": LicenceFamily.PUBLIC_DOMAIN,
    "publicdomain": LicenceFamily.PUBLIC_DOMAIN,
    "pdm": LicenceFamily.PUBLIC_DOMAIN,
    "tdm": LicenceFamily.TDM,  # PMC author manuscripts: text mining only
    "cc-no": LicenceFamily.ALL_RIGHTS_RESERVED,  # bioRxiv "no reuse"
    "no-reuse": LicenceFamily.ALL_RIGHTS_RESERVED,
    "all-rights-reserved": LicenceFamily.ALL_RIGHTS_RESERVED,
}

# URL path segments that only select a rendering of the licence.
_RENDERING_SEGMENT = re.compile(r"^(legalcode|deed|rdf)(\.[a-z_-]+)?(\.txt)?$")
_VERSION = re.compile(r"^\d+(\.\d+)?$")
_JURISDICTION = re.compile(r"^[a-z]{2,8}$")
# A trailing version and optional jurisdiction on a code, e.g. "-4.0" or "-3.0-igo".
_CODE_VERSION = re.compile(r"-(\d+\.\d+)(?:-([a-z]{2,8}))?$")


def normalise_licence(value: str) -> Licence:
    """Normalise a licence URI or code into a canonical licence.

    Args:
        value: A raw machine-readable licence value: a URL or a short code.
            Prose such as ``license-p`` text must not be passed here.

    Returns:
        The canonical licence; ``UNKNOWN`` when the value is not recognised.
    """
    text = value.strip()
    if not text:
        return UNKNOWN_LICENCE
    if _looks_like_url(text):
        return _from_url(text)
    return _from_code(text)


def _looks_like_url(text: str) -> bool:
    """Decide whether a value is a URL rather than a code.

    Args:
        text: A stripped, non-empty value.

    Returns:
        True for single-token values with a scheme or a known licence host.
    """
    if any(ch.isspace() for ch in text):
        return False
    lowered = text.lower()
    return "://" in lowered or lowered.startswith(("www.", "creativecommons.org", "arxiv.org"))


def _from_url(text: str) -> Licence:
    """Normalise a licence URL.

    Args:
        text: A URL, with or without a scheme.

    Returns:
        The canonical licence, or ``UNKNOWN`` for unrecognised hosts or paths.
    """
    # Give scheme-less URLs a scheme so urlsplit puts the host in netloc.
    parts = urlsplit(text if "://" in text else f"https://{text}")
    host = parts.netloc.lower().removeprefix("www.")
    segments = [s for s in parts.path.lower().split("/") if s]
    segments = [s for s in segments if not _RENDERING_SEGMENT.match(s)]

    if host == "creativecommons.org":
        return _from_cc_path(segments)
    if host in {"arxiv.org", "export.arxiv.org"} and segments[:1] == ["licenses"]:
        return _from_arxiv_path(segments[1:])
    return UNKNOWN_LICENCE


def _from_cc_path(segments: list[str]) -> Licence:
    """Normalise the path of a creativecommons.org URL.

    Args:
        segments: Lower-cased, non-empty path segments with rendering
            suffixes (legalcode, deed.xx) removed.

    Returns:
        The canonical licence, or ``UNKNOWN``.
    """
    if not segments:
        return UNKNOWN_LICENCE
    kind, rest = segments[0], segments[1:]

    # /publicdomain/zero/1.0/ is CC0; /publicdomain/mark/1.0/ is the PD Mark.
    if kind == "publicdomain":
        if rest[:1] == ["zero"]:
            version = rest[1] if len(rest) > 1 and _VERSION.match(rest[1]) else None
            return Licence(LicenceFamily.CC0, version)
        if rest[:1] == ["mark"]:
            return Licence(LicenceFamily.PUBLIC_DOMAIN)
        return UNKNOWN_LICENCE

    if kind not in {"licenses", "licences", "license", "licence"} or not rest:
        return UNKNOWN_LICENCE
    # The retired CC Public Domain Dedication lived under /licenses/publicdomain/.
    if rest[0] == "publicdomain":
        return Licence(LicenceFamily.PUBLIC_DOMAIN)
    family = _CC_CODES.get(rest[0])
    if family is None:
        return UNKNOWN_LICENCE
    version = rest[1] if len(rest) > 1 and _VERSION.match(rest[1]) else None
    jurisdiction = rest[2] if version and len(rest) > 2 and _JURISDICTION.match(rest[2]) else None
    return Licence(family, version, jurisdiction)


def _from_arxiv_path(segments: list[str]) -> Licence:
    """Normalise the path after arxiv.org/licenses/.

    Args:
        segments: Path segments after "licenses".

    Returns:
        The arXiv non-exclusive licence for the known arXiv licences, else
        ``UNKNOWN``.
    """
    if segments[:1] == ["nonexclusive-distrib"]:
        version = segments[1] if len(segments) > 1 and _VERSION.match(segments[1]) else None
        return Licence(LicenceFamily.ARXIV_NONEXCLUSIVE, version)
    # Papers from 1991-2003 carry an "assumed" licence with the same limits.
    if segments[:1] == ["assumed-1991-2003"]:
        return Licence(LicenceFamily.ARXIV_NONEXCLUSIVE)
    return UNKNOWN_LICENCE


def _from_code(text: str) -> Licence:
    """Normalise a licence code such as ``CC BY-NC``, ``cc_by`` or ``CC-BY-4.0``.

    Args:
        text: A stripped, non-empty, non-URL value.

    Returns:
        The canonical licence, or ``UNKNOWN``.
    """
    # Unify separators so "CC BY-NC", "cc_by_nc" and "CC-BY-NC" look the same.
    code = re.sub(r"[\s_]+", "-", text.lower()).strip("-")

    if code in _OTHER_CODES:
        return Licence(_OTHER_CODES[code])
    # SPDX-style CC0 carries a version: "cc0-1.0".
    if code.startswith("cc0-") and _VERSION.match(code.removeprefix("cc0-")):
        return Licence(LicenceFamily.CC0, code.removeprefix("cc0-"))

    # Split off a trailing version (and jurisdiction) before matching the family.
    version: str | None = None
    jurisdiction: str | None = None
    match = _CODE_VERSION.search(code)
    if match:
        version, jurisdiction = match.group(1), match.group(2)
        code = code[: match.start()]

    if code.startswith("cc-"):
        family = _CC_CODES.get(code.removeprefix("cc-"))
        if family is not None:
            return Licence(family, version, jurisdiction)
    return UNKNOWN_LICENCE
