/**
 * Neutral, paper-level credibility signals (decisions.md §2.3: nothing about
 * the journal). Every figure names its source and the date it was retrieved.
 */
import { Sparkline } from "@/components/Sparkline";
import type { Credibility, CredibilitySection } from "@/lib/api/types";
import { formatDate } from "@/lib/format";

/** Props of {@link CredibilityPanel}. */
export interface CredibilityPanelProps {
  /** The signals, or null when the service could not be reached at all. */
  credibility: Credibility | null;
}

/**
 * Source line with the "as of" date, and any note about the source's state.
 *
 * @returns The note.
 */
function AsOf({ section }: { section: CredibilitySection }) {
  return (
    <p className="as-of">
      Source:{" "}
      <a href={section.source.url} rel="noopener noreferrer">
        {section.source.name}
      </a>{" "}
      ({section.source.licence})
      {section.as_of ? `, as of ${formatDate(section.as_of)}` : ""}.
      {section.message ? ` ${section.message}` : ""}
    </p>
  );
}

/**
 * Describe a citation percentile in relative, factual words.
 *
 * @param percentile - Percentile among works of the same field, year and type.
 * @param top1 - Whether in the top 1%.
 * @param top10 - Whether in the top 10%.
 * @returns A phrase such as "top 10% of papers in its field and year".
 */
export function percentilePhrase(
  percentile: number,
  top1: boolean | null,
  top10: boolean | null,
): string {
  if (top1) return "in the top 1% of papers in its field and year by citations";
  if (top10) return "in the top 10% of papers in its field and year by citations";
  return `cited more than about ${Math.floor(percentile)}% of papers in its field and year`;
}

/**
 * The credibility panel.
 *
 * @returns The panel.
 */
export function CredibilityPanel({ credibility }: CredibilityPanelProps) {
  if (credibility === null) {
    return (
      <section className="panel" aria-labelledby="credibility-heading">
        <h2 id="credibility-heading">Citations and status</h2>
        <p className="muted">These signals could not be loaded right now.</p>
      </section>
    );
  }
  const { openalex, icite, crossref, integrity } = credibility;
  const metrics = openalex.metrics;
  return (
    <section className="panel" aria-labelledby="credibility-heading">
      <h2 id="credibility-heading">Citations and status</h2>

      {integrity.retracted || integrity.expression_of_concern ? (
        <div className="notice danger">
          {integrity.retracted ? <p>Retracted.</p> : null}
          {integrity.expression_of_concern ? (
            <p>An expression of concern has been published about this paper.</p>
          ) : null}
        </div>
      ) : null}

      <h3>Citations (OpenAlex)</h3>
      {metrics ? (
        <>
          <dl>
            <dt>Cited by</dt>
            <dd>{metrics.cited_by_count ?? "unknown"}</dd>
            {metrics.fwci !== null ? (
              <>
                <dt>Field-weighted impact</dt>
                <dd>{metrics.fwci.toFixed(2)} (1.00 = world average)</dd>
              </>
            ) : null}
          </dl>
          {metrics.citation_percentile !== null ? (
            <p className="small">
              {`This paper is ${percentilePhrase(
                metrics.citation_percentile,
                metrics.top_1_percent,
                metrics.top_10_percent,
              )}.`}
            </p>
          ) : null}
          <Sparkline data={metrics.counts_by_year} label="Citations" />
        </>
      ) : (
        <p className="muted small">No citation data.</p>
      )}
      <AsOf section={openalex} />

      {icite.status !== "not_applicable" ? (
        <>
          <h3>Citations (NIH iCite)</h3>
          {icite.metrics ? (
            <>
              <dl>
                <dt>Cited by</dt>
                <dd>{icite.metrics.citation_count ?? "unknown"}</dd>
                {icite.metrics.relative_citation_ratio !== null ? (
                  <>
                    <dt>Relative Citation Ratio</dt>
                    <dd>
                      {icite.metrics.relative_citation_ratio.toFixed(2)}
                      {icite.metrics.rcr_provisional ? " (provisional)" : ""}
                    </dd>
                  </>
                ) : null}
              </dl>
              <Sparkline data={icite.metrics.citations_by_year} label="Citations" />
            </>
          ) : (
            <p className="muted small">No iCite data.</p>
          )}
          <AsOf section={icite} />
        </>
      ) : null}

      <h3>Corrections and retractions</h3>
      {crossref.notices.length > 0 ? (
        <ul className="small">
          {crossref.notices.map((notice) => (
            <li key={`${notice.kind}-${notice.notice_doi ?? notice.date}`}>
              {notice.notice_url ? <a href={notice.notice_url}>{notice.label}</a> : notice.label}
              {notice.date ? `, ${formatDate(notice.date)}` : ""}
              {notice.source === "retraction-watch" ? " (Retraction Watch)" : " (publisher)"}
            </li>
          ))}
        </ul>
      ) : crossref.status === "ok" ? (
        <p className="small">None recorded.</p>
      ) : (
        <p className="muted small">Not available.</p>
      )}
      <AsOf section={crossref} />
      {crossref.source.citation ? <p className="as-of">{crossref.source.citation}</p> : null}

      <p className="small muted">
        Citation counts show attention, not whether a finding is correct. Recent papers have had
        little time to be cited.
      </p>
    </section>
  );
}
