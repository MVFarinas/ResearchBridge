/** The availability tag shown on every search result (decisions.md §1.5). */
import type { Availability, GenerationStatus } from "@/lib/api/types";
import { availabilityLabel } from "@/lib/format";

/** Props of {@link AvailabilityTag}. */
export interface AvailabilityTagProps {
  /** The tag. */
  availability: Availability;
  /** The rewrite's status, for corpus papers. */
  rewriteStatus?: GenerationStatus | null;
  /**
   * Whether to include the explanation as visually hidden text for screen
   * readers (default true). Turn it off where the explanation is already
   * shown beside the tag, as in the home page's legend.
   */
  describe?: boolean;
}

/**
 * A labelled tag (text, not colour alone). The explanation is a tooltip for
 * pointer users and hidden text for screen readers; keyboard and touch users
 * reach it through the legend linked from the search results.
 *
 * @returns The tag.
 */
export function AvailabilityTag({
  availability,
  rewriteStatus = null,
  describe = true,
}: AvailabilityTagProps) {
  const { label, description } = availabilityLabel(availability, rewriteStatus);
  return (
    <span className={`tag ${availability}`} title={description}>
      {label}
      {describe ? <span className="visually-hidden">. {description}</span> : null}
    </span>
  );
}
