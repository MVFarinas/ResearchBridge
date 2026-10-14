"use client";

/**
 * The lookup form. It posts to a server action, so it also works before
 * JavaScript has loaded; the outcome (or an error) is shown below the form.
 */
import { useActionState } from "react";

import { type LookupState, lookupAction } from "@/app/lookup/actions";
import { LookupResult } from "@/components/LookupResult";

/** Props of {@link LookupForm}. */
export interface LookupFormProps {
  /** A query to prefill (e.g. from a search result's "check" link). */
  initialQuery?: string;
}

/**
 * The lookup form and its outcome.
 *
 * @returns The form.
 */
export function LookupForm({ initialQuery = "" }: LookupFormProps) {
  const [state, formAction, pending] = useActionState<LookupState, FormData>(lookupAction, {
    query: initialQuery,
    result: null,
    error: "",
  });
  return (
    <>
      <form className="search-form" action={formAction}>
        <label htmlFor="lookup-query">DOI, PubMed ID, PMC ID, arXiv ID or title</label>
        <div className="search-row">
          <input
            id="lookup-query"
            name="query"
            type="text"
            required
            maxLength={500}
            defaultValue={state.query}
            placeholder="e.g. 10.1371/journal.pmed.1004542"
            aria-describedby={state.error ? "lookup-error" : undefined}
          />
          <button className="button" type="submit" disabled={pending}>
            {pending ? "Looking up…" : "Look up"}
          </button>
        </div>
      </form>
      {state.error ? (
        <p id="lookup-error" className="notice danger" role="alert">
          {state.error}
        </p>
      ) : null}
      {state.result ? <LookupResult result={state.result} /> : null}
    </>
  );
}
