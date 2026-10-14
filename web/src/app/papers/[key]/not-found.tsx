/** The paper-level 404: the paper is unknown or its licence does not allow showing it. */
import Link from "next/link";

/**
 * The not-found page for papers.
 *
 * @returns The page.
 */
export default function PaperNotFound() {
  return (
    <>
      <h1>Paper not available here</h1>
      <p className="lede">
        ResearchBridge does not hold this paper, or its licence does not allow showing it.
      </p>
      <p>
        <Link href="/lookup">Look it up</Link> to check whether it can be added, or{" "}
        <Link href="/search">search</Link> for it.
      </p>
    </>
  );
}
