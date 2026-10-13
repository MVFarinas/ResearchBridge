import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { CredibilityPanel, percentilePhrase } from "@/components/CredibilityPanel";
import { syntheticCredibility } from "@/test/fixtures";

describe("CredibilityPanel", () => {
  it("shows each source's figures with its 'as of' date", () => {
    render(<CredibilityPanel credibility={syntheticCredibility()} />);
    expect(screen.getByText("1.50 (1.00 = world average)")).toBeInTheDocument();
    expect(screen.getByText(/top 10% of papers in its field and year/)).toBeInTheDocument();
    expect(screen.getByText("1.25 (provisional)")).toBeInTheDocument();
    expect(screen.getByText(/as of 13 October 2026/)).toBeInTheDocument();
    expect(screen.getByText(/as of 12 October 2026/)).toBeInTheDocument();
    expect(screen.getByText(/as of 11 October 2026/)).toBeInTheDocument();
    expect(screen.getByText("None recorded.")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Citations per year: 2025: 4, 2026: 8" })).toBeInTheDocument();
  });

  it("lists notices and flags retraction and expressions of concern", () => {
    const credibility = syntheticCredibility({
      crossref: {
        ...syntheticCredibility().crossref,
        notices: [
          {
            kind: "expression_of_concern",
            label: "Expression of concern",
            source: "retraction-watch",
            notice_doi: "10.9999/notice",
            notice_url: "https://doi.org/10.9999/notice",
            date: "2021-04-01",
            retraction_watch_record: "1",
          },
        ],
      },
      integrity: {
        retracted: true,
        retraction_source: "crossref:retraction-watch",
        retraction_date: "2022-04-30",
        expression_of_concern: true,
        corrected: false,
      },
    });
    render(<CredibilityPanel credibility={credibility} />);
    expect(screen.getByText("Retracted.")).toBeInTheDocument();
    expect(screen.getByText(/An expression of concern has been published/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Expression of concern" })).toHaveAttribute(
      "href",
      "https://doi.org/10.9999/notice",
    );
  });

  it("says when a source is unavailable rather than inventing figures", () => {
    const credibility = syntheticCredibility({
      openalex: {
        ...syntheticCredibility().openalex,
        status: "unavailable",
        as_of: null,
        message: "OpenAlex could not be reached (503).",
        metrics: null,
      },
    });
    render(<CredibilityPanel credibility={credibility} />);
    expect(screen.getByText("No citation data.")).toBeInTheDocument();
    expect(screen.getByText(/OpenAlex could not be reached/)).toBeInTheDocument();
  });

  it("handles a backend that could not be reached", () => {
    render(<CredibilityPanel credibility={null} />);
    expect(screen.getByText("These signals could not be loaded right now.")).toBeInTheDocument();
  });

  it("never mentions the journal", () => {
    const { container } = render(<CredibilityPanel credibility={syntheticCredibility()} />);
    expect(container.textContent?.toLowerCase()).not.toMatch(/journal|impact factor|predatory/);
  });
});

describe("percentilePhrase", () => {
  it("uses top-1% and top-10% flags first, then the percentile", () => {
    expect(percentilePhrase(99.5, true, true)).toContain("top 1%");
    expect(percentilePhrase(91, false, true)).toContain("top 10%");
    expect(percentilePhrase(64.7, false, false)).toBe(
      "cited more than about 64% of papers in its field and year",
    );
  });
});
