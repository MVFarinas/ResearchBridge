/**
 * The root layout: page frame, navigation, skip link and the sources footer.
 */
import "./globals.css";

import type { Metadata, Viewport } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

/** Site-wide metadata; pages add their own titles and descriptions. */
export const metadata: Metadata = {
  title: { default: "ResearchBridge", template: "%s · ResearchBridge" },
  description:
    "Openly licensed research papers, made readable: the original beside a plain-English version, with explanations and the context to judge them.",
  metadataBase: new URL(process.env.RB_SITE_URL || "http://localhost:3000"),
};

/** Viewport settings for phones and tablets. */
export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
};

/**
 * The page frame shared by every page.
 *
 * @returns The HTML document.
 */
export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <a className="skip-link" href="#main">
          Skip to content
        </a>
        <header className="site-header">
          <div className="frame">
            <Link href="/" className="brand">
              ResearchBridge
            </Link>
            <nav className="site-nav" aria-label="Main">
              <ul>
                <li>
                  <Link href="/search">Search</Link>
                </li>
                <li>
                  <Link href="/lookup">Look up a paper</Link>
                </li>
                <li>
                  <Link href="/methodology">Methodology</Link>
                </li>
              </ul>
            </nav>
          </div>
        </header>
        <main id="main" className="frame" tabIndex={-1}>
          {children}
        </main>
        <footer className="site-footer">
          <div className="frame">
            <p>
              ResearchBridge shows only papers whose licence allows it, with credit to their
              authors on every page. Full text comes from the PubMed Central Article Datasets of
              the NIH National Library of Medicine; use does not imply endorsement by NLM.
              Citation data from OpenAlex (CC0) and NIH iCite (public domain); corrections and
              retractions from Crossref, including the Retraction Watch Database.
            </p>
            <p>
              Explanations and plain-English versions, when they appear, are written by an AI
              model and marked as such until a person has checked them.
            </p>
          </div>
        </footer>
      </body>
    </html>
  );
}
