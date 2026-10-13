/**
 * Loads the credibility signals for the paper page. Rendered inside Suspense,
 * so the paper text is not held up by the metadata services.
 */
import { CredibilityPanel } from "@/components/CredibilityPanel";
import { apiGet } from "@/lib/api/client";
import type { Credibility } from "@/lib/api/types";

/**
 * Seconds the signals may be reused. Short, because the panel reports
 * retraction notices; the backend caches the sources itself, with "as of" dates.
 */
export const CREDIBILITY_REVALIDATE = 60;

/** Props of {@link CredibilitySlot}. */
export interface CredibilitySlotProps {
  /** The paper key. */
  paperKey: string;
}

/**
 * Fetch and render the credibility panel; a failure shows the panel's "could not load" state.
 *
 * @returns The panel.
 */
export async function CredibilitySlot({ paperKey }: CredibilitySlotProps) {
  let credibility: Credibility | null = null;
  try {
    credibility = await apiGet<Credibility>(
      `papers/${encodeURIComponent(paperKey)}/credibility/`,
      {},
      CREDIBILITY_REVALIDATE,
    );
  } catch {
    credibility = null;
  }
  return <CredibilityPanel credibility={credibility} />;
}
