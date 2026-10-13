/**
 * The methodology page. The faithfulness benchmark (decisions.md §1.4) has not
 * been run yet, so the page says so and describes what it will measure; no
 * results are shown until they exist.
 */
import type { Metadata } from "next";

/** Page metadata. */
export const metadata: Metadata = { title: "Methodology" };

/**
 * The methodology page.
 *
 * @returns The page.
 */
export default function MethodologyPage() {
  return (
    <>
      <h1>Methodology</h1>
      <div className="notice warn" role="status">
        <p>
          <strong>The faithfulness benchmark is pending.</strong> No results have been published
          yet, and no plain-English versions are shown until it is done.
        </p>
      </div>
      <h2>What the benchmark will measure</h2>
      <p>
        Before any plain-English version is published, ResearchBridge will test how faithfully AI
        rewrites keep to the original papers. About twelve biomedical papers, across randomised
        trials, observational studies, laboratory work and reviews, will be rewritten, and each
        rewrite split into its individual claims.
      </p>
      <p>At least two raters with domain knowledge will check every claim against the source for:</p>
      <ul>
        <li>whether the source supports it, does not support it, or contradicts it;</li>
        <li>findings stated more broadly than the study shows;</li>
        <li>hedges and limitations that were dropped;</li>
        <li>associations reworded as causes.</li>
      </ul>
      <p>
        Human-written plain-language versions of the same passages will be rated the same way,
        and an automatic judge will be compared against the human raters to learn whether
        faithfulness can be checked automatically. The model and settings used for rewriting will
        be chosen from these results, not in advance.
      </p>
      <h2>What is shown here today</h2>
      <ul>
        <li>
          Only papers whose licence allows it, with the licence and credit to the authors on
          every page.
        </li>
        <li>
          Citation counts and retraction or expression-of-concern notices from open sources, each
          with the date it was retrieved. Nothing is said about the journal a paper appeared in.
        </li>
      </ul>
    </>
  );
}
