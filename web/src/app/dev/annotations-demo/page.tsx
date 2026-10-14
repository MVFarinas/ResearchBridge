/**
 * DEVELOPMENT ONLY: a demo of the annotation layer and the side-by-side layout
 * with SYNTHETIC data. In a production build the page is a 404, so it can
 * never be reached by readers or indexed.
 */
import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { AlignedParagraphs } from "@/components/AlignedParagraphs";
import { AnnotationLayer } from "@/components/AnnotationLayer";
import { OriginalText } from "@/components/OriginalText";
import { SYNTHETIC_ANNOTATIONS, SYNTHETIC_REWRITE, SYNTHETIC_SECTIONS } from "@/dev/synthetic-demo";

/** Never indexed. */
export const metadata: Metadata = {
  title: "Synthetic annotation demo (development only)",
  robots: { index: false, follow: false },
};

/**
 * The demo page (404 in production).
 *
 * @returns The page.
 */
export default function AnnotationsDemoPage() {
  if (process.env.NODE_ENV === "production") notFound();
  return (
    <>
      <p className="demo-banner" role="note">
        SYNTHETIC DEMO, development only. This is not a real paper, and these are not real
        explanations or a real plain-English version.
      </p>
      <h1>Annotation layer demo</h1>
      <h2>Original + explanations</h2>
      <AnnotationLayer annotations={SYNTHETIC_ANNOTATIONS}>
        <OriginalText sections={SYNTHETIC_SECTIONS} />
      </AnnotationLayer>
      <h2>Side-by-side layout</h2>
      <AlignedParagraphs
        paragraphs={SYNTHETIC_SECTIONS.flatMap((section) => section.paragraphs)}
        rewritten={SYNTHETIC_REWRITE}
      />
    </>
  );
}
