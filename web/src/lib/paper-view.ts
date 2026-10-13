/**
 * Paper page helpers: which view to show and how sections are titled.
 */
import type { GenerationState, PaperDetail, Section } from "@/lib/api/types";

/** The two reading views of a paper. */
export type PaperView = "plain" | "original";

/**
 * Choose the view to render.
 *
 * The plain-English view is the default only when a rewrite exists; until
 * then papers open on the original, so readers never land on an empty view.
 *
 * @param requested - The `view` URL parameter, if any.
 * @param rewrite - The rewrite's state.
 * @returns The view.
 */
export function chooseView(requested: string | undefined, rewrite: GenerationState): PaperView {
  if (requested === "plain" || requested === "original") return requested;
  return rewrite.status === "available" ? "plain" : "original";
}

const UNTITLED: Record<string, string> = {
  abstract: "Abstract",
  ack: "Acknowledgements",
  app: "Appendix",
  notes: "Notes",
};

/**
 * The heading to show for a section, if any.
 *
 * @param section - The section.
 * @returns Its label and title, a conventional name for untitled abstracts,
 *   acknowledgements, appendices and notes, or "" for untitled containers.
 */
export function sectionHeading(section: Section): string {
  const title = [section.label, section.title].filter(Boolean).join(" ");
  if (title) return section.title.startsWith(section.label) ? section.title : title;
  return UNTITLED[section.kind] ?? "";
}

/**
 * The HTML heading level for a section (the page title is the h1).
 *
 * @param depth - Nesting depth (0 for roots).
 * @returns 2 to 5.
 */
export function headingLevel(depth: number): 2 | 3 | 4 | 5 {
  return Math.min(2 + Math.max(depth, 0), 5) as 2 | 3 | 4 | 5;
}

/**
 * Explain parts left out because their own licence differs from the paper's.
 *
 * @param withheld - Counts of withheld paragraphs and figures or tables.
 * @returns A sentence, or "" when nothing is withheld.
 */
export function withheldMessage(withheld: PaperDetail["withheld"]): string {
  const parts: string[] = [];
  if (withheld.paragraphs > 0) {
    parts.push(`${withheld.paragraphs} ${withheld.paragraphs === 1 ? "paragraph" : "paragraphs"}`);
  }
  if (withheld.figures > 0) {
    parts.push(
      `${withheld.figures} ${withheld.figures === 1 ? "figure or table" : "figures or tables"}`,
    );
  }
  if (parts.length === 0) return "";
  const total = withheld.paragraphs + withheld.figures;
  return `${parts.join(" and ")} ${total === 1 ? "is" : "are"} not shown because their own licence differs from the paper's, or is still being checked. See the original paper for them.`;
}
