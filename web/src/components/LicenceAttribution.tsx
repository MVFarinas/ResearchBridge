/**
 * The licence and attribution block every paper page carries (decisions.md §1.1),
 * with the NLM acknowledgement the PMC Cloud Service terms require.
 */
import type { PaperDetail } from "@/lib/api/types";
import { formatAuthors, formatDate } from "@/lib/format";

/** Props of {@link LicenceAttribution} and {@link LicenceLine}. */
export interface LicenceAttributionProps {
  /** The paper. */
  paper: PaperDetail;
}

/**
 * The licence name, linked to its text.
 *
 * @returns The link, or the plain label when no URL is known.
 */
function LicenceLink({ paper }: LicenceAttributionProps) {
  const { label, url } = paper.licence;
  return url ? (
    <a href={url} rel="license noopener noreferrer">
      {label}
    </a>
  ) : (
    <>{label}</>
  );
}

/**
 * A one-line licence statement for the top of the page.
 *
 * @returns The line.
 */
export function LicenceLine({ paper }: LicenceAttributionProps) {
  return (
    <p className="licence-line">
      Licence: <LicenceLink paper={paper} />.{" "}
      {paper.permissions.can_rewrite
        ? "It allows a plain-English version with credit to the authors."
        : "It allows showing the original, but not a rewritten version."}{" "}
      <a href="#attribution">Attribution and source</a>
    </p>
  );
}

/**
 * The full attribution block: who to credit, the copyright line, the licence,
 * what was changed, and where the text came from.
 *
 * @returns The block.
 */
export function LicenceAttribution({ paper }: LicenceAttributionProps) {
  const { attribution } = paper;
  return (
    <section className="attribution" id="attribution" aria-labelledby="attribution-heading">
      <h2 id="attribution-heading">Licence and attribution</h2>
      <p>
        “{paper.title}” by {formatAuthors(attribution.authors, 6) || "its authors"}
        {paper.journal ? `, ${paper.journal}` : ""}
        {paper.published_date ? ` (${formatDate(paper.published_date)})` : ""}
        {paper.links.doi ? (
          <>
            , <a href={paper.links.doi}>{paper.links.doi}</a>
          </>
        ) : null}
        . Licensed under <LicenceLink paper={paper} />.
      </p>
      {attribution.copyright.map((line) => (
        <p key={line}>{line}</p>
      ))}
      {paper.licence.non_commercial ? (
        <p>The licence allows non-commercial use only.</p>
      ) : null}
      {paper.permissions.output_licence ? (
        <p>
          Any plain-English version published here is released under{" "}
          {paper.permissions.output_licence.url ? (
            <a href={paper.permissions.output_licence.url} rel="license">
              {paper.permissions.output_licence.label}
            </a>
          ) : (
            paper.permissions.output_licence.label
          )}
          .
        </p>
      ) : null}
      <p>{attribution.changes}</p>
      <p>
        Source:{" "}
        {attribution.source.url ? (
          <a href={attribution.source.url}>{attribution.source.name}</a>
        ) : (
          attribution.source.name
        )}
        {paper.identifiers.source_version ? ` (${paper.identifiers.source_version})` : ""}.
      </p>
      {attribution.source.acknowledgement ? (
        <p className="small muted">{attribution.source.acknowledgement}</p>
      ) : null}
    </section>
  );
}
