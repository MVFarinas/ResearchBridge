/**
 * The appraisal summary panel (Plan.md Phase 3, feature 3). No summary has
 * been generated yet, so it shows an honest empty state and what the summary
 * will cover, plus the declarations quoted from the paper itself.
 */
import { EmptyState } from "@/components/EmptyState";
import type { GenerationState, PaperDetail } from "@/lib/api/types";

/** Props of {@link SummaryPanel}. */
export interface SummaryPanelProps {
  /** The summary's state. */
  summary: GenerationState;
  /** Conflict-of-interest and funding statements quoted from the paper. */
  declarations: PaperDetail["declarations"];
}

/**
 * The summary panel with the paper's own declarations.
 *
 * @returns The panel.
 */
export function SummaryPanel({ summary, declarations }: SummaryPanelProps) {
  const quoted = [...declarations.conflicts_of_interest, ...declarations.funding];
  return (
    <section className="panel" aria-labelledby="summary-heading">
      <h2 id="summary-heading">Summary</h2>
      <EmptyState title="Not generated yet">
        <p>{summary.reason}</p>
        <p className="small">
          When available, it will set out the main findings, limitations, conflicts of interest,
          funding, sample and effect sizes, and whether the findings show cause or only an
          association, each linked to the passage it comes from.
        </p>
      </EmptyState>
      {quoted.length > 0 ? (
        <>
          <h3>Declarations in the paper</h3>
          <p className="small muted">Quoted from the paper, not summarised.</p>
          {declarations.conflicts_of_interest.map((text) => (
            <blockquote key={`coi-${text}`} className="small">
              <strong>Competing interests:</strong> {text}
            </blockquote>
          ))}
          {declarations.funding.map((text) => (
            <blockquote key={`funding-${text}`} className="small">
              <strong>Funding:</strong> {text}
            </blockquote>
          ))}
        </>
      ) : null}
    </section>
  );
}
