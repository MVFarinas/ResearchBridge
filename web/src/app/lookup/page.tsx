/**
 * The lookup page (entry point 2, decisions.md §1.5): find a paper by
 * identifier or title; eligible papers not yet here are prepared on request.
 */
import type { Metadata } from "next";

import { LookupForm } from "@/components/LookupForm";

/** Page metadata. */
export const metadata: Metadata = { title: "Look up a paper" };

/** Props Next.js passes to the page. */
interface LookupPageProps {
  /** URL parameters (`q` prefills the form). */
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

/**
 * The lookup page.
 *
 * @returns The page.
 */
export default async function LookupPage({ searchParams }: LookupPageProps) {
  const { q } = await searchParams;
  const initialQuery = (typeof q === "string" ? q : "").slice(0, 500);
  return (
    <>
      <h1>Look up a paper</h1>
      <p className="lede">
        Enter a paper&apos;s DOI, PubMed ID, PMC ID or arXiv ID, or its title. If it is here, you
        will go straight to it. If its licence allows ResearchBridge to show it, it will be
        prepared for you. Otherwise you will get a link to read it at the publisher.
      </p>
      <LookupForm initialQuery={initialQuery} />
    </>
  );
}
