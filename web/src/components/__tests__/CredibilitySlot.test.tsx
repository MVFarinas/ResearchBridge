import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { apiGet } = vi.hoisted(() => ({ apiGet: vi.fn() }));
vi.mock("@/lib/api/client", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api/client")>()),
  apiGet,
}));

import { CREDIBILITY_REVALIDATE, CredibilitySlot } from "@/components/CredibilitySlot";
import { syntheticCredibility } from "@/test/fixtures";

beforeEach(() => {
  apiGet.mockReset();
});

describe("CredibilitySlot", () => {
  it("fetches the signals with a short reuse window and renders them", async () => {
    apiGet.mockResolvedValue(syntheticCredibility());
    render(await CredibilitySlot({ paperKey: "PMC900000001" }));
    // A minute at most, so a newly recorded retraction notice shows promptly.
    expect(CREDIBILITY_REVALIDATE).toBeLessThanOrEqual(60);
    expect(apiGet).toHaveBeenCalledWith("papers/PMC900000001/credibility/", {}, CREDIBILITY_REVALIDATE);
    expect(screen.getByText(/as of 13 October 2026/)).toBeInTheDocument();
  });

  it("shows the panel's could-not-load state when the API fails", async () => {
    apiGet.mockRejectedValue(new Error("synthetic outage"));
    render(await CredibilitySlot({ paperKey: "PMC900000001" }));
    expect(screen.getByText("These signals could not be loaded right now.")).toBeInTheDocument();
  });
});
