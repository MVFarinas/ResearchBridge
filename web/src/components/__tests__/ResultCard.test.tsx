import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ResultCard } from "@/components/ResultCard";
import { HIGHLIGHT_START as S, HIGHLIGHT_STOP as E } from "@/lib/highlight";
import { syntheticResult } from "@/test/fixtures";

describe("ResultCard", () => {
  it("links a corpus paper to its page, with an honest tag and highlighted snippet", () => {
    render(
      <ul>
        <ResultCard result={syntheticResult({ snippet: `about ${S}sleep${E}` })} />
      </ul>,
    );
    expect(screen.getByRole("link", { name: "Synthetic test paper" })).toHaveAttribute(
      "href",
      "/papers/PMC900000001",
    );
    expect(screen.getByText("Plain English permitted (not written yet)")).toBeInTheDocument();
    expect(screen.queryByText("Plain English available")).not.toBeInTheDocument();
    expect(screen.getByText("sleep").tagName).toBe("MARK");
    expect(screen.getByText("Licence: CC BY 4.0")).toBeInTheDocument();
  });

  it("routes a 'may be available' work to lookup, never to a paper page", () => {
    render(
      <ul>
        <ResultCard
          result={syntheticResult({
            origin: "openalex",
            key: null,
            availability: "may_be_available",
            rewrite_status: null,
            licence: null,
            lookup_query: "10.9999/synthetic.2",
          })}
        />
      </ul>,
    );
    expect(screen.getByRole("heading", { name: "Synthetic test paper" })).not.toContainElement(
      screen.queryByRole("link", { name: "Synthetic test paper" }),
    );
    expect(screen.getByRole("link", { name: "Check if it can be added" })).toHaveAttribute(
      "href",
      "/lookup?q=10.9999%2Fsynthetic.2",
    );
    expect(screen.getByRole("link", { name: "Read original paper" })).toHaveAttribute(
      "href",
      "https://doi.org/10.9999/synthetic.1",
    );
    expect(screen.getByRole("link", { name: "Find on Google Scholar" })).toBeInTheDocument();
  });

  it("flags retracted papers", () => {
    render(
      <ul>
        <ResultCard result={syntheticResult({ is_retracted: true })} />
      </ul>,
    );
    expect(screen.getByText("Retracted")).toBeInTheDocument();
  });
});
