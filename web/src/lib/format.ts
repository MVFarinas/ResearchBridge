/**
 * Formatting helpers for dates, author lists and availability labels.
 */
import type { Availability, GenerationStatus } from "@/lib/api/types";

const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

/**
 * Format an ISO 8601 date of any precision for readers, in UTC.
 *
 * @param value - `YYYY`, `YYYY-MM`, `YYYY-MM-DD` or a full timestamp.
 * @returns e.g. "13 October 2026", "May 2024" or "2024"; "" for empty or unparsable input.
 */
export function formatDate(value: string | null | undefined): string {
  const match = /^(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?/.exec(value ?? "");
  if (!match) return "";
  const [, year, month, day] = match;
  const monthName = month ? MONTHS[Number(month) - 1] : undefined;
  if (!monthName) return year ?? "";
  if (!day) return `${monthName} ${year}`;
  return `${Number(day)} ${monthName} ${year}`;
}

/**
 * Join author names, shortening long lists.
 *
 * @param names - Author names in order.
 * @param max - How many to show before "et al.".
 * @returns e.g. "A, B and C" or "A, B, C et al.".
 */
export function formatAuthors(names: string[], max = 3): string {
  if (names.length === 0) return "";
  if (names.length > max) return `${names.slice(0, max).join(", ")} et al.`;
  if (names.length === 1) return names[0] ?? "";
  return `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`;
}

/** Reader-facing label and explanation of an availability tag. */
export interface AvailabilityLabel {
  /** Short label for the tag. */
  label: string;
  /** One-sentence explanation. */
  description: string;
}

/**
 * The label of an availability tag.
 *
 * A "plain-English available" paper whose rewrite has not been generated is
 * labelled as such: the tag says what the licence allows, and the label never
 * claims a rewrite exists when it does not.
 *
 * @param availability - The tag.
 * @param rewriteStatus - The rewrite's status, for corpus papers.
 * @returns Label and description.
 */
export function availabilityLabel(
  availability: Availability,
  rewriteStatus: GenerationStatus | null = null,
): AvailabilityLabel {
  switch (availability) {
    case "plain_english_available":
      return rewriteStatus === "available"
        ? {
            label: "Plain English available",
            description: "Read a plain-English version beside the original.",
          }
        : {
            label: "Plain English permitted (not written yet)",
            description:
              "The licence allows a plain-English version; it has not been generated yet. The original is here.",
          };
    case "original_annotations_only":
      return {
        label: "Original + explanations",
        description:
          "The licence allows showing the original, with explanations, but not rewriting it.",
      };
    case "may_be_available":
      return {
        label: "May be available: request it",
        description:
          "Reported as openly licensed elsewhere. Look it up to check the licence at its source.",
      };
    case "original_elsewhere":
      return {
        label: "Original elsewhere",
        description: "Not available here. Read it at the publisher.",
      };
  }
}
