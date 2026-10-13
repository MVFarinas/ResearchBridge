/** One search result: title, byline, availability tag, snippet and next steps. */
import Link from "next/link";

import { AvailabilityTag } from "@/components/AvailabilityTag";
import { Highlighted } from "@/components/Highlighted";
import type { SearchResult } from "@/lib/api/types";
import { formatAuthors, formatDate } from "@/lib/format";

/** Props of {@link ResultCard}. */
export interface ResultCardProps {
  /** The result. */
  result: SearchResult;
}

/**
 * A search result. Corpus papers link to their page; others link to the DOI,
 * and openly licensed ones offer a lookup that checks eligibility at the source.
 *
 * @returns The card.
 */
export function ResultCard({ result }: ResultCardProps) {
  const byline = [formatAuthors(result.authors), result.journal, formatDate(result.published_date)]
    .filter(Boolean)
    .join(" · ");
  const title = result.title || "Untitled";
  return (
    <li className="result">
      <AvailabilityTag availability={result.availability} rewriteStatus={result.rewrite_status} />{" "}
      {result.is_retracted ? <span className="tag retracted">Retracted</span> : null}
      <h3>{result.key ? <Link href={`/papers/${result.key}`}>{title}</Link> : title}</h3>
      {byline ? <p className="meta">{byline}</p> : null}
      {result.licence ? <p className="meta">Licence: {result.licence}</p> : null}
      {result.snippet ? (
        <p className="snippet">
          <Highlighted snippet={result.snippet} />
        </p>
      ) : null}
      <div className="result-actions">
        {result.key ? <Link href={`/papers/${result.key}`}>Read it here</Link> : null}
        {result.lookup_query ? (
          <Link href={`/lookup?q=${encodeURIComponent(result.lookup_query)}`}>
            Check if it can be added
          </Link>
        ) : null}
        {result.links.doi ? (
          <a href={result.links.doi} rel="noopener noreferrer">
            Read original paper
          </a>
        ) : null}
        {result.links.scholar ? (
          <a href={result.links.scholar} rel="noopener noreferrer">
            Find on Google Scholar
          </a>
        ) : null}
      </div>
    </li>
  );
}
