"""The paper detail document: everything the paper page renders, in one response.

Built only from the licence-gated access layer: the displayable version, its
displayable sections, paragraphs and figures, and displayable annotations.
It carries the licence, derived permissions and attribution that decisions.md
§1.1 requires on every paper page, the NLM acknowledgement the PMC Cloud
Service terms require, and the honest state of generated content (none yet).
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from rb_backend.annotations.models import Annotation
from rb_backend.corpus import access
from rb_backend.corpus.models import Figure, Paper, PaperVersion, Paragraph, Section, Source
from rb_backend.corpus.search_index import author_names
from rb_backend.discovery.keys import paper_key
from rb_backend.discovery.links import doi_url, scholar_search_url
from rb_backend.generation_status import rewrite_status, summary_status

CHANGES_NOTE = (
    "The original text is shown as published, converted from the publisher's JATS XML to "
    "plain paragraphs. Formatting, equations and table contents are simplified, and figure "
    "images are not shown; see the original for them."
)
NLM_ACKNOWLEDGEMENT = (
    "Full text and metadata from the NIH National Library of Medicine (NLM) PubMed Central "
    "Article Datasets on AWS (https://registry.opendata.aws/ncbi-pmc/), accessed {date}. "
    "Use does not imply endorsement by NLM."
)


def paper_detail(paper: Paper) -> dict[str, Any] | None:
    """Build the detail document of a displayable paper.

    Args:
        paper: A paper (from the gated access layer).

    Returns:
        The JSON-ready document, or None if the paper has no displayable version.
    """
    version = access.displayable_version(paper)
    if version is None:
        return None
    can_rewrite = access.rewriteable_versions().filter(pk=version.pk).exists()
    withheld = access.withheld_parts(version)
    return {
        "key": paper_key(paper),
        "title": version.title,
        "identifiers": {
            "doi": paper.doi,
            "pmcid": paper.pmcid,
            "pmid": paper.pmid,
            "arxiv_id": paper.arxiv_id,
            "source_version": version.source_version_id,
        },
        "authors": _authors(version.authors),
        "journal": version.journal_title,
        "publisher": version.publisher,
        "published_date": version.published_date,
        "article_type": version.article_type,
        "citation": version.citation,
        "retraction": {
            "is_retracted": paper.is_retracted,
            "source": paper.retraction_source or None,
            "date": paper.retraction_date.isoformat() if paper.retraction_date else None,
        },
        "licence": _licence(version),
        "permissions": {
            "can_display": True,
            "can_rewrite": can_rewrite,
            "output_licence": _output_licence(version) if can_rewrite else None,
        },
        "attribution": _attribution(paper, version),
        "declarations": {
            "conflicts_of_interest": _strings(version.coi_statements),
            "funding": _strings(dict(version.funding or {}).get("statements")),
        },
        "sections": _sections(version),
        "withheld": {"paragraphs": withheld.paragraphs, "figures": withheld.figures},
        "annotations": _annotations(version),
        "rewrite": rewrite_status(can_rewrite=can_rewrite, is_retracted=paper.is_retracted),
        "summary": summary_status(),
        "links": {
            "doi": doi_url(paper.doi),
            "scholar": scholar_search_url(title=version.title, doi=paper.doi),
            "source": _source_url(paper, version),
        },
    }


def _licence(version: PaperVersion) -> dict[str, Any]:
    """The decided licence of a version.

    Args:
        version: The version.

    Returns:
        Label, URL, family, version and its conditions.
    """
    licence = version.licence
    return {
        "label": licence.label,
        "url": licence.uri,
        "family": licence.family.value,
        "version": licence.version,
        "attribution_required": version.attribution_required,
        "non_commercial": version.non_commercial,
        "share_alike": version.share_alike,
        "no_derivatives": licence.no_derivatives,
        "decision_source": version.decision_source,
        "decided_at": version.decided_at.isoformat() if version.decided_at else None,
    }


def _output_licence(version: PaperVersion) -> dict[str, Any] | None:
    """The licence a rewrite of the version must carry (share-alike sets it).

    Args:
        version: A rewriteable version.

    Returns:
        ``{"label", "url"}``, or None.
    """
    output = version.output_licence
    return {"label": output.label, "url": output.uri} if output else None


def _attribution(paper: Paper, version: PaperVersion) -> dict[str, Any]:
    """Who to credit, the copyright statement, and where the text came from.

    Args:
        paper: The paper.
        version: Its displayable version.

    Returns:
        The attribution block.
    """
    retrieved = version.content_retrieved_at
    accessed = retrieved.date().isoformat() if retrieved else "an unknown date"
    is_pmc = version.source == Source.PMC
    return {
        "authors": author_names(version.authors),
        "copyright": access.article_copyright(version),
        "changes": CHANGES_NOTE,
        "source": {
            "name": "PubMed Central (PMC) Article Datasets, NIH National Library of Medicine"
            if is_pmc
            else version.source,
            "url": _source_url(paper, version),
            "retrieved_at": retrieved.isoformat() if retrieved else None,
            "acknowledgement": NLM_ACKNOWLEDGEMENT.format(date=accessed) if is_pmc else "",
        },
    }


def _source_url(paper: Paper, version: PaperVersion) -> str | None:
    """The source's own page for the article.

    Args:
        paper: The paper.
        version: Its version.

    Returns:
        The PMC article page for PMC papers, else None.
    """
    if version.source == Source.PMC and paper.pmcid:
        return f"https://pmc.ncbi.nlm.nih.gov/articles/{paper.pmcid}/"
    return None


def _sections(version: PaperVersion) -> list[dict[str, Any]]:
    """Displayable sections in document order, with their paragraphs and figures.

    Args:
        version: The displayable version.

    Returns:
        A flat list; ``parent`` and ``depth`` give the nesting.
    """
    sections: list[Section] = list(access.displayable_sections(version))
    paragraphs: dict[int, list[Paragraph]] = defaultdict(list)
    for paragraph in access.displayable_paragraphs(version):
        paragraphs[paragraph.section_id].append(paragraph)
    figures: dict[str, list[Figure]] = defaultdict(list)
    for figure in access.displayable_figures(version):
        figures[figure.section_stable_id].append(figure)

    # Depth from the parent chain (parents always precede children).
    by_pk = {section.pk: section for section in sections}
    depth: dict[int, int] = {}
    for section in sections:
        parent = by_pk.get(section.parent_id) if section.parent_id else None
        depth[section.pk] = depth[parent.pk] + 1 if parent is not None else 0

    return [
        {
            "id": section.stable_id,
            "parent": by_pk[section.parent_id].stable_id if section.parent_id in by_pk else None,
            "depth": depth[section.pk],
            "kind": section.kind,
            "title": section.title,
            "label": section.label,
            "paragraphs": [
                {"id": p.stable_id, "kind": p.kind, "text": p.text} for p in paragraphs[section.pk]
            ],
            "figures": [_figure(f) for f in figures[section.stable_id]],
        }
        for section in sections
    ]


def _figure(figure: Figure) -> dict[str, Any]:
    """A figure or table's caption (images and table bodies are not stored).

    Args:
        figure: A displayable figure or table.

    Returns:
        Its ID, kind, label and caption.
    """
    return {
        "id": figure.stable_id,
        "kind": figure.kind,
        "label": figure.label,
        "caption_title": figure.caption_title,
        "caption": figure.caption,
    }


def _annotations(version: PaperVersion) -> list[dict[str, Any]]:
    """Displayable annotations of a version, in W3C Web Annotation shape.

    An annotation whose paragraph text changed since it was anchored is left
    out until it is re-anchored (its selectors may no longer match).

    Args:
        version: The displayable version.

    Returns:
        Annotations with ResearchBridge's provenance fields alongside.
    """
    annotations = (
        Annotation.objects.displayable()
        .filter(paper_version=version)
        .select_related("paragraph")
        .order_by("paragraph__position", "created_at")
    )
    return [
        {
            "@context": "http://www.w3.org/ns/anno.jsonld",
            "id": f"urn:uuid:{annotation.id}",
            "type": "Annotation",
            "motivation": annotation.motivation,
            "body": annotation.body,
            "target": annotation.target,
            "paragraph_id": annotation.paragraph_stable_id,
            "provenance": annotation.provenance,
            "model": annotation.model or None,
            "prompt_version": annotation.prompt_version or None,
            "verified": annotation.verified_at is not None,
            "superseded": annotation.superseded_by_id is not None,
            "needs_disclaimer": annotation.needs_disclaimer,
            "created_at": annotation.created_at.isoformat(),
        }
        for annotation in annotations
        if annotation.paragraph is not None
        and annotation.paragraph.text_sha256 == annotation.paragraph_text_sha256
    ]


def _authors(authors: object) -> list[dict[str, Any]]:
    """Author names and ORCID iDs.

    Args:
        authors: The stored author list.

    Returns:
        ``[{"name", "orcid"}]`` for authors with a name.
    """
    if not isinstance(authors, list):
        return []
    result = []
    for author in authors:
        if not isinstance(author, dict):
            continue
        names = author_names([author])
        if names:
            orcid = author.get("orcid")
            result.append({"name": names[0], "orcid": orcid if isinstance(orcid, str) else None})
    return result


def _strings(value: object) -> list[str]:
    """The non-empty strings of a stored JSON list.

    Args:
        value: A JSON value.

    Returns:
        Its string items, stripped.
    """
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]
