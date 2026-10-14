"""The PMC Cloud Service client, against recorded responses."""

from __future__ import annotations

import json

import httpx
import pytest
from support import PMC_FIXTURES, RecordedBucket

from rb_backend.ingestion.pmc import (
    BASE_URL,
    PmcBucket,
    PmcError,
    PmcMetadata,
    normalise_pmcid,
    parse_version_listing,
    s3_to_https,
)
from rb_backend.ingestion.runtime import build_request_fetcher
from rbcore.http import FetchError, PoliteFetcher


def test_metadata_parses_a_recorded_document() -> None:
    """Every field the gate and pipeline use is read with the right type."""
    # Identity fields of the recorded eLife article.
    metadata = PmcMetadata.from_json((PMC_FIXTURES / "PMC10718527.1.json").read_bytes())
    assert (metadata.pmcid, metadata.version, metadata.version_id) == (
        "PMC10718527",
        1,
        "PMC10718527.1",
    )
    assert metadata.pmid == "38088194"  # a JSON number in the source
    assert metadata.doi == "10.7554/eLife.93719"

    # The flags the gate and the pipeline act on, and the MD5-carrying XML URL.
    assert metadata.license_code == "CC BY"
    assert metadata.is_retracted is False
    assert metadata.is_manuscript is False
    assert metadata.xml_url == (
        f"{BASE_URL}/PMC10718527.1/PMC10718527.1.xml?md5=cac06beeb774deb26c2cb3b1ea0f5c60"
    )
    assert metadata.xml_md5 == "cac06beeb774deb26c2cb3b1ea0f5c60"


def test_tdm_manuscript_metadata() -> None:
    """The recorded author manuscript carries the TDM code."""
    metadata = PmcMetadata.from_json((PMC_FIXTURES / "PMC13641010.1.json").read_bytes())
    assert metadata.license_code == "TDM"
    assert metadata.is_manuscript is True
    assert metadata.is_pmc_openaccess is False


@pytest.mark.parametrize(
    ("document", "message"),
    [
        (b"not json", "not valid JSON"),
        (b"[]", "not an object"),
        (b'{"pmcid": "PMC1"}', "'version' must be int"),
        (b'{"pmcid": "PMC1", "version": true}', "'version' must be int"),
        (b'{"pmcid": "nope", "version": 1}', "not a PMC ID"),
        (b'{"pmcid": "PMC1", "version": 1, "is_retracted": "no"}', "'is_retracted' must be bool"),
        (
            b'{"pmcid": "PMC1", "version": 1, "xml_url": "s3://other-bucket/x.xml"}',
            "not in the pmc-oa-opendata bucket",
        ),
    ],
)
def test_malformed_metadata_is_refused(document: bytes, message: str) -> None:
    """Untrusted metadata with missing or mistyped fields raises instead of guessing."""
    with pytest.raises(PmcError, match=message):
        PmcMetadata.from_json(document)


def test_missing_licence_code_is_none() -> None:
    """An empty or absent code is recorded as no evidence (synthetic document)."""
    metadata = PmcMetadata.from_json(b'{"pmcid": "PMC1", "version": 1, "license_code": ""}')
    assert metadata.license_code is None
    assert metadata.xml_url is None


@pytest.mark.parametrize(
    ("value", "expected"), [("PMC123", "PMC123"), ("pmc123", "PMC123"), (" 123 ", "PMC123")]
)
def test_normalise_pmcid(value: str, expected: str) -> None:
    """PMC IDs are accepted with or without their prefix."""
    assert normalise_pmcid(value) == expected


def test_normalise_pmcid_rejects_other_identifiers() -> None:
    """DOIs and PMIDs-with-prefixes are not PMC IDs."""
    with pytest.raises(PmcError):
        normalise_pmcid("10.7554/eLife.93719")


def test_s3_to_https() -> None:
    """S3 URLs map onto the public HTTPS endpoint, keeping the md5 parameter."""
    assert s3_to_https("s3://pmc-oa-opendata/PMC1.1/PMC1.1.xml?md5=ab") == (
        f"{BASE_URL}/PMC1.1/PMC1.1.xml?md5=ab"
    )
    assert s3_to_https(f"{BASE_URL}/x") == f"{BASE_URL}/x"


def test_listing_parses_recorded_prefixes() -> None:
    """A recorded listing yields the article's version IDs."""
    data = (PMC_FIXTURES / "PMC10718527-listing.xml").read_bytes()
    assert parse_version_listing(data, "PMC10718527") == ["PMC10718527.1"]


def test_listing_sorts_numerically_and_ignores_other_articles() -> None:
    """Versions sort as numbers; prefixes of other IDs are ignored (synthetic listing)."""
    data = (
        b'<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">'
        b"<IsTruncated>false</IsTruncated>"
        b"<CommonPrefixes><Prefix>PMC1.10/</Prefix></CommonPrefixes>"
        b"<CommonPrefixes><Prefix>PMC1.2/</Prefix></CommonPrefixes>"
        b"<CommonPrefixes><Prefix>PMC12.1/</Prefix></CommonPrefixes>"
        b"</ListBucketResult>"
    )
    assert parse_version_listing(data, "PMC1") == ["PMC1.2", "PMC1.10"]


def test_listing_refuses_truncation_and_entities() -> None:
    """Truncated listings and XML with entity declarations are refused."""
    truncated = (
        b'<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">'
        b"<IsTruncated>true</IsTruncated></ListBucketResult>"
    )
    with pytest.raises(PmcError, match="truncated"):
        parse_version_listing(truncated, "PMC1")
    bomb = b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa">]><x>&a;</x>'
    with pytest.raises(Exception, match=r"(?i)entit"):
        parse_version_listing(bomb, "PMC1")


def test_bucket_lists_fetches_metadata_and_verifies_xml(
    bucket: PmcBucket, recorded: RecordedBucket
) -> None:
    """The client reads listing, metadata and XML from the (recorded) bucket."""
    assert bucket.list_versions("PMC7853715") == ["PMC7853715.1"]
    metadata, raw = bucket.metadata("PMC7853715.1")
    assert json.loads(raw)["license_code"] == "CC BY"
    xml = bucket.article_xml(metadata)
    assert b"<article" in xml
    assert recorded.fetched(".xml") == [metadata.xml_url]


def test_unknown_article_lists_no_versions(bucket: PmcBucket) -> None:
    """An ID not (yet) in the bucket has no versions."""
    assert bucket.list_versions("PMC900000999") == []


def test_metadata_for_another_version_is_refused(
    bucket: PmcBucket, recorded: RecordedBucket
) -> None:
    """A document that describes a different version than requested is an error."""
    recorded.overrides[f"{BASE_URL}/PMC1.2/PMC1.2.json"] = b'{"pmcid": "PMC1", "version": 1}'
    with pytest.raises(PmcError, match=r"describes PMC1\.1"):
        bucket.metadata("PMC1.2")


def test_xml_with_wrong_md5_is_refused_after_one_fresh_attempt(
    bucket: PmcBucket, recorded: RecordedBucket, fetcher: PoliteFetcher
) -> None:
    """A corrupted download is refetched once (cache discarded), then refused."""
    # Arrange: synthetic metadata whose MD5 no served file can match.
    metadata = PmcMetadata.from_json(
        json.dumps(
            {
                "pmcid": "PMC1",
                "version": 1,
                "xml_url": "s3://pmc-oa-opendata/PMC1.1/PMC1.1.xml?md5=00000000000000000000000000000000",
            }
        ).encode()
    )
    assert metadata.xml_url is not None
    recorded.overrides[metadata.xml_url] = b"<synthetic/>"

    # The download is retried once without the cache, then refused.
    with pytest.raises(PmcError, match="does not match its MD5"):
        bucket.article_xml(metadata)
    assert len(recorded.fetched(".xml")) == 2
    cached = fetcher.cache_path(metadata.xml_url)
    assert cached is not None
    assert cached.exists()  # the second (still wrong) copy; the next run retries again


def test_xml_from_a_corrupt_cache_is_replaced(
    bucket: PmcBucket, recorded: RecordedBucket, fetcher: PoliteFetcher
) -> None:
    """A cached copy that no longer matches its MD5 is discarded and fetched fresh."""
    metadata, _ = bucket.metadata("PMC10718527.1")
    assert metadata.xml_url is not None
    cached = fetcher.cache_path(metadata.xml_url)
    assert cached is not None
    cached.parent.mkdir(parents=True, exist_ok=True)
    cached.write_bytes(b"<corrupt-synthetic/>")
    assert b"<article" in bucket.article_xml(metadata)
    assert len(recorded.fetched(".xml")) == 1


def test_forget_xml_deletes_only_the_cached_copy(bucket: PmcBucket, fetcher: PoliteFetcher) -> None:
    """Forgetting an article's XML removes its cache file and reports whether one existed."""
    # Arrange: download (and so cache) one recorded article's XML.
    metadata, _ = bucket.metadata("PMC7853715.1")
    assert metadata.xml_url is not None
    bucket.article_xml(metadata)
    cached = fetcher.cache_path(metadata.xml_url)
    assert cached is not None
    assert cached.is_file()

    # The first call deletes it; a second has nothing left to delete.
    assert bucket.forget_xml(metadata.xml_url) is True
    assert not cached.exists()
    assert bucket.forget_xml(metadata.xml_url) is False


def test_forget_xml_without_a_cache_is_a_no_op() -> None:
    """A fetcher with no cache directory has nothing to forget."""
    with PoliteFetcher(cache_dir=None) as uncached:
        assert PmcBucket(uncached).forget_xml(f"{BASE_URL}/PMC1.1/PMC1.1.xml") is False


def test_request_bucket_fails_fast_on_a_throttled_bucket() -> None:
    """The lookup's bucket fetcher reports a 503 at once: one request, no back-off."""
    requests: list[str] = []
    sleeps: list[float] = []

    def throttle(request: httpx.Request) -> httpx.Response:
        """Answer every request 503 with an hour-long Retry-After (synthetic)."""
        requests.append(str(request.url))
        return httpx.Response(503, headers={"Retry-After": "3600"})

    fetcher = build_request_fetcher(transport=httpx.MockTransport(throttle), sleep=sleeps.append)
    with pytest.raises(FetchError) as caught:
        PmcBucket(fetcher).list_versions("PMC10718527")
    assert caught.value.status == 503
    assert len(requests) == 1
    assert sleeps == []
