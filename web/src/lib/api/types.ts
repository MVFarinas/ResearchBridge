/**
 * Types of the backend reader API responses (`/api/v1/`), mirroring
 * `backend/src/rb_backend/api` and `rb_backend/discovery`.
 */

/** The single availability tag every search result carries (decisions.md §1.5). */
export type Availability =
  | "plain_english_available"
  | "original_annotations_only"
  | "may_be_available"
  | "original_elsewhere";

/** Whether a generated item (rewrite, summary) exists for a paper. */
export type GenerationStatus = "available" | "not_generated" | "not_permitted";

/** The state of one generated item and the reason, in reader-facing words. */
export interface GenerationState {
  /** Available, not generated yet, or not permitted by the licence. */
  status: GenerationStatus;
  /** Why, for the reader. */
  reason: string;
}

/** Outbound links of a result or paper. */
export interface Links {
  /** `https://doi.org/<doi>`, the publisher's canonical version. */
  doi: string | null;
  /** A Google Scholar search URL (a link only; Scholar is never fetched). */
  scholar: string | null;
}

/** One search result, from the corpus or from OpenAlex. */
export interface SearchResult {
  /** Where the result came from. */
  origin: "corpus" | "openalex";
  /** The corpus paper key, when ResearchBridge holds the paper. */
  key: string | null;
  /** Title. */
  title: string;
  /** First few author names. */
  authors: string[];
  /** Journal name. */
  journal: string;
  /** ISO date at the precision known (may be ""). */
  published_date: string;
  /** Bare DOI. */
  doi: string | null;
  /** PMC ID. */
  pmcid: string | null;
  /** PubMed ID. */
  pmid: string | null;
  /** What ResearchBridge can offer for it. */
  availability: Availability;
  /** Status of the plain-English rewrite (corpus papers only). */
  rewrite_status: GenerationStatus | null;
  /** Licence label of a corpus paper (e.g. "CC BY 4.0"). */
  licence: string | null;
  /** Whether a source reports it retracted. */
  is_retracted: boolean;
  /** Outbound links. */
  links: Links;
  /** Abstract snippet with highlight markers (corpus results). */
  snippet: string;
  /** OpenAlex ID URL (OpenAlex results). */
  openalex_id?: string;
  /** The licence OpenAlex reports: a secondary signal, never a decision. */
  licence_reported_by_openalex?: string | null;
  /** Citations OpenAlex counts. */
  cited_by_count?: number | null;
  /** The identifier to send to lookup, for "may be available" results. */
  lookup_query?: string | null;
}

/** Status of the OpenAlex part of a search. */
export type OpenAlexStatus = "ok" | "skipped" | "refused" | "unavailable";

/** The response of `GET /search/`. */
export interface SearchResponse {
  /** The query searched. */
  query: string;
  /** 1-based page. */
  page: number;
  /** Results per page (both lists). */
  per_page: number;
  /** Papers in the corpus. */
  corpus: { total: number; results: SearchResult[] };
  /** The wider scholarly record from OpenAlex. */
  openalex: {
    status: OpenAlexStatus;
    notice: string;
    as_of: string | null;
    stale: boolean;
    total: number;
    results: SearchResult[];
    has_key: boolean;
  };
}

/** A paragraph of the original text. */
export interface Paragraph {
  /** Stable ID (the alignment unit for rewrites and annotations). */
  id: string;
  /** p, list-item, quote, boxed, def or formula. */
  kind: string;
  /** Plain text. */
  text: string;
}

/** A figure or table caption (images are not stored). */
export interface FigureCaption {
  /** Stable ID. */
  id: string;
  /** figure or table. */
  kind: string;
  /** Label such as "Figure 1". */
  label: string;
  /** Caption title. */
  caption_title: string;
  /** Caption text. */
  caption: string;
}

/** A section in document order; `parent` and `depth` give the nesting. */
export interface Section {
  /** Stable ID. */
  id: string;
  /** Parent section ID, if nested. */
  parent: string | null;
  /** Nesting depth (0 for roots). */
  depth: number;
  /** body, abstract, back, sec, ack, app or notes. */
  kind: string;
  /** Title ("" for untitled roots). */
  title: string;
  /** Label such as "2.1". */
  label: string;
  /** Its displayable paragraphs. */
  paragraphs: Paragraph[];
  /** Its displayable figures and tables. */
  figures: FigureCaption[];
}

/** A W3C text selector. */
export type TextSelector =
  | { type: "TextQuoteSelector"; exact: string; prefix?: string; suffix?: string }
  | { type: "TextPositionSelector"; start: number; end: number };

/** An annotation in W3C Web Annotation shape, with ResearchBridge provenance. */
export interface ApiAnnotation {
  /** `urn:uuid:<id>`. */
  id: string;
  /** Always "Annotation". */
  type: "Annotation";
  /** W3C motivation. */
  motivation: string;
  /** W3C TextualBody (plain text or Markdown; never HTML). */
  body: { type: "TextualBody"; value: string; format?: string; purpose?: string };
  /** Target: the version and its two selectors (positions in Unicode code points). */
  target: { source: string; selector: TextSelector[] };
  /** The paragraph the selectors are relative to. */
  paragraph_id: string;
  /** Who wrote it (decisions.md §1.3). */
  provenance: "llm" | "human" | "llm_edited";
  /** Model that generated it, for LLM provenance. */
  model: string | null;
  /** Prompt version, for LLM provenance. */
  prompt_version: string | null;
  /** Whether a human verified it. */
  verified: boolean;
  /** Whether a better annotation of the passage supersedes it. */
  superseded: boolean;
  /** Whether the accuracy disclaimer must be shown. */
  needs_disclaimer: boolean;
  /** Creation time. */
  created_at: string;
}

/** A licence as decided by the gate. */
export interface Licence {
  /** e.g. "CC BY 4.0". */
  label: string;
  /** Canonical licence URL, when known. */
  url: string | null;
  /** Licence family, e.g. "cc-by". */
  family: string;
  /** Version, e.g. "4.0". */
  version: string | null;
  /** Whether the authors must be credited. */
  attribution_required: boolean;
  /** Non-commercial use only. */
  non_commercial: boolean;
  /** Derivatives must carry the same licence. */
  share_alike: boolean;
  /** No derivatives (no rewrite). */
  no_derivatives: boolean;
  /** Which source field the decision came from. */
  decision_source: string;
  /** When the gate decided. */
  decided_at: string | null;
}

/** The response of `GET /papers/<key>/`. */
export interface PaperDetail {
  /** Public key (`PMC…`). */
  key: string;
  /** Title. */
  title: string;
  /** Identifiers. */
  identifiers: {
    doi: string | null;
    pmcid: string | null;
    pmid: string | null;
    arxiv_id: string | null;
    source_version: string;
  };
  /** Authors with ORCID iDs where known. */
  authors: { name: string; orcid: string | null }[];
  /** Journal. */
  journal: string;
  /** Publisher. */
  publisher: string;
  /** ISO date at the precision known. */
  published_date: string;
  /** JATS article type. */
  article_type: string;
  /** The source's citation string. */
  citation: string;
  /** Retraction status. */
  retraction: { is_retracted: boolean; source: string | null; date: string | null };
  /** The decided licence. */
  licence: Licence;
  /** What the licence permits. */
  permissions: {
    can_display: boolean;
    can_rewrite: boolean;
    output_licence: { label: string; url: string | null } | null;
  };
  /** Attribution, copyright and source acknowledgement. */
  attribution: {
    authors: string[];
    copyright: string[];
    changes: string;
    source: {
      name: string;
      url: string | null;
      retrieved_at: string | null;
      acknowledgement: string;
    };
  };
  /** Declarations quoted from the paper. */
  declarations: { conflicts_of_interest: string[]; funding: string[] };
  /** Sections in document order. */
  sections: Section[];
  /** Parts left out because their own licence is narrower or under review. */
  withheld: { paragraphs: number; figures: number };
  /** Annotations (none until generation or the community layer exists). */
  annotations: ApiAnnotation[];
  /** The plain-English rewrite's state. */
  rewrite: GenerationState;
  /** The appraisal summary's state. */
  summary: GenerationState;
  /** Outbound links. */
  links: Links & { source: string | null };
}

/** Status of one credibility source. */
export type SourceStatus = "ok" | "not_found" | "not_applicable" | "unavailable";

/** Where a credibility signal came from. */
export interface SignalSource {
  /** Source name. */
  name: string;
  /** Data licence. */
  licence: string;
  /** Source website. */
  url: string;
  /** Requested citation, if any. */
  citation?: string;
}

/** Common fields of every credibility section. */
export interface CredibilitySection {
  /** Whether the source answered. */
  status: SourceStatus;
  /** When the source gave this answer. */
  as_of: string | null;
  /** True when a refresh failed and an older answer is shown. */
  stale: boolean;
  /** Reader-facing note. */
  message: string;
  /** The source. */
  source: SignalSource;
}

/** A count for one year. */
export interface YearCount {
  /** The year. */
  year: number;
  /** The count. */
  count: number;
}

/** An editorial notice about a paper (from Crossref, including Retraction Watch). */
export interface EditorialNotice {
  /** Crossmark type, e.g. "retraction". */
  kind: string;
  /** Label, e.g. "Retraction". */
  label: string;
  /** retraction-watch or publisher. */
  source: string;
  /** DOI of the notice. */
  notice_doi: string | null;
  /** Link to the notice. */
  notice_url: string | null;
  /** Date of the notice. */
  date: string | null;
  /** Retraction Watch record ID. */
  retraction_watch_record: string | null;
}

/** The response of `GET /papers/<key>/credibility/`. */
export interface Credibility {
  /** OpenAlex citation metrics. */
  openalex: CredibilitySection & {
    metrics: {
      cited_by_count: number | null;
      counts_by_year: YearCount[];
      fwci: number | null;
      citation_percentile: number | null;
      top_1_percent: boolean | null;
      top_10_percent: boolean | null;
      is_retracted: boolean;
    } | null;
  };
  /** NIH iCite metrics. */
  icite: CredibilitySection & {
    metrics: {
      citation_count: number | null;
      citations_by_year: YearCount[];
      relative_citation_ratio: number | null;
      rcr_provisional: boolean | null;
      nih_percentile: number | null;
      is_research_article: boolean | null;
    } | null;
  };
  /** Crossref notices. */
  crossref: CredibilitySection & { notices: EditorialNotice[] };
  /** Summary of retraction and expression-of-concern status. */
  integrity: {
    retracted: boolean;
    retraction_source: string | null;
    retraction_date: string | null;
    expression_of_concern: boolean;
    corrected: boolean;
  };
}

/** Outcome of a lookup. */
export type LookupOutcome =
  | "in_corpus"
  | "queued"
  | "candidates"
  | "not_available"
  | "budget_exhausted"
  | "unavailable";

/** Status of a queued lookup request. */
export type RequestStatus =
  | "preparing"
  | "ready"
  | "held_for_review"
  | "not_available"
  | "failed";

/** The response of `GET /lookup/requests/<id>/`. */
export interface LookupRequestStatus {
  /** Request UUID. */
  id: string;
  /** Where it stands. */
  status: RequestStatus;
  /** Reader-facing message. */
  message: string;
  /** The PMC article requested. */
  pmcid: string;
  /** When it was requested. */
  created_at: string;
  /** The paper, once ready. */
  paper: { key: string; title: string } | null;
  /** Outbound links. */
  links: { doi: string | null };
}

/** The response of `POST /lookup/`. */
export interface LookupResponse {
  /** What happened. */
  outcome: LookupOutcome;
  /** Reader-facing message. */
  message: string;
  /** What was recognised in the query. */
  identifier?: { kind: string; value: string };
  /** The corpus paper, for in_corpus. */
  paper?: { key: string; title: string };
  /** The queued request, for queued. */
  request?: LookupRequestStatus;
  /** Candidates, for a title. */
  search?: SearchResponse;
  /** Outbound links, for not_available. */
  links?: Partial<Links> & { arxiv?: string | null; pubmed?: string | null };
  /** The PMC licence code seen, when it refused. */
  licence_code?: string;
}
