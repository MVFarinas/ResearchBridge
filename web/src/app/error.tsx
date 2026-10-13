"use client";

/** The error page shown when a page cannot be rendered (e.g. the API is down). */

/** Props Next.js passes to an error boundary. */
interface ErrorPageProps {
  /** The error (logged by Next.js on the server; not shown to readers). */
  error: Error & { digest?: string };
  /** Retry rendering the page. */
  reset: () => void;
}

/**
 * A plain apology with a retry button; no error details are shown to readers.
 *
 * @returns The page.
 */
export default function ErrorPage({ reset }: ErrorPageProps) {
  return (
    <>
      <h1>Something went wrong</h1>
      <p className="lede">This page could not be loaded. The service may be busy or restarting.</p>
      <button type="button" className="button" onClick={reset}>
        Try again
      </button>
    </>
  );
}
