import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AvailabilityTag } from "@/components/AvailabilityTag";

describe("AvailabilityTag", () => {
  it("carries its explanation as hidden text for screen readers, not only a tooltip", () => {
    render(<AvailabilityTag availability="original_elsewhere" />);
    const tag = screen.getByText("Original elsewhere");
    expect(tag).toHaveAttribute("title", "Not available here. Read it at the publisher.");
    expect(tag).toHaveTextContent("Original elsewhere. Not available here. Read it at the publisher.");
    expect(screen.getByText(/Not available here/, { selector: ".visually-hidden" })).toBeInTheDocument();
  });

  it("leaves the hidden explanation out where it is shown beside the tag", () => {
    render(<AvailabilityTag availability="original_elsewhere" describe={false} />);
    expect(screen.getByText("Original elsewhere")).toHaveTextContent(/^Original elsewhere$/);
  });
});
