import { describe, expect, it } from "vitest";

import { HIGHLIGHT_START as S, HIGHLIGHT_STOP as E, splitHighlights } from "@/lib/highlight";

describe("splitHighlights", () => {
  it("splits marked words from plain text", () => {
    expect(splitHighlights(`low ${S}vitamin${E} ${S}D${E} levels`)).toEqual([
      { text: "low ", highlighted: false },
      { text: "vitamin", highlighted: true },
      { text: " ", highlighted: false },
      { text: "D", highlighted: true },
      { text: " levels", highlighted: false },
    ]);
  });

  it("tolerates unbalanced markers", () => {
    expect(splitHighlights(`a${E}b ${S}c`)).toEqual([
      { text: "ab ", highlighted: false },
      { text: "c", highlighted: true },
    ]);
  });

  it("returns nothing for an empty snippet", () => {
    expect(splitHighlights("")).toEqual([]);
  });
});
