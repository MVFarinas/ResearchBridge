/**
 * The search page (entry point 1, decisions.md §1.5): papers held here first,
 * then the wider scholarly record from OpenAlex, each tagged with what
 * ResearchBridge can offer. Server-rendered from the URL, so results are
 * shareable and work without JavaScript.
 */
import type { Metadata } from "next";
import Link from "next/link";

import { Pagination } from "@/components/Pagination";
import { ResultCard } from "@/components/ResultCard";
import { SearchForm } from "@/components/SearchForm";
import { apiGet, ApiError } from "@/lib/api/client";
import type { SearchResponse } from "@/lib/api/types";
import { formatDate } from "@/lib/format";
import { parseSearchParams, type RawParams, toApiParams } from "@/lib/search-params";

/** Props Next.js passes to the page. */
interface SearchPageProps {
  /** The URL's search parameters. */
  searchParams: Promise<RawParams>;
}

/**
 * The page title, naming the query.
 *
 * @returns Metadata for the page.
 */
export async function generateMetadata({ searchParams }: SearchPageProps): Promise<Metadata> {
  const { q } = parseSearchParams(await searchParams);
  return { title: q ? `Search: ${q}` : "Search", robots: { index: false } };
}

/**
 * The search page.
 *
 * @returns The page.
 */
export default async function SearchPage({ searchParams }: SearchPageProps) {
  const query = parseSearchParams(await searchParams);
  if (!query.q) {
    return (
      <>
        <h1>Search</h1>
        <SearchForm filtersOpen />
      </>
    );
  }

  // The API is the only source of results; a failure is shown, never papered over.
  let data: SearchResponse | null = null;
  let failure = "";
  try {
    data = await apiGet<SearchResponse>("search/", toApiParams(query));
  } catch (error) {
    failure = error instanceof ApiError ? error.message : "The search failed.";
  }

  const corpus = data?.corpus;
  const openalex = data?.openalex;
  const hasNext =
    data !== null &&
    (data.page * data.per_page < data.corpus.total || data.page * data.per_page < data.openalex.total);
  return (
    <>
      <h1>Search results</h1>
      <SearchForm query={query} />
      <p className="small">
        <Link href="/#what-the-labels-mean">What the labels on results mean</Link>
      </p>
      {failure ? (
        <div className="notice danger" role="alert">
          <p>{failure} Please try again in a moment.</p>
        </div>
      ) : null}

      {corpus ? (
        <section className="results-section" aria-labelledby="corpus-heading">
          <header>
            <h2 id="corpus-heading">Readable on ResearchBridge</h2>
            <span className="muted small">
              {corpus.total} {corpus.total === 1 ? "paper" : "papers"}
            </span>
          </header>
          {corpus.results.length > 0 ? (
            <ol className="results">
              {corpus.results.map((result) => (
                <ResultCard key={result.key ?? result.title} result={result} />
              ))}
            </ol>
          ) : (
            <p className="muted">No papers here match. The wider search below may find some.</p>
          )}
        </section>
      ) : null}

      {openalex ? (
        <section className="results-section" aria-labelledby="openalex-heading">
          <header>
            <h2 id="openalex-heading">From the wider scholarly record</h2>
            {openalex.status === "ok" ? (
              <span className="muted small">
                About {openalex.total.toLocaleString("en-GB")} works, from OpenAlex
                {openalex.as_of ? `, as of ${formatDate(openalex.as_of)}` : ""}
              </span>
            ) : null}
          </header>
          {openalex.notice ? (
            <div className="notice warn">
              <p>{openalex.notice}</p>
            </div>
          ) : null}
          {openalex.results.length > 0 ? (
            <ol className="results">
              {openalex.results.map((result) => (
                <ResultCard key={result.openalex_id ?? result.title} result={result} />
              ))}
            </ol>
          ) : openalex.status === "ok" ? (
            <p className="muted">No matching works.</p>
          ) : null}
          <p className="small muted">
            Licence information from OpenAlex is only a hint: a paper is added here only after its
            licence is checked at the source.
          </p>
        </section>
      ) : null}

      <Pagination query={query} hasNext={hasNext} />
    </>
  );
}
