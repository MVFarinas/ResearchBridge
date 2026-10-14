/** Links switching between the plain-English and original views (work without JavaScript). */
import Link from "next/link";

import type { PaperView } from "@/lib/paper-view";

/** Props of {@link ViewTabs}. */
export interface ViewTabsProps {
  /** The paper key. */
  paperKey: string;
  /** The view shown. */
  current: PaperView;
}

/**
 * The view switcher; the current view is marked with `aria-current`.
 *
 * @returns The navigation.
 */
export function ViewTabs({ paperKey, current }: ViewTabsProps) {
  const views: { view: PaperView; label: string }[] = [
    { view: "plain", label: "Plain English" },
    { view: "original", label: "Original + explanations" },
  ];
  return (
    <nav className="view-tabs" aria-label="Reading view">
      {views.map(({ view, label }) => (
        <Link
          key={view}
          href={`/papers/${paperKey}?view=${view}`}
          aria-current={current === view ? "page" : undefined}
          scroll={false}
        >
          {label}
        </Link>
      ))}
    </nav>
  );
}
