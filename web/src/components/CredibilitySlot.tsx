/**
 * Loads the credibility signals for the paper page. Rendered inside Suspense,
 * so the paper text is not held up by the metadata services.
 */
import { CredibilityPanel } from "@/components/CredibilityPanel";
import { apiGet } from "@/lib/api/client";
import type { Credibility } from "@/lib/api/types";

/** Seconds the signals may be reused (the backend caches them too, with dates). */
const CREDIBILITY_REVALIDATE = 600;

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
