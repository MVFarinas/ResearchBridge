import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { LookupResult } from "@/components/LookupResult";
import { Pagination } from "@/components/Pagination";
import { SearchForm } from "@/components/SearchForm";
import { parseSearchParams } from "@/lib/search-params";
import { syntheticResult } from "@/test/fixtures";

describe("SearchForm", () => {
  it("is a GET form to /search prefilled from the current search", () => {
    const query = parseSearchParams({ q: "sleep", type: "review", sort: "newest", year_from: "2020" });
    const { container } = render(<SearchForm query={query} />);
    const form = container.querySelector("form");
    expect(form).toHaveAttribute("action", "/search");
    expect(form).toHaveAttribute("method", "get");
    expect(screen.getByRole("searchbox", { name: "Search papers" })).toHaveValue("sleep");
    expect(screen.getByRole("checkbox", { name: "Reviews" })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: "Articles" })).not.toBeChecked();
    expect(screen.getByRole("combobox", { name: "Sort by" })).toHaveValue("newest");
    expect(screen.getByRole("spinbutton", { name: "From year" })).toHaveValue(2020);
  });
});

describe("Pagination", () => {
  it("renders nothing for a single page and links neighbours otherwise", () => {
    const { container, rerender } = render(
      <Pagination query={parseSearchParams({ q: "x" })} hasNext={false} />,
    );
    expect(container).toBeEmptyDOMElement();
    rerender(<Pagination query={parseSearchParams({ q: "x", page: "2" })} hasNext />);
    expect(screen.getByRole("link", { name: "Previous page" })).toHaveAttribute("href", "/search?q=x");
    expect(screen.getByRole("link", { name: "Next page" })).toHaveAttribute(
      "href",
      "/search?q=x&page=3",
    );
  });
});

describe("LookupResult", () => {
  it("shows 'not available here' with outbound links", () => {
    render(
      <LookupResult
        result={{
          outcome: "not_available",
          message: "Synthetic: not in PubMed Central.",
          links: { doi: "https://doi.org/10.9999/x", scholar: null, pubmed: null },
          licence_code: "TDM",
        }}
      />,
    );
    expect(screen.getByRole("status")).toHaveTextContent("Synthetic: not in PubMed Central.");
    expect(screen.getByText("Licence recorded by PubMed Central: TDM.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Read original paper" })).toHaveAttribute(
      "href",
      "https://doi.org/10.9999/x",
    );
  });

  it("lists candidates for a title", () => {
    render(
      <LookupResult
        result={{
          outcome: "candidates",
          message: "Several papers may match that title.",
          search: {
            query: "synthetic",
            page: 1,
            per_page: 10,
            corpus: { total: 1, results: [syntheticResult()] },
            openalex: {
              status: "refused",
              notice: "Synthetic notice: OpenAlex declined.",
              as_of: null,
              stale: false,
              total: 0,
              results: [],
              has_key: false,
            },
          },
        }}
      />,
    );
    expect(screen.getByRole("heading", { name: "Possible matches" })).toBeInTheDocument();
    expect(screen.getByText("Synthetic notice: OpenAlex declined.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Synthetic test paper" })).toBeInTheDocument();
  });
});
