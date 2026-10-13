/**
 * Server-side client for the backend reader API.
 *
 * Only server components, server actions and route handlers call it: the API
 * address (`RB_API_URL`) is never sent to browsers. The incoming request's
 * `X-Forwarded-For` is passed on so the backend can rate-limit per reader when
 * it is configured to trust this server as a proxy (`RB_API_NUM_PROXIES`).
 */
import { headers } from "next/headers";

/** Default API address for local development. */
export const DEFAULT_API_URL = "http://127.0.0.1:8000";
/** How long to wait for the backend before giving up, in milliseconds. */
const TIMEOUT_MS = 15_000;

/** An API call that did not succeed. */
export class ApiError extends Error {
  /** The HTTP status, or 0 when the backend could not be reached. */
  readonly status: number;

  /**
   * Create the error.
   *
   * @param message - What went wrong.
   * @param status - The HTTP status (0 for a network failure).
   */
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

/**
 * The backend API's base URL, without a trailing slash.
 *
 * @returns `RB_API_URL`, or the local development default.
 */
export function apiBaseUrl(): string {
  return (process.env.RB_API_URL || DEFAULT_API_URL).replace(/\/+$/, "");
}

/**
 * Build an API URL from a path and query parameters.
 *
 * @param path - Path below `/api/v1/`, e.g. `search/`.
 * @param params - Query parameters; empty values are left out, arrays repeat the key.
 * @returns The absolute URL.
 */
export function apiUrl(
  path: string,
  params: Record<string, string | string[] | undefined> = {},
): string {
  const url = new URL(`${apiBaseUrl()}/api/v1/${path.replace(/^\/+/, "")}`);
  for (const [name, value] of Object.entries(params)) {
    for (const item of Array.isArray(value) ? value : [value]) {
      if (item !== undefined && item !== "") url.searchParams.append(name, item);
    }
  }
  return url.toString();
}

/**
 * Headers forwarded to the backend: JSON, plus the reader's forwarded address.
 *
 * @returns Request headers.
 */
async function forwardedHeaders(): Promise<Record<string, string>> {
  const result: Record<string, string> = { Accept: "application/json" };
  // Outside a request (e.g. at build time) there are no incoming headers.
  try {
    const incoming = await headers();
    const forwarded = incoming.get("x-forwarded-for");
    if (forwarded) result["X-Forwarded-For"] = forwarded;
  } catch {
    // No request scope: nothing to forward.
  }
  return result;
}

/**
 * Send one request and decode its JSON body.
 *
 * @param url - Absolute API URL.
 * @param init - Fetch options.
 * @returns The HTTP status and decoded body.
 * @throws {ApiError} When the backend cannot be reached or does not answer JSON.
 */
async function send<T>(url: string, init: RequestInit): Promise<{ status: number; data: T }> {
  let response: Response;
  try {
    response = await fetch(url, { ...init, signal: AbortSignal.timeout(TIMEOUT_MS) });
  } catch {
    throw new ApiError("The ResearchBridge service could not be reached.", 0);
  }
  // Every API response, errors included, is JSON; anything else is a fault.
  try {
    return { status: response.status, data: (await response.json()) as T };
  } catch {
    throw new ApiError(`Unexpected response from the API (HTTP ${response.status}).`, response.status);
  }
}

/**
 * GET an API resource.
 *
 * @param path - Path below `/api/v1/`.
 * @param params - Query parameters.
 * @param revalidate - Seconds Next.js may reuse the response (0: never cached).
 * @returns The decoded body, or null for 404.
 * @throws {ApiError} For any other non-success status or a network failure.
 */
export async function apiGet<T>(
  path: string,
  params: Record<string, string | string[] | undefined> = {},
  revalidate = 0,
): Promise<T | null> {
  const caching: RequestInit =
    revalidate > 0 ? { next: { revalidate } } as RequestInit : { cache: "no-store" };
  const { status, data } = await send<T>(apiUrl(path, params), {
    ...caching,
    headers: await forwardedHeaders(),
  });
  if (status === 404) return null;
  if (status < 200 || status >= 300) {
    throw new ApiError(`The API answered HTTP ${status}.`, status);
  }
  return data;
}

/**
 * POST JSON to an API endpoint.
 *
 * @param path - Path below `/api/v1/`.
 * @param body - The JSON body.
 * @returns The HTTP status and decoded body (non-success statuses included).
 * @throws {ApiError} When the backend cannot be reached.
 */
export async function apiPost<T>(path: string, body: unknown): Promise<{ status: number; data: T }> {
  return send<T>(apiUrl(path), {
    method: "POST",
    cache: "no-store",
    headers: { ...(await forwardedHeaders()), "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}
