import { describe, expect, it } from "vitest";

import type { Section } from "@/lib/api/types";
import { chooseView, headingLevel, sectionHeading, withheldMessage } from "@/lib/paper-view";

/**
 * A synthetic section.
 *
 * @param fields - Fields to set.
 * @returns The section.
 */
function section(fields: Partial<Section>): Section {
  return {
    id: "s",
    parent: null,
    depth: 0,
    kind: "sec",
    title: "",
    label: "",
    paragraphs: [],
    figures: [],
    ...fields,
  };
}

describe("chooseView", () => {
  it("opens on the original until a rewrite exists", () => {
    expect(chooseView(undefined, { status: "not_generated", reason: "" })).toBe("original");
    expect(chooseView(undefined, { status: "available", reason: "" })).toBe("plain");
  });

  it("honours an explicit choice and ignores junk", () => {
    expect(chooseView("plain", { status: "not_generated", reason: "" })).toBe("plain");
    expect(chooseView("other", { status: "available", reason: "" })).toBe("plain");
  });
});

describe("sectionHeading", () => {
  it("combines label and title without repeating the label", () => {
    expect(sectionHeading(section({ label: "2.1", title: "Methods" }))).toBe("2.1 Methods");
    expect(sectionHeading(section({ label: "2.1", title: "2.1 Methods" }))).toBe("2.1 Methods");
    expect(sectionHeading(section({ title: "1 Introduction" }))).toBe("1 Introduction");
  });

  it("names untitled abstracts and acknowledgements, and skips untitled containers", () => {
    expect(sectionHeading(section({ kind: "abstract" }))).toBe("Abstract");
    expect(sectionHeading(section({ kind: "ack" }))).toBe("Acknowledgements");
    expect(sectionHeading(section({ kind: "body" }))).toBe("");
  });
});

describe("headingLevel", () => {
  it("starts at h2 and stops at h5", () => {
    expect([0, 1, 2, 3, 7].map(headingLevel)).toEqual([2, 3, 4, 5, 5]);
  });
});

describe("withheldMessage", () => {
  it("explains withheld parts with correct grammar", () => {
    expect(withheldMessage({ paragraphs: 0, figures: 0 })).toBe("");
    expect(withheldMessage({ paragraphs: 0, figures: 1 })).toMatch(/^1 figure or table is not shown/);
    expect(withheldMessage({ paragraphs: 2, figures: 3 })).toMatch(
      /^2 paragraphs and 3 figures or tables are not shown/,
    );
  });
});
