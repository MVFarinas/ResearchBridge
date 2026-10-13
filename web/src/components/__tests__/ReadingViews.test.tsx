import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AlignedParagraphs } from "@/components/AlignedParagraphs";
import { Disclaimer } from "@/components/Disclaimer";
import { OriginalText } from "@/components/OriginalText";
import { RetractionBanner } from "@/components/RetractionBanner";
import { SummaryPanel } from "@/components/SummaryPanel";
import { syntheticPaper } from "@/test/fixtures";

describe("OriginalText", () => {
  it("renders headings, paragraphs with their IDs, and figure captions", () => {
    render(<OriginalText sections={syntheticPaper().sections} />);
    expect(screen.getByRole("heading", { level: 2, name: "Abstract" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 2, name: "1 Introduction" })).toBeInTheDocument();
    expect(screen.getByText("Synthetic body text about sleep.")).toHaveAttribute(
      "data-paragraph-id",
      "sec1-p1",
    );
    expect(screen.getByText("Synthetic caption.", { exact: false })).toBeInTheDocument();
    expect(screen.getByText(/The image not shown here/)).toBeInTheDocument();
  });

  it("renders source text as text, never as markup", () => {
    const sections = syntheticPaper().sections.map((section) => ({
      ...section,
      paragraphs: [{ id: "x", kind: "p", text: "<img src=x onerror=alert(1)> synthetic" }],
    }));
    const { container } = render(<OriginalText sections={sections} />);
    expect(container.querySelector("img")).toBeNull();
  });
});

describe("AlignedParagraphs", () => {
  it("pairs rewritten paragraphs with their originals by ID", () => {
    const { container } = render(
      <AlignedParagraphs
        paragraphs={[
          { id: "a", kind: "p", text: "Synthetic original A." },
          { id: "b", kind: "p", text: "Synthetic original B." },
        ]}
        rewritten={[{ id: "a", text: "Synthetic plain A." }]}
      />,
    );
    const rowA = container.querySelector('[data-row="a"]') as HTMLElement;
    const rowB = container.querySelector('[data-row="b"]') as HTMLElement;
    expect(rowA).toHaveClass("has-pair");
    expect(within(rowA).getByText("Synthetic plain A.")).toBeInTheDocument();
    expect(rowB).not.toHaveClass("has-pair");
    expect(within(rowB).queryByText("Plain English")).not.toBeInTheDocument();
  });
});

describe("SummaryPanel", () => {
  it("shows an honest empty state and quotes the paper's declarations", () => {
    const paper = syntheticPaper();
    render(<SummaryPanel summary={paper.summary} declarations={paper.declarations} />);
    expect(screen.getByRole("heading", { name: "Not generated yet" })).toBeInTheDocument();
    expect(screen.getByText("Synthetic: none declared.")).toBeInTheDocument();
  });
});

describe("Disclaimer and RetractionBanner", () => {
  it("says AI text has not been checked", () => {
    render(<Disclaimer kind="rewrite" />);
    expect(screen.getByRole("note")).toHaveTextContent(
      "This plain-English version was written by an AI model and has not been checked by a person yet.",
    );
  });

  it("names the source and date of a retraction", () => {
    render(<RetractionBanner source="crossref:retraction-watch" date="2010-02-06" />);
    expect(screen.getByRole("alert")).toHaveTextContent("This paper has been retracted.");
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Reported by the Retraction Watch Database (via Crossref); notice dated 6 February 2010",
    );
  });
});
