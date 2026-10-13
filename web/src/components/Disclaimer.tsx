/** The accuracy disclaimer shown with machine-written text (decisions.md §1.3). */

/** What kind of machine-written text the disclaimer accompanies. */
export type DisclaimerKind = "annotation" | "rewrite" | "summary";

/** Props of {@link Disclaimer}. */
export interface DisclaimerProps {
  /** The text it accompanies. */
  kind: DisclaimerKind;
}

const WHAT: Record<DisclaimerKind, string> = {
  annotation: "This explanation was written by an AI model",
  rewrite: "This plain-English version was written by an AI model",
  summary: "This summary was written by an AI model",
};

/**
 * A visible warning that text was written by an AI model and not yet checked by a person.
 *
 * @returns The disclaimer.
 */
export function Disclaimer({ kind }: DisclaimerProps) {
  return (
    <p className="disclaimer" role="note">
      {WHAT[kind]} and has not been checked by a person yet. It may contain mistakes: check
      anything important against the original paper.
    </p>
  );
}
