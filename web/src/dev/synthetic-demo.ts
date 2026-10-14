/**
 * SYNTHETIC demo data for the development-only annotation demo
 * (`/dev/annotations-demo`). Nothing here is a real paper, a real
 * explanation or a real rewrite; it exists only to develop the annotation
 * layer and the side-by-side layout, and is never served in production or
 * stored anywhere.
 */
import type { RewrittenParagraph } from "@/components/AlignedParagraphs";
import type { ApiAnnotation, Section } from "@/lib/api/types";

/** Synthetic sections of a made-up paper. */
export const SYNTHETIC_SECTIONS: Section[] = [
  {
    id: "abs1",
    parent: null,
    depth: 0,
    kind: "abstract",
    title: "",
    label: "",
    figures: [],
    paragraphs: [
      {
        id: "abs1-p1",
        kind: "p",
        text:
          "SYNTHETIC TEXT. In this invented cohort, nocturnal photic exposure was associated with attenuated melatonin secretion, although residual confounding cannot be excluded.",
      },
    ],
  },
  {
    id: "sec1",
    parent: null,
    depth: 0,
    kind: "sec",
    title: "1 Introduction",
    label: "",
    figures: [],
    paragraphs: [
      {
        id: "sec1-p1",
        kind: "p",
        text:
          "SYNTHETIC TEXT. Circadian rhythms coordinate physiology across the 24-hour day; melatonin is a hormone whose release rises in darkness (café-style lighting, 💡, was not studied).",
      },
    ],
  },
];

/** Synthetic plain-English paragraphs, aligned by paragraph ID. */
export const SYNTHETIC_REWRITE: RewrittenParagraph[] = [
  {
    id: "abs1-p1",
    text:
      "SYNTHETIC REWRITE. In this made-up group of people, more light at night went along with less melatonin. Other differences between people might explain this, so it does not show that light caused it.",
  },
];

/**
 * Build a synthetic annotation on a quoted passage.
 *
 * @param id - Annotation ID suffix.
 * @param paragraphId - The paragraph.
 * @param text - The paragraph's text.
 * @param exact - The passage to quote (must occur in the text).
 * @param explanation - The synthetic explanation.
 * @param provenance - Who "wrote" it.
 * @returns The annotation in the API's shape, with code-point positions.
 */
function synthetic(
  id: string,
  paragraphId: string,
  text: string,
  exact: string,
  explanation: string,
  provenance: ApiAnnotation["provenance"],
): ApiAnnotation {
  const start = [...text.slice(0, text.indexOf(exact))].length;
  return {
    id: `urn:uuid:00000000-0000-4000-8000-${id.padStart(12, "0")}`,
    type: "Annotation",
    motivation: "describing",
    body: { type: "TextualBody", value: explanation, format: "text/plain" },
    target: {
      source: "synthetic-demo",
      selector: [
        { type: "TextQuoteSelector", exact },
        { type: "TextPositionSelector", start, end: start + [...exact].length },
      ],
    },
    paragraph_id: paragraphId,
    provenance,
    model: provenance === "human" ? null : "synthetic-demo-model",
    prompt_version: provenance === "human" ? null : "synthetic-demo",
    verified: false,
    superseded: false,
    needs_disclaimer: provenance !== "human",
    created_at: "2026-10-13T00:00:00Z",
  };
}

const ABSTRACT = SYNTHETIC_SECTIONS[0]?.paragraphs[0]?.text ?? "";
const INTRO = SYNTHETIC_SECTIONS[1]?.paragraphs[0]?.text ?? "";

/** Synthetic annotations, including one after an emoji to exercise UTF-16 conversion. */
export const SYNTHETIC_ANNOTATIONS: ApiAnnotation[] = [
  synthetic(
    "1",
    "abs1-p1",
    ABSTRACT,
    "nocturnal photic exposure",
    "SYNTHETIC EXPLANATION: light at night.",
    "llm",
  ),
  synthetic(
    "2",
    "abs1-p1",
    ABSTRACT,
    "residual confounding",
    "SYNTHETIC EXPLANATION: other differences between groups that the analysis did not remove.",
    "human",
  ),
  synthetic("3", "sec1-p1", INTRO, "was not studied", "SYNTHETIC EXPLANATION: after an emoji.", "llm"),
];
