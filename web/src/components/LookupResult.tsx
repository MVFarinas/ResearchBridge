/**
 * What a lookup found, for outcomes that stay on the lookup page: candidates
 * for a title, "not available here" with links, or a temporary problem.
 */
import { ResultCard } from "@/components/ResultCard";
import type { LookupResponse } from "@/lib/api/types";

/** Props of {@link LookupResult}. */
export interface LookupResultProps {
  /** The backend's answer. */
  result: LookupResponse;
}

/**
 * The lookup outcome.
 *
 * @returns The rendered outcome.
 */
export function LookupResult({ result }: LookupResultProps) {
  if (result.outcome === "candidates" && result.search) {
    const candidates = [...result.search.corpus.results, ...result.search.openalex.results];
    return (
      <section aria-labelledby="candidates-heading">
        <h2 id="candidates-heading">Possible matches</h2>
        <p>{result.message}</p>
        {result.search.openalex.notice ? (
          <p className="notice warn">{result.search.openalex.notice}</p>
        ) : null}
        {candidates.length > 0 ? (
          <ol className="results">
            {candidates.map((candidate) => (
              <ResultCard
                key={candidate.key ?? candidate.openalex_id ?? candidate.title}
                result={candidate}
              />
            ))}
          </ol>
        ) : (
          <p className="muted">No matches found. Try the DOI if you have it.</p>
        )}
      </section>
    );
  }

  const links = result.links ?? {};
  const tone = result.outcome === "not_available" ? "notice" : "notice warn";
  return (
    <div className={tone} role="status">
      <p>{result.message}</p>
      {result.licence_code ? (
        <p className="small">Licence recorded by PubMed Central: {result.licence_code}.</p>
      ) : null}
      <p className="result-actions">
        {links.doi ? (
          <a href={links.doi} rel="noopener noreferrer">
            Read original paper
          </a>
        ) : null}
        {links.arxiv ? (
          <a href={links.arxiv} rel="noopener noreferrer">
            Read it on arXiv
          </a>
        ) : null}
        {links.pubmed ? (
          <a href={links.pubmed} rel="noopener noreferrer">
            View on PubMed
          </a>
        ) : null}
        {links.scholar ? (
          <a href={links.scholar} rel="noopener noreferrer">
            Find on Google Scholar
          </a>
        ) : null}
      </p>
    </div>
  );
}
