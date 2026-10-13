"use client";

/** Re-renders the current page from the server at an interval (used while a paper is prepared). */
import { useRouter } from "next/navigation";
import { useEffect } from "react";

/** Props of {@link AutoRefresh}. */
export interface AutoRefreshProps {
  /** Seconds between refreshes. */
  seconds: number;
}

/**
 * Refreshes the server-rendered page every `seconds` while mounted. Renders nothing.
 *
 * @returns Null.
 */
export function AutoRefresh({ seconds }: AutoRefreshProps) {
  const router = useRouter();
  useEffect(() => {
    const timer = window.setInterval(() => router.refresh(), seconds * 1000);
    return () => window.clearInterval(timer);
  }, [router, seconds]);
  return null;
}
