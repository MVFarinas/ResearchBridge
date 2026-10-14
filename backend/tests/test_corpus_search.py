"""The full-text search index and corpus search, always behind the licence gate."""

from __future__ import annotations

import pytest
from django.core.management import call_command
from reader_support import CC_BY_ND, ingest, serve_synthetic_article
from support import RecordedBucket

from rb_backend.corpus.models import GateStatus, PaperVersion, SearchDocument
from rb_backend.corpus.search_index import author_names, published_year
from rb_backend.discovery.corpus_search import (
    HIGHLIGHT_START,
    HIGHLIGHT_STOP,
    CorpusSearch,
    search_corpus,
)
from rb_backend.ingestion.pmc import PmcBucket

pytestmark = pytest.mark.django_db


@pytest.fixture
def corpus(recorded: RecordedBucket, bucket: PmcBucket) -> None:
    """Three synthetic articles: CC BY 2020, CC BY 2024, CC BY-ND 2022, plus a TDM manuscript."""
    serve_synthetic_article(
        recorded,
        pmcid="PMC900000101",
        title="Synthetic study of sleep in teenagers",
        abstract="Synthetic abstract: sleep duration and school performance in adolescents.",
        year=2020,
    )
    serve_synthetic_article(
        recorded,
        pmcid="PMC900000102",
        title="Synthetic trial of vitamin D and sleep",
        abstract="Synthetic abstract: vitamin D supplementation did not change sleep quality.",
        year=2024,
    )
    serve_synthetic_article(
        recorded,
        pmcid="PMC900000103",
        title="Synthetic review of sleep hygiene",
        abstract="Synthetic abstract: a review of sleep hygiene advice.",
        year=2022,
        licence_code="CC BY-ND",
        licence_url=CC_BY_ND,
    )
    for pmcid in ("PMC900000101", "PMC900000102", "PMC900000103", "PMC13641010"):
        ingest(pmcid, bucket)


def keys(search: CorpusSearch) -> list[str]:
    """PMC IDs of a search's hits, in order."""
    return [hit.document.version.paper.pmcid or "" for hit in search_corpus(search).hits]


def test_gate_evaluation_builds_the_search_document(corpus: None) -> None:
    """Ingestion (through the gate) indexes title, abstract, authors, journal and year."""
    document = SearchDocument.objects.get(version__paper__pmcid="PMC900000102")
    assert document.title == "Synthetic trial of vitamin D and sleep"
    assert "did not change sleep quality" in document.abstract
    assert document.authors == "Author Synthetic"
    assert document.journal == "Synthetic Journal of Testing"
    assert document.published_year == 2024
    assert document.document is not None


def test_rejected_papers_are_never_found(corpus: None) -> None:
    """The TDM manuscript is indexed (title only) but the gated query never returns it."""
    rejected = PaperVersion.objects.get(paper__pmcid="PMC13641010")
    assert rejected.gate_status == GateStatus.REJECTED
    title_word = rejected.title.split()[0]
    assert "PMC13641010" not in keys(CorpusSearch(query=title_word))


def test_search_ranks_title_matches_and_highlights(corpus: None) -> None:
    """All three sleep papers match; the snippet marks the matched words."""
    page = search_corpus(CorpusSearch(query="sleep"))
    assert page.total == 3
    snippet = page.hits[0].snippet
    assert f"{HIGHLIGHT_START}sleep{HIGHLIGHT_STOP}" in snippet.lower()


def test_websearch_syntax(corpus: None) -> None:
    """Quoted phrases and exclusions follow websearch_to_tsquery."""
    assert keys(CorpusSearch(query='"vitamin D"')) == ["PMC900000102"]
    assert sorted(keys(CorpusSearch(query="sleep -vitamin"))) == ["PMC900000101", "PMC900000103"]


def test_year_filters(corpus: None) -> None:
    """Year bounds are inclusive."""
    assert sorted(keys(CorpusSearch(query="sleep", year_from=2022))) == [
        "PMC900000102",
        "PMC900000103",
    ]
    assert keys(CorpusSearch(query="sleep", year_to=2020)) == ["PMC900000101"]


def test_availability_filter_and_flags(corpus: None) -> None:
    """The ND paper is display-only; the CC BY papers may be rewritten."""
    only = keys(CorpusSearch(query="sleep", availability="original_annotations_only"))
    assert only == ["PMC900000103"]
    plain = keys(CorpusSearch(query="sleep", availability="plain_english_available"))
    assert sorted(plain) == ["PMC900000101", "PMC900000102"]
    flags = {
        hit.document.version.paper.pmcid: hit.can_rewrite
        for hit in search_corpus(CorpusSearch(query="sleep")).hits
    }
    assert flags == {"PMC900000101": True, "PMC900000102": True, "PMC900000103": False}


def test_sort_by_date(corpus: None) -> None:
    """Newest and oldest orders follow the publication date."""
    assert keys(CorpusSearch(query="sleep", sort="newest")) == [
        "PMC900000102",
        "PMC900000103",
        "PMC900000101",
    ]
    assert keys(CorpusSearch(query="sleep", sort="oldest")) == [
        "PMC900000101",
        "PMC900000103",
        "PMC900000102",
    ]


def test_pagination(corpus: None) -> None:
    """Pages slice the ordered results; the total covers all pages."""
    first = search_corpus(CorpusSearch(query="sleep", sort="newest", per_page=2))
    second = search_corpus(CorpusSearch(query="sleep", sort="newest", per_page=2, page=2))
    assert first.total == second.total == 3
    assert [h.document.version.paper.pmcid for h in second.hits] == ["PMC900000101"]


def test_rebuild_command_recreates_documents(corpus: None) -> None:
    """rebuild_search_index restores documents for every current version."""
    SearchDocument.objects.all().delete()
    call_command("rebuild_search_index")
    assert SearchDocument.objects.count() == 4
    assert keys(CorpusSearch(query="hygiene")) == ["PMC900000103"]


def test_recorded_plos_article_is_searchable(bucket: PmcBucket) -> None:
    """The real PLOS Medicine article is found by words from its title and abstract."""
    ingest("PMC11964404", bucket)
    assert keys(CorpusSearch(query="predatory journals")) == ["PMC11964404"]


@pytest.mark.parametrize(
    ("value", "expected"), [("2024-05-01", 2024), ("2019", 2019), ("", None), ("May", None)]
)
def test_published_year(value: str, expected: int | None) -> None:
    """Years come from ISO dates of any precision."""
    assert published_year(value) == expected


def test_author_names_skip_malformed_entries() -> None:
    """Names come from name or collab; other shapes are ignored."""
    authors = [{"name": "A B"}, {"collab": "Group C"}, {"name": ""}, "junk", {"orcid": "x"}]
    assert author_names(authors) == ["A B", "Group C"]
    assert author_names("not a list") == []
