"""Tests for rbcore.licences.normalise and the Licence model."""

from __future__ import annotations

import pytest

from rbcore.licences import Licence, LicenceFamily, normalise_licence

F = LicenceFamily


@pytest.mark.parametrize(
    ("value", "family", "version", "jurisdiction"),
    [
        # Every CC family, current version, both schemes and with/without www.
        ("https://creativecommons.org/licenses/by/4.0/", F.CC_BY, "4.0", None),
        ("http://creativecommons.org/licenses/by-sa/4.0/", F.CC_BY_SA, "4.0", None),
        ("https://www.creativecommons.org/licenses/by-nd/4.0", F.CC_BY_ND, "4.0", None),
        ("http://creativecommons.org/licenses/by-nc/4.0/", F.CC_BY_NC, "4.0", None),
        ("https://creativecommons.org/licenses/by-nc-sa/4.0/", F.CC_BY_NC_SA, "4.0", None),
        ("https://creativecommons.org/licenses/by-nc-nd/4.0/", F.CC_BY_NC_ND, "4.0", None),
        # Older versions and jurisdiction ports.
        ("http://creativecommons.org/licenses/by/2.0", F.CC_BY, "2.0", None),
        ("http://creativecommons.org/licenses/by/2.5/", F.CC_BY, "2.5", None),
        ("https://creativecommons.org/licenses/by/3.0/us/", F.CC_BY, "3.0", "us"),
        ("https://creativecommons.org/licenses/by-nc-nd/3.0/igo/", F.CC_BY_NC_ND, "3.0", "igo"),
        (
            "http://creativecommons.org/licenses/by-nc-sa/2.5/scotland/",
            F.CC_BY_NC_SA,
            "2.5",
            "scotland",
        ),
        # CC 1.0 spelled NC-ND as "by-nd-nc".
        ("http://creativecommons.org/licenses/by-nd-nc/1.0/", F.CC_BY_NC_ND, "1.0", None),
        # Rendering suffixes, upper case, no scheme, and the British spelling seen in the wild.
        ("https://creativecommons.org/licenses/by/4.0/legalcode", F.CC_BY, "4.0", None),
        ("https://creativecommons.org/licenses/by/4.0/legalcode.de", F.CC_BY, "4.0", None),
        ("https://creativecommons.org/licenses/by-nc/4.0/deed.en", F.CC_BY_NC, "4.0", None),
        ("HTTPS://CreativeCommons.org/Licenses/BY/4.0/", F.CC_BY, "4.0", None),
        ("creativecommons.org/licenses/by/4.0", F.CC_BY, "4.0", None),
        ("https://creativecommons.org/licences/by/4.0/", F.CC_BY, "4.0", None),
        ("https://creativecommons.org/licenses/by/4.0/?ref=chooser", F.CC_BY, "4.0", None),
        ("https://creativecommons.org/licenses/by/", F.CC_BY, None, None),
        # CC0 and public domain.
        ("http://creativecommons.org/publicdomain/zero/1.0/", F.CC0, "1.0", None),
        ("https://creativecommons.org/publicdomain/zero/1.0/legalcode", F.CC0, "1.0", None),
        ("https://creativecommons.org/publicdomain/mark/1.0/", F.PUBLIC_DOMAIN, None, None),
        ("http://creativecommons.org/licenses/publicdomain/", F.PUBLIC_DOMAIN, None, None),
        # arXiv licence URIs (OAI-PMH metadataPrefix=arXiv).
        ("http://arxiv.org/licenses/nonexclusive-distrib/1.0/", F.ARXIV_NONEXCLUSIVE, "1.0", None),
        ("https://arxiv.org/licenses/nonexclusive-distrib/1.0", F.ARXIV_NONEXCLUSIVE, "1.0", None),
        ("http://arxiv.org/licenses/assumed-1991-2003/", F.ARXIV_NONEXCLUSIVE, None, None),
    ],
)
def test_normalises_licence_urls(
    value: str, family: LicenceFamily, version: str | None, jurisdiction: str | None
) -> None:
    """Licence URLs in every form normalise to the right family, version and port."""
    assert normalise_licence(value) == Licence(family, version, jurisdiction)


@pytest.mark.parametrize(
    ("value", "family", "version"),
    [
        # PMC Cloud Service license_code values.
        ("CC BY", F.CC_BY, None),
        ("CC BY-SA", F.CC_BY_SA, None),
        ("CC BY-ND", F.CC_BY_ND, None),
        ("CC BY-NC", F.CC_BY_NC, None),
        ("CC BY-NC-SA", F.CC_BY_NC_SA, None),
        ("CC BY-NC-ND", F.CC_BY_NC_ND, None),
        ("CC0", F.CC0, None),
        ("TDM", F.TDM, None),
        # Europe PMC search "license" values.
        ("cc by", F.CC_BY, None),
        ("cc by-nc-nd", F.CC_BY_NC_ND, None),
        ("cc0", F.CC0, None),
        # bioRxiv / medRxiv API values.
        ("cc_by", F.CC_BY, None),
        ("cc_by_nc", F.CC_BY_NC, None),
        ("cc_by_nd", F.CC_BY_ND, None),
        ("cc_by_nc_nd", F.CC_BY_NC_ND, None),
        ("cc0_ng", F.CC0, None),
        ("cc_no", F.ALL_RIGHTS_RESERVED, None),
        # SPDX identifiers and free-standing names.
        ("CC-BY-4.0", F.CC_BY, "4.0"),
        ("CC-BY-NC-ND-4.0", F.CC_BY_NC_ND, "4.0"),
        ("CC0-1.0", F.CC0, "1.0"),
        ("CC BY 4.0", F.CC_BY, "4.0"),
        ("public domain", F.PUBLIC_DOMAIN, None),
        ("Public-Domain", F.PUBLIC_DOMAIN, None),
        ("All rights reserved", F.ALL_RIGHTS_RESERVED, None),
    ],
)
def test_normalises_licence_codes(value: str, family: LicenceFamily, version: str | None) -> None:
    """Codes from PMC, Europe PMC, bioRxiv and SPDX normalise correctly."""
    licence = normalise_licence(value)
    assert licence.family is family
    assert licence.version == version


@pytest.mark.parametrize(
    "value",
    [
        "",
        "   ",
        "open-access",  # a common, meaningless @license-type value
        "other",
        "https://www.elsevier.com/open-access/userlicense/1.0/",
        "http://www.springer.com/tdm",
        "https://creativecommons.org/licenses/sampling+/1.0/",
        "https://creativecommons.org/licenses/nd/1.0/",  # CC 1.0 without attribution
        "https://creativecommons.org/",
        "https://example.org/licenses/by/4.0/",
        "http://arxiv.org/licenses/something-else/",
        "file:///etc/passwd",
        # Prose is never interpreted, even when it names a licence.
        "This article is distributed under the terms of the Creative Commons Attribution License",
        "CC BY or CC BY-NC",
    ],
)
def test_unrecognised_values_are_unknown(value: str) -> None:
    """Anything not recognised normalises to UNKNOWN (and so fails closed)."""
    assert normalise_licence(value).family is F.UNKNOWN


@pytest.mark.parametrize(
    ("licence", "flags"),
    [
        (Licence(F.CC_BY, "4.0"), (True, False, False, False, True)),
        (Licence(F.CC_BY_SA, "4.0"), (True, True, False, False, True)),
        (Licence(F.CC_BY_ND, "4.0"), (True, False, False, True, True)),
        (Licence(F.CC_BY_NC, "4.0"), (True, False, True, False, True)),
        (Licence(F.CC_BY_NC_SA, "4.0"), (True, True, True, False, True)),
        (Licence(F.CC_BY_NC_ND, "4.0"), (True, False, True, True, True)),
        (Licence(F.CC0, "1.0"), (False, False, False, False, True)),
        (Licence(F.PUBLIC_DOMAIN), (False, False, False, False, True)),
        (Licence(F.ARXIV_NONEXCLUSIVE, "1.0"), (False, False, False, False, False)),
        (Licence(F.TDM), (False, False, False, False, False)),
        (Licence(F.ALL_RIGHTS_RESERVED), (False, False, False, False, False)),
        (Licence(F.UNKNOWN), (False, False, False, False, False)),
    ],
)
def test_licence_flags(licence: Licence, flags: tuple[bool, bool, bool, bool, bool]) -> None:
    """Each family exposes attribution, share-alike, NC, ND and open flags."""
    assert (
        licence.attribution,
        licence.share_alike,
        licence.non_commercial,
        licence.no_derivatives,
        licence.is_open,
    ) == flags


def test_licence_uri_and_label() -> None:
    """Canonical URIs and labels are built from family, version and port."""
    assert Licence(F.CC_BY_NC_ND, "4.0").uri == "https://creativecommons.org/licenses/by-nc-nd/4.0/"
    assert Licence(F.CC_BY, "3.0", "igo").uri == "https://creativecommons.org/licenses/by/3.0/igo/"
    assert Licence(F.CC0, "1.0").uri == "https://creativecommons.org/publicdomain/zero/1.0/"
    assert Licence(F.CC_BY).uri is None  # version unknown: no canonical deed
    assert Licence(F.ALL_RIGHTS_RESERVED).uri is None
    assert Licence(F.CC_BY_NC_SA, "4.0").label == "CC BY-NC-SA 4.0"
    assert Licence(F.CC_BY, "3.0", "igo").label == "CC BY 3.0 IGO"
    assert Licence(F.TDM).label.startswith("Text and data mining only")


def test_round_trip_through_canonical_uri() -> None:
    """Normalising a licence's canonical URI gives the same licence back."""
    for family in (F.CC_BY, F.CC_BY_SA, F.CC_BY_ND, F.CC_BY_NC, F.CC_BY_NC_SA, F.CC_BY_NC_ND):
        licence = Licence(family, "4.0")
        assert licence.uri is not None
        assert normalise_licence(licence.uri) == licence
