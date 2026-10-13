/**
 * The home page: what ResearchBridge is, the search box, and what the
 * availability tags mean.
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
      <h1>Read research papers in plain English</h1>
      <p className="lede">
        ResearchBridge puts openly licensed research papers beside a faithful plain-English
        version, with explanations of hard passages and neutral context to judge them by. Search
        the scholarly record, or look up a paper you have heard about.
      </p>
      <SearchForm />
      <p>
        Have a DOI, PubMed ID or PMC ID? <Link href="/lookup">Look up a paper</Link>.
      </p>
      <h2>What the labels on results mean</h2>
      <ul className="legend">
        {TAGS.map((tag) => (
          <li key={tag}>
            <AvailabilityTag availability={tag} /> {availabilityLabel(tag).description}
          </li>
        ))}
      </ul>
    </>
  );
}
