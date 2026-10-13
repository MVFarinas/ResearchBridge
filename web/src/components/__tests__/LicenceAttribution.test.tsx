import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { LicenceAttribution, LicenceLine } from "@/components/LicenceAttribution";
import { syntheticPaper } from "@/test/fixtures";

describe("LicenceAttribution", () => {
  it("credits the authors, links the licence and acknowledges NLM", () => {
    render(<LicenceAttribution paper={syntheticPaper()} />);
    const block = screen.getByRole("region", { name: "Licence and attribution" });
    expect(block).toHaveTextContent("“Synthetic test paper” by Ada Synthetic and Bo Example");
    const licenceLinks = screen.getAllByRole("link", { name: "CC BY 4.0" });
    expect(licenceLinks[0]).toHaveAttribute("href", "https://creativecommons.org/licenses/by/4.0/");
    expect(licenceLinks[0]).toHaveAttribute("rel", expect.stringContaining("license"));
    expect(screen.getByText("© 2024 Synthetic et al")).toBeInTheDocument();
    expect(block).toHaveTextContent("Use does not imply endorsement by NLM.");
    expect(block).toHaveTextContent("Any plain-English version published here is released under");
  });

  it("states non-commercial terms and omits the output licence when rewriting is not allowed", () => {
    const paper = syntheticPaper({
      licence: { ...syntheticPaper().licence, label: "CC BY-NC-ND 4.0", non_commercial: true },
      permissions: { can_display: true, can_rewrite: false, output_licence: null },
    });
    render(<LicenceAttribution paper={paper} />);
    expect(screen.getByText("The licence allows non-commercial use only.")).toBeInTheDocument();
    expect(screen.queryByText(/plain-English version published here/)).not.toBeInTheDocument();
  });

  it("summarises the licence in one line", () => {
    render(
      <LicenceLine
        paper={syntheticPaper({
          permissions: { can_display: true, can_rewrite: false, output_licence: null },
        })}
      />,
    );
    expect(screen.getByText(/not a rewritten version/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Attribution and source" })).toHaveAttribute(
      "href",
      "#attribution",
    );
  });
});
