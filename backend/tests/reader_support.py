"""Test support for the reader API: ingest recorded and synthetic articles.

Recorded articles (eLife and PLOS, CC BY) come through the real pipeline from
the recorded bucket. Synthetic articles are minimal JATS documents built here,
served by the same fake bucket, and named synthetic in their titles and IDs
(PMC IDs from 900000000 up, DOIs under the never-registered 10.9999 prefix).
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from xml.sax.saxutils import escape

from support import RecordedBucket

from rb_backend.ingestion.pipeline import IngestReport, ingest_pmc_article
from rb_backend.ingestion.pmc import PmcBucket

NOW = datetime(2026, 10, 13, 12, 0, tzinfo=UTC)
TODAY = date(2026, 10, 13)
CC_BY = "http://creativecommons.org/licenses/by/4.0/"
CC_BY_ND = "http://creativecommons.org/licenses/by-nd/4.0/"


def ingest(pmcid: str, bucket: PmcBucket) -> IngestReport:
    """Ingest an article from the fake bucket with fixed clocks.

    Args:
        pmcid: The PMC ID.
        bucket: The bucket client on the fake host.

    Returns:
        The ingestion report.
    """
    return ingest_pmc_article(pmcid, bucket=bucket, now=NOW, today=TODAY)


def synthetic_article_jats(
    *,
    pmcid: str,
    title: str,
    abstract: str,
    paragraphs: list[str],
    year: int,
    licence_url: str = CC_BY,
) -> bytes:
    """A minimal synthetic JATS article (not a real paper).

    Args:
        pmcid: Its synthetic PMC ID.
        title: Its title.
        abstract: One abstract paragraph.
        paragraphs: Body paragraphs.
        year: Publication year.
        licence_url: The licence URI in its permissions.

    Returns:
        The XML bytes.
    """
    body = "".join(f"<p>{escape(text)}</p>" for text in paragraphs)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<article xmlns:ali="http://www.niso.org/schemas/ali/1.0/" article-type="research-article">'
        "<front><journal-meta><journal-title-group>"
        "<journal-title>Synthetic Journal of Testing</journal-title>"
        "</journal-title-group></journal-meta><article-meta>"
        f'<article-id pub-id-type="pmcid">{pmcid}</article-id>'
        f"<title-group><article-title>{escape(title)}</article-title></title-group>"
        '<contrib-group><contrib contrib-type="author"><name><surname>Synthetic</surname>'
        "<given-names>Author</given-names></name></contrib></contrib-group>"
        f'<pub-date pub-type="epub"><year>{year}</year><month>05</month><day>01</day></pub-date>'
        "<permissions><copyright-statement>Synthetic copyright statement</copyright-statement>"
        f"<license><ali:license_ref>{licence_url}</ali:license_ref></license></permissions>"
        f"<abstract><p>{escape(abstract)}</p></abstract>"
        f"</article-meta></front><body><sec><title>Introduction</title>{body}</sec></body>"
        "</article>"
    ).encode()


def serve_synthetic_article(
    recorded: RecordedBucket,
    *,
    pmcid: str,
    title: str,
    abstract: str = "A synthetic abstract about mitochondria and sleep.",
    paragraphs: list[str] | None = None,
    year: int = 2024,
    licence_code: str = "CC BY",
    licence_url: str = CC_BY,
    is_retracted: bool = False,
) -> None:
    """Serve a synthetic article (listing, metadata, XML) from the fake bucket.

    Args:
        recorded: The fake bucket host.
        pmcid: A synthetic PMC ID (900000000 or above).
        title: Its title (should say "synthetic").
        abstract: Its abstract.
        paragraphs: Body paragraphs.
        year: Publication year.
        licence_code: The PMC ``license_code``.
        licence_url: The JATS licence URI (keep it consistent with the code).
        is_retracted: The PMC retraction flag.
    """
    version_id = f"{pmcid}.1"
    xml = synthetic_article_jats(
        pmcid=pmcid,
        title=title,
        abstract=abstract,
        paragraphs=paragraphs or ["Synthetic body paragraph (not real text)."],
        year=year,
        licence_url=licence_url,
    )
    digest = recorded.add_xml(version_id, xml)
    recorded.add_listing(pmcid, [1])
    number = pmcid.removeprefix("PMC")
    recorded.add_metadata(
        {
            "pmcid": pmcid,
            "version": 1,
            "pmid": int(number),
            "doi": f"10.9999/synthetic.{number}",
            "title": title,
            "citation": "Synthetic. 2026.",
            "is_pmc_openaccess": True,
            "is_manuscript": False,
            "is_historical_ocr": False,
            "is_retracted": is_retracted,
            "license_code": licence_code,
            "xml_url": f"s3://pmc-oa-opendata/{version_id}/{version_id}.xml?md5={digest}",
        }
    )
