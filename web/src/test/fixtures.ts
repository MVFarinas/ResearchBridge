/**
 * SYNTHETIC test data shaped like the backend API's responses. None of it is
 * a real paper, explanation or metric; values are invented to exercise the UI.
 */
import type {
  ApiAnnotation,
  Credibility,
  PaperDetail,
  SearchResult,
} from "@/lib/api/types";

/**
 * A synthetic paper detail, with overrides.
 *
 * @param overrides - Fields to replace.
 * @returns The paper.
 */
export function syntheticPaper(overrides: Partial<PaperDetail> = {}): PaperDetail {
  return {
    key: "PMC900000001",
    title: "Synthetic test paper",
    identifiers: {
      doi: "10.9999/synthetic.1",
      pmcid: "PMC900000001",
      pmid: "900000001",
      arxiv_id: null,
      source_version: "PMC900000001.1",
    },
    authors: [{ name: "Ada Synthetic", orcid: null }, { name: "Bo Example", orcid: null }],
    journal: "Synthetic Journal of Testing",
    publisher: "Synthetic Publisher",
    published_date: "2024-05-01",
    article_type: "research-article",
    citation: "Synthetic. 2024.",
    retraction: { is_retracted: false, source: null, date: null },
    licence: {
      label: "CC BY 4.0",
      url: "https://creativecommons.org/licenses/by/4.0/",
      family: "cc-by",
      version: "4.0",
      attribution_required: true,
      non_commercial: false,
      share_alike: false,
      no_derivatives: false,
      decision_source: "pmc:license_code",
      decided_at: "2026-10-13T12:00:00Z",
    },
    permissions: {
      can_display: true,
      can_rewrite: true,
      output_licence: { label: "CC BY 4.0", url: "https://creativecommons.org/licenses/by/4.0/" },
    },
    attribution: {
      authors: ["Ada Synthetic", "Bo Example"],
      copyright: ["© 2024 Synthetic et al"],
      changes: "Synthetic changes note.",
      source: {
        name: "PubMed Central (PMC) Article Datasets, NIH National Library of Medicine",
        url: "https://pmc.ncbi.nlm.nih.gov/articles/PMC900000001/",
        retrieved_at: "2026-10-13T12:00:00Z",
        acknowledgement:
          "Full text and metadata from the NIH National Library of Medicine (NLM) PubMed Central Article Datasets on AWS, accessed 2026-10-13. Use does not imply endorsement by NLM.",
      },
    },
    declarations: { conflicts_of_interest: ["Synthetic: none declared."], funding: [] },
    sections: [
      {
        id: "abs1",
        parent: null,
        depth: 0,
        kind: "abstract",
        title: "",
        label: "",
        figures: [],
        paragraphs: [{ id: "abs1-p1", kind: "p", text: "Synthetic abstract text." }],
      },
      {
        id: "sec1",
        parent: null,
        depth: 0,
        kind: "sec",
        title: "Introduction",
        label: "1",
        figures: [
          {
            id: "fig1",
            kind: "figure",
            label: "Figure 1",
            caption_title: "Synthetic figure.",
            caption: "Synthetic caption.",
          },
        ],
        paragraphs: [{ id: "sec1-p1", kind: "p", text: "Synthetic body text about sleep." }],
      },
    ],
    withheld: { paragraphs: 0, figures: 0 },
    annotations: [],
    rewrite: { status: "not_generated", reason: "A plain-English version has not been generated yet." },
    summary: { status: "not_generated", reason: "An appraisal summary has not been generated yet." },
    links: {
      doi: "https://doi.org/10.9999/synthetic.1",
      scholar: "https://scholar.google.com/scholar?q=Synthetic+test+paper",
      source: "https://pmc.ncbi.nlm.nih.gov/articles/PMC900000001/",
    },
    ...overrides,
  };
}

/**
 * A synthetic search result, with overrides.
 *
 * @param overrides - Fields to replace.
 * @returns The result.
 */
export function syntheticResult(overrides: Partial<SearchResult> = {}): SearchResult {
  return {
    origin: "corpus",
    key: "PMC900000001",
    title: "Synthetic test paper",
    authors: ["Ada Synthetic"],
    journal: "Synthetic Journal of Testing",
    published_date: "2024-05-01",
    doi: "10.9999/synthetic.1",
    pmcid: "PMC900000001",
    pmid: null,
    availability: "plain_english_available",
    rewrite_status: "not_generated",
    licence: "CC BY 4.0",
    is_retracted: false,
    links: {
      doi: "https://doi.org/10.9999/synthetic.1",
      scholar: "https://scholar.google.com/scholar?q=Synthetic",
    },
    snippet: "",
    ...overrides,
  };
}

/**
 * A synthetic annotation on a paragraph, positioned in code points.
 *
 * @param paragraphId - The paragraph.
 * @param text - The paragraph's text.
 * @param exact - The quoted passage (must occur in the text).
 * @param overrides - Fields to replace.
 * @returns The annotation.
 */
export function syntheticAnnotation(
  paragraphId: string,
  text: string,
  exact: string,
  overrides: Partial<ApiAnnotation> = {},
): ApiAnnotation {
  const start = [...text.slice(0, text.indexOf(exact))].length;
  return {
    id: `urn:uuid:synthetic-${paragraphId}-${start}`,
    type: "Annotation",
    motivation: "describing",
    body: { type: "TextualBody", value: "Synthetic explanation.", format: "text/plain" },
    target: {
      source: "synthetic",
      selector: [
        { type: "TextQuoteSelector", exact },
        { type: "TextPositionSelector", start, end: start + [...exact].length },
      ],
    },
    paragraph_id: paragraphId,
    provenance: "llm",
    model: "synthetic-model",
    prompt_version: "synthetic-v0",
    verified: false,
    superseded: false,
    needs_disclaimer: true,
    created_at: "2026-10-13T12:00:00Z",
    ...overrides,
  };
}

/**
 * Synthetic credibility signals, with overrides.
 *
 * @param overrides - Fields to replace.
 * @returns The signals.
 */
export function syntheticCredibility(overrides: Partial<Credibility> = {}): Credibility {
  const source = (name: string) => ({ name, licence: "CC0", url: "https://example.org/" });
  return {
    openalex: {
      status: "ok",
      as_of: "2026-10-13T12:00:00Z",
      stale: false,
      message: "",
      source: source("OpenAlex"),
      metrics: {
        cited_by_count: 12,
        counts_by_year: [
          { year: 2025, count: 4 },
          { year: 2026, count: 8 },
        ],
        fwci: 1.5,
        citation_percentile: 91.2,
        top_1_percent: false,
        top_10_percent: true,
        is_retracted: false,
      },
    },
    icite: {
      status: "ok",
      as_of: "2026-10-12T12:00:00Z",
      stale: false,
      message: "",
      source: source("NIH iCite"),
      metrics: {
        citation_count: 10,
        citations_by_year: [{ year: 2026, count: 10 }],
        relative_citation_ratio: 1.25,
        rcr_provisional: true,
        nih_percentile: 60,
        is_research_article: true,
      },
    },
    crossref: {
      status: "ok",
      as_of: "2026-10-11T12:00:00Z",
      stale: false,
      message: "",
      source: { ...source("Crossref"), citation: "Synthetic citation request." },
      notices: [],
    },
    integrity: {
      retracted: false,
      retraction_source: null,
      retraction_date: null,
      expression_of_concern: false,
      corrected: false,
    },
    ...overrides,
  };
}
