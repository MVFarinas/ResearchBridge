"""Client for the PMC Cloud Service bucket ``s3://pmc-oa-opendata`` over HTTPS.

Layout (from the bucket README, read 2026-10-13,
https://pmc-oa-opendata.s3.amazonaws.com/README.txt): each article version
lives under a prefix such as ``PMC10718527.1/`` holding ``<prefix>.xml``
(JATS), ``<prefix>.txt``, ``<prefix>.json`` (metadata) and, when licences
allow, the PDF and media. The JSON carries ``license_code`` (a Creative
Commons code, or ``TDM`` for author manuscripts that may only be text-mined)
and ``is_retracted``. Its ``xml_url`` is an ``s3://`` URL with the object's
MD5 as an ``md5`` parameter, which this client checks after download.

The bucket is public: plain HTTPS GETs, no credentials, no AWS SDK. Every
request goes through :class:`rbcore.http.PoliteFetcher` (rate-limited, neutral
User-Agent). Metadata and listings are always fetched fresh, so re-runs see
changes; the XML is cached by its URL, which embeds its MD5, so a cached copy
is reused only while it is still the current object.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit

from defusedxml import ElementTree

from rbcore.http import PoliteFetcher

BUCKET = "pmc-oa-opendata"
BASE_URL = f"https://{BUCKET}.s3.amazonaws.com"
_S3_NAMESPACE = "{http://s3.amazonaws.com/doc/2006-03-01/}"
_PMCID = re.compile(r"^PMC(\d+)$")
_VERSION_PREFIX = re.compile(r"^(PMC\d+)\.(\d+)/$")


class PmcError(RuntimeError):
    """Raised when the bucket returns something this client cannot use."""


def normalise_pmcid(value: str) -> str:
    """Normalise a PMC ID to ``PMC<digits>``.

    Args:
        value: ``PMC123``, ``pmc123`` or ``123``.

    Returns:
        The ID with its ``PMC`` prefix.

    Raises:
        PmcError: If the value is not a PMC ID.
    """
    text = value.strip().upper()
    if text.isdigit():
        text = f"PMC{text}"
    if not _PMCID.match(text):
        raise PmcError(f"not a PMC ID: {value!r}")
    return text


@dataclass(frozen=True, slots=True)
class PmcMetadata:
    """The per-version JSON metadata document.

    Attributes:
        pmcid: PMC ID with prefix.
        version: Version number.
        version_id: ``<pmcid>.<version>``.
        pmid: PubMed ID, if any.
        doi: DOI, if any.
        title: Title.
        citation: Journal citation string.
        is_pmc_openaccess: In the PMC Open Access Subset.
        is_manuscript: An author manuscript.
        is_historical_ocr: From the back-scanning project.
        is_retracted: Retracted.
        license_code: The licence code ("CC BY", "TDM", ...), or None.
        xml_url: HTTPS URL of the JATS XML (with its ``md5`` parameter).
        xml_md5: MD5 the bucket publishes for the XML, if given.
        raw: The parsed JSON document.
    """

    pmcid: str
    version: int
    version_id: str
    pmid: str | None
    doi: str | None
    title: str
    citation: str
    is_pmc_openaccess: bool | None
    is_manuscript: bool | None
    is_historical_ocr: bool | None
    is_retracted: bool
    license_code: str | None
    xml_url: str | None
    xml_md5: str | None
    raw: Mapping[str, Any]

    @classmethod
    def from_json(cls, data: bytes) -> PmcMetadata:
        """Parse and validate a metadata document.

        Args:
            data: The JSON bytes.

        Returns:
            The metadata.

        Raises:
            PmcError: If the JSON is malformed or required fields are
                missing or of the wrong type.
        """
        try:
            raw = json.loads(data)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise PmcError(f"metadata is not valid JSON: {exc}") from exc
        if not isinstance(raw, dict):
            raise PmcError("metadata JSON is not an object")

        # Identity fields are required and must be well formed.
        pmcid = normalise_pmcid(_require(raw, "pmcid", str))
        version = _require(raw, "version", int)
        xml_s3 = _optional(raw, "xml_url", str)
        xml_url = s3_to_https(xml_s3) if xml_s3 else None
        return cls(
            pmcid=pmcid,
            version=version,
            version_id=f"{pmcid}.{version}",
            pmid=_identifier(raw.get("pmid")),
            doi=_identifier(raw.get("doi")),
            title=_optional(raw, "title", str) or "",
            citation=_optional(raw, "citation", str) or "",
            is_pmc_openaccess=_optional(raw, "is_pmc_openaccess", bool),
            is_manuscript=_optional(raw, "is_manuscript", bool),
            is_historical_ocr=_optional(raw, "is_historical_ocr", bool),
            is_retracted=bool(_optional(raw, "is_retracted", bool)),
            license_code=_optional(raw, "license_code", str) or None,
            xml_url=xml_url,
            xml_md5=_md5_param(xml_url) if xml_url else None,
            raw=raw,
        )


def _require[T](raw: Mapping[str, Any], key: str, kind: type[T]) -> T:
    """Read a required field of a given type.

    Args:
        raw: The JSON object.
        key: Field name.
        kind: Expected Python type.

    Returns:
        The value.

    Raises:
        PmcError: If it is missing or of another type.
    """
    value = raw.get(key)
    # bool is a subclass of int: never accept it where an int is expected.
    if not isinstance(value, kind) or (kind is int and isinstance(value, bool)):
        raise PmcError(f"metadata field {key!r} must be {kind.__name__}, got {value!r}")
    return value


def _optional[T](raw: Mapping[str, Any], key: str, kind: type[T]) -> T | None:
    """Read an optional field of a given type.

    Args:
        raw: The JSON object.
        key: Field name.
        kind: Expected Python type.

    Returns:
        The value, or None when it is missing or null.

    Raises:
        PmcError: If it is present with another type.
    """
    value = raw.get(key)
    if value is None:
        return None
    if not isinstance(value, kind):
        raise PmcError(f"metadata field {key!r} must be {kind.__name__}, got {value!r}")
    return value


def _identifier(value: object) -> str | None:
    """Turn an identifier given as a string or a number into a string.

    Args:
        value: The JSON value (PMC gives PMIDs as numbers).

    Returns:
        The stripped string, or None for null or empty values.
    """
    if value is None or isinstance(value, bool):
        return None
    text = str(value).strip()
    return text or None


def s3_to_https(url: str) -> str:
    """Convert an ``s3://pmc-oa-opendata/...`` URL into its public HTTPS URL.

    Args:
        url: An S3 URL from the metadata (or an HTTPS URL, returned as is).

    Returns:
        ``https://pmc-oa-opendata.s3.amazonaws.com/<key>[?query]``.

    Raises:
        PmcError: If the URL points outside the bucket.
    """
    parts = urlsplit(url)
    if parts.scheme == "https" and parts.netloc == f"{BUCKET}.s3.amazonaws.com":
        return url
    if parts.scheme != "s3" or parts.netloc != BUCKET:
        raise PmcError(f"URL is not in the {BUCKET} bucket: {url!r}")
    query = f"?{parts.query}" if parts.query else ""
    return f"{BASE_URL}{parts.path}{query}"


def _md5_param(url: str) -> str | None:
    """Return the ``md5`` query parameter of a bucket URL.

    Args:
        url: The URL.

    Returns:
        The lower-cased hex digest, or None.
    """
    values = parse_qs(urlsplit(url).query).get("md5")
    return values[0].lower() if values else None


def parse_version_listing(data: bytes, pmcid: str) -> list[str]:
    """Extract version prefixes from a ListObjectsV2 response.

    Args:
        data: The XML response (parsed with defusedxml).
        pmcid: The PMC ID that was listed.

    Returns:
        Version IDs such as ``PMC11370360.1``, sorted by version number.

    Raises:
        PmcError: If the XML is malformed or the listing was truncated.
    """
    try:
        root = ElementTree.fromstring(data)
    except ElementTree.ParseError as exc:
        raise PmcError(f"bucket listing is not valid XML: {exc}") from exc
    if (root.findtext(f"{_S3_NAMESPACE}IsTruncated") or "false").strip() == "true":
        raise PmcError(f"bucket listing for {pmcid} was truncated")

    # Keep only prefixes of exactly this PMC ID (PMC1. must not match PMC12.).
    versions: list[tuple[int, str]] = []
    for element in root.iter(f"{_S3_NAMESPACE}Prefix"):
        match = _VERSION_PREFIX.match((element.text or "").strip())
        if match and match.group(1) == pmcid:
            versions.append((int(match.group(2)), f"{pmcid}.{match.group(2)}"))
    return [version_id for _, version_id in sorted(versions)]


class PmcBucket:
    """Read article versions from the PMC Cloud Service bucket."""

    def __init__(self, fetcher: PoliteFetcher, *, base_url: str = BASE_URL) -> None:
        """Create the client.

        Args:
            fetcher: The polite fetcher all requests go through.
            base_url: Bucket URL (overridable for tests).
        """
        self._fetcher = fetcher
        self._base_url = base_url.rstrip("/")

    def listing_url(self, pmcid: str) -> str:
        """URL that lists every version prefix of one PMC ID.

        Args:
            pmcid: PMC ID with prefix.

        Returns:
            The ListObjectsV2 URL.
        """
        query = urlencode({"list-type": "2", "prefix": f"{pmcid}.", "delimiter": "/"})
        return f"{self._base_url}/?{query}"

    def metadata_url(self, version_id: str) -> str:
        """URL of one version's JSON metadata.

        Args:
            version_id: e.g. ``PMC10718527.1``.

        Returns:
            The HTTPS URL.
        """
        return f"{self._base_url}/{version_id}/{version_id}.json"

    def list_versions(self, pmcid: str) -> list[str]:
        """List the versions of an article present in the bucket (always fresh).

        Args:
            pmcid: PMC ID with prefix.

        Returns:
            Version IDs sorted by version number; empty if the article is
            not in the bucket (yet).

        Raises:
            PmcError: For a malformed or truncated listing.
            rbcore.http.FetchError: If the request fails.
        """
        return parse_version_listing(
            self._fetcher.get(self.listing_url(pmcid), use_cache=False), pmcid
        )

    def metadata(self, version_id: str) -> tuple[PmcMetadata, bytes]:
        """Fetch one version's metadata (always fresh).

        Args:
            version_id: e.g. ``PMC10718527.1``.

        Returns:
            The parsed metadata and the raw bytes.

        Raises:
            PmcError: If the document is malformed or describes another version.
            rbcore.http.FetchError: If the request fails.
        """
        data = self._fetcher.get(self.metadata_url(version_id), use_cache=False)
        metadata = PmcMetadata.from_json(data)
        if metadata.version_id != version_id:
            raise PmcError(f"metadata at {version_id} describes {metadata.version_id}")
        return metadata, data

    def article_xml(self, metadata: PmcMetadata) -> bytes:
        """Fetch a version's JATS XML and check it against the published MD5.

        Args:
            metadata: The version's metadata.

        Returns:
            The XML bytes (untrusted; parse only with rbcore.jats).

        Raises:
            PmcError: If the metadata has no XML URL or the MD5 differs.
            rbcore.http.FetchError: If the request fails.
        """
        if metadata.xml_url is None:
            raise PmcError(f"{metadata.version_id} metadata has no xml_url")
        data = self._fetcher.get(metadata.xml_url)
        if _md5_matches(data, metadata.xml_md5):
            return data

        # A bad cached copy is discarded and fetched once more before giving up.
        cached = self._fetcher.cache_path(metadata.xml_url)
        if cached is not None:
            cached.unlink(missing_ok=True)
        data = self._fetcher.get(metadata.xml_url)
        if not _md5_matches(data, metadata.xml_md5):
            raise PmcError(f"{metadata.version_id} XML does not match its MD5 {metadata.xml_md5}")
        return data


def _md5_matches(data: bytes, expected: str | None) -> bool:
    """Check bytes against the MD5 the bucket publishes.

    MD5 is used only because it is the digest the bucket publishes; it is an
    integrity check against accidental corruption, not a security control.

    Args:
        data: The downloaded bytes.
        expected: The published hex digest, or None when none is published.

    Returns:
        True if no digest is published or the digests match.
    """
    if expected is None:
        return True
    return hashlib.md5(data, usedforsecurity=False).hexdigest() == expected
