"""The PMC Cloud Service (``pmc-oa-opendata`` S3 bucket) over HTTPS.

The bucket is world-readable and needs no account. Each article version has
``PMC<id>.<v>/PMC<id>.<v>.json`` (metadata, including the authoritative
per-article ``license_code``, decisions.md §1.1 addendum) and
``PMC<id>.<v>.xml`` (JATS). Bucket terms: acknowledge NLM as the source,
imply no endorsement, honour ``is_retracted``, and treat ``TDM`` (author
manuscripts) as never-ingest.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit

from rbbench.sources.safexml import parse_untrusted_xml
from rbcore.http import PoliteFetcher

PMC_S3_HTTPS = "https://pmc-oa-opendata.s3.amazonaws.com"
_S3_NS = "{http://s3.amazonaws.com/doc/2006-03-01/}"


class PmcError(RuntimeError):
    """Raised when the PMC Cloud Service returns something unusable."""


@dataclass(frozen=True, slots=True)
class PmcRecord:
    """The per-article-version metadata JSON from the PMC Cloud Service.

    Attributes:
        pmcid: PMC ID with prefix, e.g. "PMC7853715".
        version: Article version number.
        pmid: PubMed ID, if any.
        doi: DOI, if any.
        title: Article title.
        citation: Citation string.
        is_pmc_openaccess: Whether the article is in the PMC Open Access Subset.
        is_manuscript: Whether it is an author manuscript.
        is_retracted: Whether PMC marks it retracted.
        license_code: The raw ``license_code`` (e.g. "CC BY", "TDM").
        xml_url: HTTPS URL of the JATS file.
        xml_md5: MD5 of the JATS file, from the ``md5`` query of ``xml_url``.
        json_url: The HTTPS URL this record was read from.
    """

    pmcid: str
    version: int
    pmid: str | None
    doi: str | None
    title: str
    citation: str
    is_pmc_openaccess: bool
    is_manuscript: bool
    is_retracted: bool
    license_code: str | None
    xml_url: str
    xml_md5: str | None
    json_url: str

    @property
    def key(self) -> str:
        """The version-qualified ID used as the benchmark's paper key, e.g. "PMC7853715.1"."""
        return f"{self.pmcid}.{self.version}"


def json_url(pmcid: str, version: int) -> str:
    """Return the HTTPS URL of an article version's metadata JSON.

    Args:
        pmcid: PMC ID with prefix.
        version: Version number.

    Returns:
        The URL.
    """
    key = f"{pmcid}.{version}"
    return f"{PMC_S3_HTTPS}/{key}/{key}.json"


def s3_to_https(s3_url: str) -> tuple[str, str | None]:
    """Convert an ``s3://pmc-oa-opendata/...`` URL to HTTPS and extract its MD5.

    Args:
        s3_url: A URL as given in the metadata JSON, e.g.
            ``s3://pmc-oa-opendata/PMC1.1/PMC1.1.xml?md5=abc``.

    Returns:
        ``(https_url, md5)``; md5 is None when absent.

    Raises:
        PmcError: If the URL is not in the ``pmc-oa-opendata`` bucket.
    """
    parts = urlsplit(s3_url)
    if parts.scheme != "s3" or parts.netloc != "pmc-oa-opendata" or not parts.path:
        raise PmcError(f"unexpected object URL {s3_url!r}")
    md5 = parse_qs(parts.query).get("md5", [None])[0]
    return f"{PMC_S3_HTTPS}{parts.path}", md5


def latest_version(fetcher: PoliteFetcher, pmcid: str) -> int:
    """Find the newest version of an article in the bucket.

    Args:
        fetcher: The polite fetcher.
        pmcid: PMC ID with prefix.

    Returns:
        The highest version number listed.

    Raises:
        PmcError: If the article has no version in the bucket.
    """
    query = urlencode({"list-type": "2", "prefix": f"{pmcid}.", "delimiter": "/"})
    root = parse_untrusted_xml(fetcher.get(f"{PMC_S3_HTTPS}/?{query}"))
    versions: list[int] = []
    # Common prefixes look like "PMC7853715.1/"; anything else is ignored.
    for prefix in root.iter(f"{_S3_NS}Prefix"):
        text = (prefix.text or "").strip()
        head, _, tail = text.rstrip("/").rpartition(".")
        if head == pmcid and tail.isdigit() and text.endswith("/"):
            versions.append(int(tail))
    if not versions:
        raise PmcError(f"{pmcid} has no version in the PMC Cloud Service")
    return max(versions)


def parse_record(data: bytes, url: str) -> PmcRecord:
    """Parse a metadata JSON document.

    Args:
        data: The JSON bytes.
        url: Where it came from (recorded as evidence).

    Returns:
        The record.

    Raises:
        PmcError: If the JSON is not an object or lacks required fields.
    """
    # The document is untrusted: it must be a JSON object with the fields we rely on.
    try:
        raw: Any = json.loads(data)
    except json.JSONDecodeError as exc:
        raise PmcError(f"{url}: invalid JSON") from exc
    if not isinstance(raw, dict) or "pmcid" not in raw or "xml_url" not in raw:
        raise PmcError(f"{url}: not a PMC metadata record")
    # The JATS location is an s3:// URL with its MD5; fetch it over HTTPS and check it.
    xml_url, xml_md5 = s3_to_https(str(raw["xml_url"]))
    # Absent flags read as false; a missing licence stays None so the gate refuses it.
    return PmcRecord(
        pmcid=str(raw["pmcid"]),
        version=int(raw.get("version") or 1),
        pmid=str(raw["pmid"]) if raw.get("pmid") else None,
        doi=str(raw["doi"]) if raw.get("doi") else None,
        title=str(raw.get("title") or ""),
        citation=str(raw.get("citation") or ""),
        is_pmc_openaccess=bool(raw.get("is_pmc_openaccess")),
        is_manuscript=bool(raw.get("is_manuscript")),
        is_retracted=bool(raw.get("is_retracted")),
        license_code=str(raw["license_code"]) if raw.get("license_code") else None,
        xml_url=xml_url,
        xml_md5=xml_md5,
        json_url=url,
    )


def fetch_record(fetcher: PoliteFetcher, pmcid: str, version: int) -> PmcRecord:
    """Download and parse an article version's metadata JSON.

    Args:
        fetcher: The polite fetcher.
        pmcid: PMC ID with prefix.
        version: Version number.

    Returns:
        The record.
    """
    url = json_url(pmcid, version)
    return parse_record(fetcher.get(url), url)


def fetch_jats(fetcher: PoliteFetcher, record: PmcRecord) -> bytes:
    """Download an article version's JATS and verify its MD5.

    Args:
        fetcher: The polite fetcher.
        record: The article's metadata.

    Returns:
        The JATS bytes.

    Raises:
        PmcError: If the MD5 does not match the one in the metadata.
    """
    data = fetcher.get(record.xml_url)
    # MD5 here is an integrity check against the bucket's own manifest, not security.
    if record.xml_md5 is not None:
        digest = hashlib.md5(data, usedforsecurity=False).hexdigest()
        if digest != record.xml_md5:
            raise PmcError(f"{record.xml_url}: MD5 {digest} does not match {record.xml_md5}")
    return data


def retrieved_on(fetcher: PoliteFetcher, url: str) -> date:
    """Return the date a URL's cached response was first retrieved (UTC).

    Args:
        fetcher: The fetcher whose cache holds the response.
        url: The URL.

    Returns:
        The cache file's modification date, or today when nothing is cached.
        It is a file-system date: copying the cache without preserving
        modification times, or rebuilding it, changes it although the
        evidence did not change (documented in benchmark/selection/README.md).
    """
    path = fetcher.cache_path(url)
    if path is not None and path.is_file():
        return datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).date()
    return datetime.now(UTC).date()
