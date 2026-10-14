"use server";

/**
 * The lookup server action: sends the reader's query to the backend and
 * redirects to the paper (when held here) or to the request's status page
 * (when it was queued). Other outcomes are returned for the form to show.
 */
import { redirect } from "next/navigation";

import { ApiError, apiPost } from "@/lib/api/client";
import type { LookupResponse } from "@/lib/api/types";

/** What the lookup form shows after a submission. */
export interface LookupState {
  /** The query submitted. */
  query: string;
  /** The backend's answer, when there is one to show. */
  result: LookupResponse | null;
  /** A reader-facing error, or "". */
  error: string;
}

/** Error shown when the query is empty (not exported: a "use server" module exports only actions). */
const EMPTY_QUERY_ERROR = "Enter a DOI, PubMed ID, PMC ID, arXiv ID or a title.";

/**
 * Look a paper up.
 *
 * @param _previous - The form's previous state (unused).
 * @param formData - The submitted form, with a `query` field.
 * @returns The state to show; never returns for papers held here or queued (redirects).
 */
export async function lookupAction(_previous: LookupState, formData: FormData): Promise<LookupState> {
  const query = String(formData.get("query") ?? "").trim();
  if (!query) return { query, result: null, error: EMPTY_QUERY_ERROR };

  // Ask the backend; translate transport and validation failures into messages.
  let status: number;
  let data: LookupResponse | Record<string, string[]>;
  try {
    ({ status, data } = await apiPost<LookupResponse | Record<string, string[]>>("lookup/", {
      query,
    }));
  } catch (error) {
    const message = error instanceof ApiError ? error.message : "The lookup failed.";
    return { query, result: null, error: `${message} Please try again.` };
  }
  if (status === 429) {
    return {
      query,
      result: null,
      error: "Too many lookups in a short time. Please wait a minute and try again.",
    };
  }
  if (status === 400) {
    const messages = Object.values(data as Record<string, string[]>).flat();
    return { query, result: null, error: messages[0] ?? EMPTY_QUERY_ERROR };
  }

  // Held here, or queued: go straight to the paper or to the request's status.
  const result = data as LookupResponse;
  if (result.outcome === "in_corpus" && result.paper) redirect(`/papers/${result.paper.key}`);
  if (result.outcome === "queued" && result.request) {
    redirect(`/lookup/requests/${result.request.id}`);
  }
  return { query, result, error: "" };
}
