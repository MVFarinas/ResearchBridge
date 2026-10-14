"""GET /api/v1/papers/<key>/: the paper page's content, behind the licence gate."""

from __future__ import annotations

from typing import Any

import pytest
from reader_support import CC_BY_ND, ingest, serve_synthetic_article
from rest_framework.test import APIClient
from support import RecordedBucket

from rb_backend.annotations.models import Annotation, Provenance
from rb_backend.corpus.models import Figure, GateStatus, Paper, Paragraph
from rb_backend.ingestion.pmc import PmcBucket

pytestmark = pytest.mark.django_db

PLOS = "PMC11964404"
ELIFE = "PMC10718527"


def get(api: APIClient, key: str) -> Any:
    """GET a paper and return the response."""
    return api.get(f"/api/v1/papers/{key}/")


def test_detail_of_a_recorded_cc_by_paper(api: APIClient, bucket: PmcBucket) -> None:
    """The PLOS article comes back with metadata, licence, permissions and links."""
    ingest(PLOS, bucket)
    response = get(api, PLOS)
    assert response.status_code == 200
    data = response.json()
    assert data["key"] == PLOS
    assert data["title"] == "Predatory journals: What can we do to protect their prey?"
    assert data["identifiers"]["doi"] == "10.1371/journal.pmed.1004542"
    assert data["authors"][0]["name"]
    assert data["licence"]["label"] == "CC BY 4.0"
    assert data["licence"]["url"] == "https://creativecommons.org/licenses/by/4.0/"
    assert data["licence"]["attribution_required"] is True
    assert data["permissions"] == {
        "can_display": True,
        "can_rewrite": True,
        "output_licence": {
            "label": "CC BY 4.0",
            "url": "https://creativecommons.org/licenses/by/4.0/",
        },
    }
    assert data["links"]["doi"] == "https://doi.org/10.1371/journal.pmed.1004542"
    assert data["links"]["scholar"].startswith("https://scholar.google.com/scholar?q=Predatory")
    assert data["links"]["source"] == f"https://pmc.ncbi.nlm.nih.gov/articles/{PLOS}/"


def test_detail_carries_attribution_and_nlm_acknowledgement(
    api: APIClient, bucket: PmcBucket
) -> None:
    """Every paper page gets its copyright line, the changes note and the NLM credit."""
    ingest(PLOS, bucket)
    attribution = get(api, PLOS).json()["attribution"]
    assert attribution["copyright"] == ["© 2025 Laine et al"]
    assert "converted from the publisher's JATS XML" in attribution["changes"]
    acknowledgement = attribution["source"]["acknowledgement"]
    assert "National Library of Medicine" in acknowledgement
    assert "accessed 2026-10-13" in acknowledgement
    assert "does not imply endorsement" in acknowledgement


def test_sections_and_paragraphs_in_document_order(api: APIClient, bucket: PmcBucket) -> None:
    """Sections are flat with parent and depth; paragraphs keep their stable IDs."""
    ingest(PLOS, bucket)
    data = get(api, PLOS).json()
    sections = data["sections"]
    stored = list(
        Paragraph.objects.filter(version__paper__pmcid=PLOS)
        .order_by("position")
        .values_list("stable_id", flat=True)
    )
    returned = [p["id"] for s in sections for p in s["paragraphs"]]
    assert returned == stored
    # Children come after their parent and sit one level deeper.
    by_id = {s["id"]: s for s in sections}
    for section in sections:
        if section["parent"] is not None:
            assert by_id[section["parent"]]["depth"] == section["depth"] - 1
    assert data["withheld"] == {"paragraphs": 0, "figures": 0}


def test_generated_content_is_reported_honestly(api: APIClient, bucket: PmcBucket) -> None:
    """No rewrite, summary or annotation exists yet, and the API says so."""
    ingest(PLOS, bucket)
    data = get(api, PLOS).json()
    assert data["rewrite"]["status"] == "not_generated"
    assert data["summary"]["status"] == "not_generated"
    assert data["annotations"] == []


def test_no_derivatives_paper_is_display_only(
    api: APIClient, recorded: RecordedBucket, bucket: PmcBucket
) -> None:
    """A CC BY-ND paper is shown but marked not rewriteable, with no output licence."""
    serve_synthetic_article(
        recorded,
        pmcid="PMC900000201",
        title="Synthetic no-derivatives article",
        licence_code="CC BY-ND",
        licence_url=CC_BY_ND,
    )
    ingest("PMC900000201", bucket)
    data = get(api, "PMC900000201").json()
    assert data["licence"]["no_derivatives"] is True
    assert data["permissions"]["can_rewrite"] is False
    assert data["permissions"]["output_licence"] is None
    assert data["rewrite"]["status"] == "not_permitted"


def test_retracted_paper_is_shown_with_its_retraction(
    api: APIClient, recorded: RecordedBucket, bucket: PmcBucket
) -> None:
    """A retracted paper stays readable, flagged, and is never rewritten."""
    serve_synthetic_article(
        recorded, pmcid="PMC900000202", title="Synthetic retracted article", is_retracted=True
    )
    ingest("PMC900000202", bucket)
    data = get(api, "PMC900000202").json()
    assert data["retraction"]["is_retracted"] is True
    assert data["retraction"]["source"] == "pmc:is_retracted"
    assert data["permissions"]["can_rewrite"] is False
    assert data["rewrite"]["status"] == "not_permitted"
    assert "retracted" in data["rewrite"]["reason"]


@pytest.mark.parametrize("key", ["PMC13641010", "PMC999999999", "not-a-key", "rb-999999"])
def test_unknown_or_gated_papers_are_404(api: APIClient, bucket: PmcBucket, key: str) -> None:
    """A rejected (TDM) paper is indistinguishable from one that does not exist."""
    ingest("PMC13641010", bucket)
    assert Paper.objects.filter(pmcid="PMC13641010").exists()
    assert get(api, key).status_code == 404


def test_internal_keys_resolve(api: APIClient, bucket: PmcBucket) -> None:
    """``rb-<id>`` keys reach the same paper (for papers without a PMC ID later)."""
    ingest(PLOS, bucket)
    paper = Paper.objects.get(pmcid=PLOS)
    assert get(api, f"rb-{paper.pk}").json()["key"] == PLOS


def test_withheld_figures_are_counted_not_shown(api: APIClient, bucket: PmcBucket) -> None:
    """A figure sent to licence review is left out and counted."""
    ingest(ELIFE, bucket)
    figure = Figure.objects.get(version__paper__pmcid=ELIFE)
    shown_before = [f["id"] for s in get(api, ELIFE).json()["sections"] for f in s["figures"]]
    assert shown_before == [figure.stable_id]
    # Simulate the gate sending the figure to review (its own licence unclear).
    Figure.objects.filter(pk=figure.pk).update(
        gate_status=GateStatus.REVIEW,
        can_display=False,
        can_rewrite=False,
        output_licence_family="",
        output_licence_version="",
    )
    data = get(api, ELIFE).json()
    shown = [f["id"] for s in data["sections"] for f in s["figures"]]
    assert figure.stable_id not in shown
    assert data["withheld"]["figures"] == 1


def _synthetic_annotation(paragraph: Paragraph, provenance: Provenance) -> Annotation:
    """A synthetic annotation on the first word of a paragraph (not real content)."""
    word = paragraph.text.split()[0]
    annotation = Annotation(
        paper_version=paragraph.version,
        paragraph=paragraph,
        target={
            "source": paragraph.version.source_version_id,
            "selector": [
                {"type": "TextQuoteSelector", "exact": word},
                {"type": "TextPositionSelector", "start": 0, "end": len(word)},
            ],
        },
        body={
            "type": "TextualBody",
            "value": "Synthetic test explanation (not real).",
            "format": "text/plain",
        },
        provenance=provenance,
        model="synthetic-model" if provenance != Provenance.HUMAN else "",
        prompt_version="synthetic-v0" if provenance != Provenance.HUMAN else "",
    )
    annotation.save()
    return annotation


def test_annotations_are_returned_in_w3c_shape(api: APIClient, bucket: PmcBucket) -> None:
    """Stored annotations come back with selectors, provenance and the disclaimer flag."""
    ingest(PLOS, bucket)
    paragraph = Paragraph.objects.filter(version__paper__pmcid=PLOS).order_by("position").first()
    assert paragraph is not None
    annotation = _synthetic_annotation(paragraph, Provenance.LLM)
    [returned] = get(api, PLOS).json()["annotations"]
    assert returned["id"] == f"urn:uuid:{annotation.id}"
    assert returned["type"] == "Annotation"
    assert returned["paragraph_id"] == paragraph.stable_id
    assert returned["provenance"] == "llm"
    assert returned["needs_disclaimer"] is True
    assert returned["target"]["selector"][1] == {
        "type": "TextPositionSelector",
        "start": 0,
        "end": len(paragraph.text.split()[0]),
    }


def test_drifted_annotations_are_withheld(api: APIClient, bucket: PmcBucket) -> None:
    """An annotation whose paragraph text changed is not served until re-anchored."""
    ingest(PLOS, bucket)
    paragraph = Paragraph.objects.filter(version__paper__pmcid=PLOS).order_by("position").first()
    assert paragraph is not None
    annotation = _synthetic_annotation(paragraph, Provenance.HUMAN)
    Annotation.objects.filter(pk=annotation.pk).update(paragraph_text_sha256="0" * 64)
    assert get(api, PLOS).json()["annotations"] == []
