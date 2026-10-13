/**
 * The paper page, server-rendered so search engines index it (decisions.md
 * §1.5): the original text with its annotation layer, the plain-English view
 * (an honest empty state until generation exists), the summary and
 * credibility panels, and the licence and attribution block (§1.1).
 */
import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { AnnotationLayer } from "@/components/AnnotationLayer";
import { CredibilitySlot } from "@/components/CredibilitySlot";
import { EmptyState } from "@/components/EmptyState";
import { LicenceAttribution, LicenceLine } from "@/components/LicenceAttribution";
import { OriginalText } from "@/components/OriginalText";
import { RetractionBanner } from "@/components/RetractionBanner";
import { SummaryPanel } from "@/components/SummaryPanel";
import { ViewTabs } from "@/components/ViewTabs";
import { apiGet } from "@/lib/api/client";
import type { PaperDetail } from "@/lib/api/types";
import { formatAuthors, formatDate } from "@/lib/format";
import { chooseView, withheldMessage } from "@/lib/paper-view";

/** Seconds a paper's content may be reused before it is fetched again. */
const PAPER_REVALIDATE = 300;

/** Props Next.js passes to the page. */
interface PaperPageProps {
  /** Route parameters. */
  params: Promise<{ key: string }>;
  /** URL parameters (`view`). */
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

/**
 * Fetch a paper, or show the 404 page.
 *
 * @param key - The paper key from the URL.
 * @returns The paper.
 */
async function loadPaper(key: string): Promise<PaperDetail> {
  const paper = await apiGet<PaperDetail>(`papers/${encodeURIComponent(key)}/`, {}, PAPER_REVALIDATE);
  if (paper === null) notFound();
  return paper;
}

/**
 * The first abstract paragraph, shortened, for the page description.
 *
 * @param paper - The paper.
 * @returns Up to about 200 characters.
 */
function description(paper: PaperDetail): string {
  const text =
    paper.sections
      .filter((section) => section.id.startsWith("abs"))
      .flatMap((section) => section.paragraphs)[0]?.text ?? "";
  return text.length > 200 ? `${text.slice(0, 197).trimEnd()}…` : text;
}

/**
 * Title, description, canonical URL and Highwire-style citation tags (read by
 * Google Scholar and reference managers).
 *
 * @returns Metadata for the page.
 */
export async function generateMetadata({ params }: PaperPageProps): Promise<Metadata> {
  const { key } = await params;
  const paper = await loadPaper(key);
  const other: Record<string, string | string[]> = {
    citation_title: paper.title,
    citation_author: paper.authors.map((author) => author.name),
  };
  if (paper.journal) other.citation_journal_title = paper.journal;
  if (paper.published_date) other.citation_publication_date = paper.published_date.replaceAll("-", "/");
  if (paper.identifiers.doi) other.citation_doi = paper.identifiers.doi;
  if (paper.identifiers.pmid) other.citation_pmid = paper.identifiers.pmid;
  return {
    title: paper.title,
    description: description(paper),
    alternates: { canonical: `/papers/${paper.key}` },
    other,
  };
}

/**
 * The paper page.
 *
 * @returns The page.
 */
export default async function PaperPage({ params, searchParams }: PaperPageProps) {
  const { key } = await params;
  const requested = (await searchParams).view;
  const paper = await loadPaper(key);
  const view = chooseView(typeof requested === "string" ? requested : undefined, paper.rewrite);
  const visibleAnnotations = paper.annotations.filter((annotation) => !annotation.superseded);

  return (
    <article>
      {paper.retraction.is_retracted ? (
        <RetractionBanner source={paper.retraction.source} date={paper.retraction.date} />
      ) : null}
      <div className="paper-layout">
        <div>
          <header className="paper-header">
            <p className="muted small">
              {[paper.journal, formatDate(paper.published_date)].filter(Boolean).join(" · ")}
            </p>
            <h1>{paper.title}</h1>
            <p className="byline">{formatAuthors(paper.authors.map((a) => a.name), 8)}</p>
            <LicenceLine paper={paper} />
            <div className="link-bar">
              {paper.links.doi ? (
                <a className="button" href={paper.links.doi} rel="noopener noreferrer">
                  Read original paper
                </a>
              ) : null}
              {paper.links.scholar ? (
                <a className="button secondary" href={paper.links.scholar} rel="noopener noreferrer">
                  Find on Google Scholar
                </a>
              ) : null}
            </div>
          </header>

          <ViewTabs paperKey={paper.key} current={view} />

          {view === "plain" ? (
            <EmptyState
              title={
                paper.rewrite.status === "not_permitted"
                  ? "No plain-English version for this paper"
                  : "Plain-English version not written yet"
              }
            >
              <p>{paper.rewrite.reason}</p>
              <p>
                <a href={`/papers/${paper.key}?view=original`}>Read the original</a>
                {paper.rewrite.status === "not_generated"
                  ? " in the meantime. When the plain-English version is ready it will appear here, paragraph by paragraph beside the original on wide screens."
                  : "."}
              </p>
            </EmptyState>
          ) : (
            <>
              {withheldMessage(paper.withheld) ? (
                <div className="notice info">
                  <p>{withheldMessage(paper.withheld)}</p>
                </div>
              ) : null}
              {visibleAnnotations.length === 0 ? (
                <p className="notice">
                  No explanations have been written for this paper yet.
                </p>
              ) : null}
              <AnnotationLayer annotations={visibleAnnotations}>
                <OriginalText sections={paper.sections} />
              </AnnotationLayer>
            </>
          )}

          <LicenceAttribution paper={paper} />
        </div>

        <aside aria-label="About this paper">
          <SummaryPanel summary={paper.summary} declarations={paper.declarations} />
          <Suspense
            fallback={
              <section className="panel">
                <h2>Citations and status</h2>
                <p className="muted">Loading…</p>
              </section>
            }
          >
            <CredibilitySlot paperKey={paper.key} />
          </Suspense>
        </aside>
      </div>
    </article>
  );
}
