/** The availability tag shown on every search result (decisions.md §1.5). */
import type { Availability, GenerationStatus } from "@/lib/api/types";
import { availabilityLabel } from "@/lib/format";

/** Props of {@link AvailabilityTag}. */
export interface AvailabilityTagProps {
  /** The tag. */
  availability: Availability;
  /** The rewrite's status, for corpus papers. */
  rewriteStatus?: GenerationStatus | null;
}

/**
 * A labelled tag (text, not colour alone) with its explanation as a tooltip.
 *
 * @returns The tag.
 */
export function AvailabilityTag({ availability, rewriteStatus = null }: AvailabilityTagProps) {
  const { label, description } = availabilityLabel(availability, rewriteStatus);
  return (
    <span className={`tag ${availability}`} title={description}>
      {label}
    </span>
  );
}
