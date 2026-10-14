/**
 * The home page: what ResearchBridge is (and, honestly, what it does not do
 * yet), the search box, and what the availability tags mean.
 */
import Link from "next/link";

import { AvailabilityTag } from "@/components/AvailabilityTag";
import { SearchForm } from "@/components/SearchForm";
import type { Availability } from "@/lib/api/types";
import { availabilityLabel } from "@/lib/format";

const TAGS: Availability[] = [
  "plain_english_available",
  "original_annotations_only",
  "may_be_available",
  "original_elsewhere",
];

/**
 * The home page.
 *
 * @returns The page.
 */
export default function HomePage() {
  return (
    <>
      <h1>Openly licensed research papers, made readable</h1>
      <p className="lede">
        ResearchBridge will put openly licensed research papers beside a faithful plain-English
        version, with explanations of hard passages. Today you can search the scholarly record,
        read the original text of papers whose licence allows it, with neutral context to judge
        them by, and look up a paper you have heard about.
      </p>
      <div className="notice info" role="note">
        <p>
          <strong>Plain-English versions and explanations are not published yet.</strong> They
          will appear only after a benchmark has tested how faithful they are; see the{" "}
          <Link href="/methodology">methodology</Link>.
        </p>
      </div>
      <SearchForm />
      <p>
        Have a DOI, PubMed ID or PMC ID? <Link href="/lookup">Look up a paper</Link>.
      </p>
      <h2 id="what-the-labels-mean">What the labels on results mean</h2>
      <ul className="legend">
        {TAGS.map((tag) => (
          <li key={tag}>
            <AvailabilityTag availability={tag} describe={false} />{" "}
            {availabilityLabel(tag).description}
          </li>
        ))}
      </ul>
    </>
  );
}
