import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("next/headers", () => ({
  headers: vi.fn(async () => new Headers({ "x-forwarded-for": "203.0.113.7" })),
}));

import { ApiError, apiGet, apiPost, apiUrl } from "@/lib/api/client";

const fetchMock = vi.fn();

beforeEach(() => {
  vi.stubGlobal("fetch", fetchMock);
  vi.stubEnv("RB_API_URL", "http://api.test:8000/");
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  fetchMock.mockReset();
});

/**
 * A JSON response.
 *
 * @param status - HTTP status.
 * @param body - JSON body.
 * @returns The response.
 */
function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("apiUrl", () => {
  it("joins the base URL, path and parameters, repeating arrays and skipping empties", () => {
    expect(apiUrl("/search/", { q: "a b", type: ["article", "review"], sort: "", page: undefined })).toBe(
      "http://api.test:8000/api/v1/search/?q=a+b&type=article&type=review",
    );
  });

  it("defaults to the local backend", () => {
    vi.stubEnv("RB_API_URL", "");
    expect(apiUrl("papers/PMC1/")).toBe("http://127.0.0.1:8000/api/v1/papers/PMC1/");
  });
});

describe("apiGet", () => {
  it("returns the body and forwards the reader's address", async () => {
    fetchMock.mockResolvedValue(json(200, { ok: true }));
    await expect(apiGet("papers/PMC1/")).resolves.toEqual({ ok: true });
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect((init.headers as Record<string, string>)["X-Forwarded-For"]).toBe("203.0.113.7");
    expect(init.cache).toBe("no-store");
  });

  it("asks Next.js to reuse responses when given a revalidation time", async () => {
    fetchMock.mockResolvedValue(json(200, {}));
    await apiGet("papers/PMC1/", {}, 300);
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit & { next?: unknown }];
    expect(init.next).toEqual({ revalidate: 300 });
  });

  it("maps 404 to null and other failures to ApiError", async () => {
    fetchMock.mockResolvedValueOnce(json(404, { detail: "no" }));
    await expect(apiGet("papers/X/")).resolves.toBeNull();
    fetchMock.mockResolvedValueOnce(json(500, { detail: "boom" }));
    await expect(apiGet("papers/X/")).rejects.toMatchObject({ status: 500 });
  });

  it("reports an unreachable backend with status 0", async () => {
    fetchMock.mockRejectedValue(new TypeError("fetch failed"));
    const error = await apiGet("search/").catch((caught: unknown) => caught);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(0);
  });

  it("refuses a non-JSON answer", async () => {
    fetchMock.mockResolvedValue(new Response("<html>", { status: 502 }));
    await expect(apiGet("search/")).rejects.toMatchObject({ status: 502 });
  });
});

describe("apiPost", () => {
  it("sends JSON and returns status and body, including errors", async () => {
    fetchMock.mockResolvedValue(json(400, { query: ["too short"] }));
    await expect(apiPost("lookup/", { query: "ab" })).resolves.toEqual({
      status: 400,
      data: { query: ["too short"] },
    });
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://api.test:8000/api/v1/lookup/");
    expect(init.method).toBe("POST");
    expect(init.body).toBe(JSON.stringify({ query: "ab" }));
  });
});
