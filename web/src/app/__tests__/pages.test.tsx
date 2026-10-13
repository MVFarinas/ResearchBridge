import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { apiGet, notFound, redirect } = vi.hoisted(() => ({
  apiGet: vi.fn(),
  notFound: vi.fn(() => {
    throw new Error("NOT_FOUND");
  }),
  redirect: vi.fn((url: string) => {
    throw new Error(`REDIRECT ${url}`);
  }),
}));
vi.mock("@/lib/api/client", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api/client")>()),
  apiGet,
}));
vi.mock("next/navigation", () => ({
  notFound,
  redirect,
  useRouter: () => ({ refresh: vi.fn() }),
}));
// The credibility slot is an async server component; the page test replaces it.
vi.mock("@/components/CredibilitySlot", () => ({
  CredibilitySlot: () => <p>Synthetic credibility slot</p>,
}));
vi.mock("@recogito/text-annotator/text-annotator.css", () => ({}));

import AnnotationsDemoPage from "@/app/dev/annotations-demo/page";
import RequestPage from "@/app/lookup/requests/[id]/page";
import MethodologyPage from "@/app/methodology/page";
import PaperPage, { generateMetadata } from "@/app/papers/[key]/page";
import SearchPage from "@/app/search/page";
import { syntheticPaper, syntheticResult } from "@/test/fixtures";

beforeEach(() => {
  apiGet.mockReset();
});

afterEach(() => {
  vi.unstubAllEnvs();
});

/**
 * Render the paper page for a synthetic paper.
 *
 * @param view - The `view` URL parameter.
 * @param overrides - Paper fields to replace.
 */
async function renderPaper(view?: string, overrides = {}) {
  apiGet.mockResolvedValue(syntheticPaper(overrides));
  render(
    await PaperPage({
      params: Promise.resolve({ key: "PMC900000001" }),
      searchParams: Promise.resolve(view ? { view } : {}),
    }),
  );
}

describe("paper page", () => {
  it("opens on the original with licence, links, panels and an honest note", async () => {
    await renderPaper();
    expect(screen.getByRole("heading", { level: 1, name: "Synthetic test paper" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Original + explanations" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(screen.getByText("Synthetic body text about sleep.")).toBeInTheDocument();
    expect(screen.getByText("No explanations have been written for this paper yet.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Read original paper" })).toHaveAttribute(
      "href",
      "https://doi.org/10.9999/synthetic.1",
    );
    expect(screen.getByRole("link", { name: "Find on Google Scholar" })).toHaveAttribute(
      "href",
      expect.stringMatching(/^https:\/\/scholar\.google\.com\/scholar\?q=/),
    );
    expect(screen.getByRole("region", { name: "Licence and attribution" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Not generated yet" })).toBeInTheDocument();
    expect(screen.getByText("Synthetic credibility slot")).toBeInTheDocument();
    expect(apiGet).toHaveBeenCalledWith("papers/PMC900000001/", {}, 300);
  });

  it("shows an empty state, not invented text, in the plain-English view", async () => {
    await renderPaper("plain");
    expect(
      screen.getByRole("heading", { name: "Plain-English version not written yet" }),
    ).toBeInTheDocument();
    expect(screen.queryByText("Synthetic body text about sleep.")).not.toBeInTheDocument();
    // The licence block is on every view.
    expect(screen.getByRole("region", { name: "Licence and attribution" })).toBeInTheDocument();
  });

  it("explains a paper whose licence forbids a rewrite", async () => {
    await renderPaper("plain", {
      rewrite: { status: "not_permitted", reason: "Synthetic: no derivatives." },
    });
    expect(screen.getByRole("heading", { name: "No plain-English version for this paper" })).toBeInTheDocument();
    expect(screen.getByText("Synthetic: no derivatives.")).toBeInTheDocument();
  });

  it("shows the retraction banner and withheld parts", async () => {
    await renderPaper(undefined, {
      retraction: { is_retracted: true, source: "pmc:is_retracted", date: null },
      withheld: { paragraphs: 0, figures: 2 },
    });
    expect(screen.getByRole("alert")).toHaveTextContent("This paper has been retracted.");
    expect(screen.getByText(/2 figures or tables are not shown/)).toBeInTheDocument();
  });

  it("returns 404 for unknown papers", async () => {
    apiGet.mockResolvedValue(null);
    await expect(
      PaperPage({ params: Promise.resolve({ key: "PMC0" }), searchParams: Promise.resolve({}) }),
    ).rejects.toThrow("NOT_FOUND");
  });

  it("publishes citation metadata for indexing", async () => {
    apiGet.mockResolvedValue(syntheticPaper());
    const metadata = await generateMetadata({
      params: Promise.resolve({ key: "PMC900000001" }),
      searchParams: Promise.resolve({}),
    });
    expect(metadata.title).toBe("Synthetic test paper");
    expect(metadata.description).toBe("Synthetic abstract text.");
    expect(metadata.alternates?.canonical).toBe("/papers/PMC900000001");
    expect(metadata.other).toMatchObject({
      citation_title: "Synthetic test paper",
      citation_author: ["Ada Synthetic", "Bo Example"],
      citation_doi: "10.9999/synthetic.1",
      citation_publication_date: "2024/05/01",
    });
  });
});

describe("search page", () => {
  it("shows corpus and OpenAlex sections with the OpenAlex notice", async () => {
    apiGet.mockResolvedValue({
      query: "sleep",
      page: 1,
      per_page: 10,
      corpus: { total: 1, results: [syntheticResult()] },
      openalex: {
        status: "refused",
        notice: "Synthetic: OpenAlex declined. Showing papers from ResearchBridge only.",
        as_of: null,
        stale: false,
        total: 0,
        results: [],
        has_key: false,
      },
    });
    render(await SearchPage({ searchParams: Promise.resolve({ q: "sleep" }) }));
    expect(screen.getByRole("heading", { name: "Readable on ResearchBridge" })).toBeInTheDocument();
    expect(screen.getByText(/Showing papers from ResearchBridge only/)).toBeInTheDocument();
    expect(apiGet).toHaveBeenCalledWith("search/", expect.objectContaining({ q: "sleep" }));
  });

  it("shows only the form without a query, and an error when the API fails", async () => {
    render(await SearchPage({ searchParams: Promise.resolve({}) }));
    expect(apiGet).not.toHaveBeenCalled();
    apiGet.mockRejectedValue(new Error("synthetic"));
    render(await SearchPage({ searchParams: Promise.resolve({ q: "x" }) }));
    expect(screen.getByRole("alert")).toHaveTextContent("The search failed.");
  });
});

describe("lookup request page", () => {
  it("shows a preparing request and redirects a ready one", async () => {
    const base = {
      id: "123e4567-e89b-42d3-a456-426614174000",
      message: "Synthetic: being prepared.",
      pmcid: "PMC900000001",
      created_at: "2026-10-13T12:00:00Z",
      links: { doi: null },
    };
    apiGet.mockResolvedValueOnce({ ...base, status: "preparing", paper: null });
    render(await RequestPage({ params: Promise.resolve({ id: base.id }) }));
    expect(screen.getByRole("heading", { name: "Preparing this paper" })).toBeInTheDocument();
    apiGet.mockResolvedValueOnce({ ...base, status: "ready", paper: { key: "PMC900000001", title: "t" } });
    await expect(RequestPage({ params: Promise.resolve({ id: base.id }) })).rejects.toThrow(
      "REDIRECT /papers/PMC900000001",
    );
  });

  it("rejects malformed IDs without calling the API", async () => {
    await expect(RequestPage({ params: Promise.resolve({ id: "../etc" }) })).rejects.toThrow(
      "NOT_FOUND",
    );
    expect(apiGet).not.toHaveBeenCalled();
  });
});

describe("methodology and the development demo", () => {
  it("says the benchmark is pending and shows no results", () => {
    render(<MethodologyPage />);
    expect(screen.getByRole("status")).toHaveTextContent("The faithfulness benchmark is pending.");
    expect(document.body.textContent).not.toMatch(/\d+(\.\d+)?%/);
  });

  it("labels the demo as synthetic in development", () => {
    vi.stubEnv("NODE_ENV", "development");
    render(<AnnotationsDemoPage />);
    expect(screen.getByText(/SYNTHETIC DEMO, development only/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Side-by-side layout" })).toBeInTheDocument();
  });

  it("is unreachable in production", () => {
    vi.stubEnv("NODE_ENV", "production");
    expect(() => AnnotationsDemoPage()).toThrow("NOT_FOUND");
  });
});
