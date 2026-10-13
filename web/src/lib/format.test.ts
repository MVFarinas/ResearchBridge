import { describe, expect, it } from "vitest";

import { availabilityLabel, formatAuthors, formatDate } from "@/lib/format";

describe("formatDate", () => {
  it.each([
    ["2026-10-13", "13 October 2026"],
    ["2026-10-13T22:00:27.624606+00:00", "13 October 2026"],
    ["2024-05", "May 2024"],
    ["2024", "2024"],
    ["", ""],
    [null, ""],
    ["not a date", ""],
  ])("formats %s as %s", (input, expected) => {
    expect(formatDate(input)).toBe(expected);
  });
});

describe("formatAuthors", () => {
  it("joins short lists and shortens long ones", () => {
    expect(formatAuthors([])).toBe("");
    expect(formatAuthors(["A"])).toBe("A");
    expect(formatAuthors(["A", "B"])).toBe("A and B");
    expect(formatAuthors(["A", "B", "C"])).toBe("A, B and C");
    expect(formatAuthors(["A", "B", "C", "D"])).toBe("A, B, C et al.");
  });
});

describe("availabilityLabel", () => {
  it("never claims a plain-English version exists before it is generated", () => {
    expect(availabilityLabel("plain_english_available", "not_generated").label).toBe(
      "Plain English permitted (not written yet)",
    );
    expect(availabilityLabel("plain_english_available").label).toContain("not written yet");
    expect(availabilityLabel("plain_english_available", "available").label).toBe(
      "Plain English available",
    );
  });

  it("labels the other tags", () => {
    expect(availabilityLabel("original_annotations_only").label).toBe("Original + explanations");
    expect(availabilityLabel("may_be_available").label).toBe("May be available: request it");
    expect(availabilityLabel("original_elsewhere").label).toBe("Original elsewhere");
  });
});
