import { beforeEach, describe, expect, it, vi } from "vitest";

const { apiPost, redirect } = vi.hoisted(() => ({
  apiPost: vi.fn(),
  redirect: vi.fn((url: string) => {
    throw new Error(`REDIRECT ${url}`);
  }),
}));
vi.mock("@/lib/api/client", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api/client")>()),
  apiPost,
}));
vi.mock("next/navigation", () => ({ redirect }));

import { type LookupState, lookupAction } from "@/app/lookup/actions";
import { ApiError } from "@/lib/api/client";

const INITIAL: LookupState = { query: "", result: null, error: "" };

/**
 * A form with a query field.
 *
 * @param query - The value.
 * @returns The form data.
 */
function form(query: string): FormData {
  const data = new FormData();
  data.set("query", query);
  return data;
}

beforeEach(() => {
  apiPost.mockReset();
  redirect.mockClear();
});

describe("lookupAction", () => {
  it("asks for input when the query is empty, without calling the API", async () => {
    const state = await lookupAction(INITIAL, form("   "));
    expect(state.error).toMatch(/Enter a DOI/);
    expect(apiPost).not.toHaveBeenCalled();
  });

  it("redirects to a paper held here", async () => {
    apiPost.mockResolvedValue({
      status: 200,
      data: { outcome: "in_corpus", message: "", paper: { key: "PMC1", title: "t" } },
    });
    await expect(lookupAction(INITIAL, form("10.9999/x"))).rejects.toThrow("REDIRECT /papers/PMC1");
    expect(apiPost).toHaveBeenCalledWith("lookup/", { query: "10.9999/x" });
  });

  it("redirects to the status page of a queued paper", async () => {
    apiPost.mockResolvedValue({
      status: 202,
      data: { outcome: "queued", message: "", request: { id: "abc" } },
    });
    await expect(lookupAction(INITIAL, form("PMC1"))).rejects.toThrow(
      "REDIRECT /lookup/requests/abc",
    );
  });

  it("returns other outcomes for the form to show", async () => {
    const data = { outcome: "not_available", message: "Synthetic", links: {} };
    apiPost.mockResolvedValue({ status: 200, data });
    await expect(lookupAction(INITIAL, form("10.9999/y"))).resolves.toEqual({
      query: "10.9999/y",
      result: data,
      error: "",
    });
  });

  it("turns validation errors, rate limits and outages into messages", async () => {
    apiPost.mockResolvedValueOnce({ status: 400, data: { query: ["Synthetic validation error"] } });
    expect((await lookupAction(INITIAL, form("ab"))).error).toBe("Synthetic validation error");
    apiPost.mockResolvedValueOnce({ status: 429, data: { detail: "throttled" } });
    expect((await lookupAction(INITIAL, form("abc"))).error).toMatch(/Too many lookups/);
    apiPost.mockRejectedValueOnce(new ApiError("Unreachable.", 0));
    expect((await lookupAction(INITIAL, form("abc"))).error).toBe("Unreachable. Please try again.");
  });
});
