/** A prominent notice on a retracted paper (Phase 2 keeps retracted papers readable). */
import { formatDate } from "@/lib/format";

/** Props of {@link RetractionBanner}. */
export interface RetractionBannerProps {
  /** Which source reported the retraction, e.g. "crossref:retraction-watch". */
  source: string | null;
  /** Date of the notice, if known. */
  date: string | null;
}

const SOURCE_NAMES: Record<string, string> = {
  "pmc:is_retracted": "PubMed Central",
  "crossref:retraction-watch": "the Retraction Watch Database (via Crossref)",
  "crossref:publisher": "the publisher (via Crossref)",
  "openalex:is_retracted": "OpenAlex (from the Retraction Watch Database)",
};

/**
 * A banner stating that the paper has been retracted, and by whose account.
 *
 * @returns The banner.
 */
export function RetractionBanner({ source, date }: RetractionBannerProps) {
  const reportedBy = source ? (SOURCE_NAMES[source] ?? source) : "a source we use";
  return (
    <div className="notice danger" role="alert">
      <p>
        <strong>This paper has been retracted.</strong> Its findings should not be relied on.
      </p>
      <p className="small">
        Reported by {reportedBy}
        {date ? `; notice dated ${formatDate(date)}` : ""}. The original is kept here so the record
        can be read, but no plain-English version is produced.
      </p>
    </div>
  );
}
