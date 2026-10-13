/** A clearly marked "nothing here yet" block, used instead of placeholder content. */
import type { ReactNode } from "react";

/** Props of {@link EmptyState}. */
export interface EmptyStateProps {
  /** Short heading. */
  title: string;
  /** Explanation and any next step. */
  children?: ReactNode;
}

/**
 * An honest empty state: says what is missing and why, never shows stand-in content.
 *
 * @returns The block.
 */
export function EmptyState({ title, children }: EmptyStateProps) {
  return (
    <div className="empty-state">
      <h3>{title}</h3>
      {children}
    </div>
  );
}
