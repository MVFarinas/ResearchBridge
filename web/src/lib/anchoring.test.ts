import { describe, expect, it } from "vitest";

import {
  anchorAnnotation,
  codePointOffsetToUtf16,
  placeAnnotations,
  quotedText,
  toRecogitoAnnotation,
} from "@/lib/anchoring";
import { syntheticAnnotation } from "@/test/fixtures";

describe("codePointOffsetToUtf16", () => {
  it("is the identity for text without astral characters", () => {
    expect(codePointOffsetToUtf16("café", 4)).toBe(4);
  });

  it("counts an emoji as one code point but two UTF-16 units", () => {
    const text = "a💡b";
    expect(codePointOffsetToUtf16(text, 1)).toBe(1);
    expect(codePointOffsetToUtf16(text, 2)).toBe(3);
    expect(codePointOffsetToUtf16(text, 3)).toBe(4);
  });

  it("rejects offsets outside the text", () => {
    expect(codePointOffsetToUtf16("abc", 4)).toBeNull();
    expect(codePointOffsetToUtf16("abc", -1)).toBeNull();
    expect(codePointOffsetToUtf16("abc", 1.5)).toBeNull();
  });
});

describe("anchorAnnotation", () => {
  const text = "Light 💡 at night lowers melatonin; light at night matters.";

  it("uses the position selector, converted to UTF-16", () => {
    const annotation = syntheticAnnotation("p1", text, "at night lowers");
    const span = anchorAnnotation(annotation, text);
    expect(span).toEqual({ start: 9, end: 24, quote: "at night lowers" });
    expect(text.slice(span?.start, span?.end)).toBe("at night lowers");
  });

  it("falls back to the quote when the position no longer matches", () => {
    const annotation = syntheticAnnotation("p1", text, "melatonin", {
      target: {
        source: "synthetic",
        selector: [
          { type: "TextQuoteSelector", exact: "melatonin" },
          { type: "TextPositionSelector", start: 0, end: 9 },
        ],
      },
    });
    expect(anchorAnnotation(annotation, text)).toEqual({
      start: text.indexOf("melatonin"),
      end: text.indexOf("melatonin") + 9,
      quote: "melatonin",
    });
  });

  it("uses prefix and suffix to choose between repeats, and refuses to guess", () => {
    const ambiguous = syntheticAnnotation("p1", text, "at night", {
      target: { source: "s", selector: [{ type: "TextQuoteSelector", exact: "at night" }] },
    });
    expect(anchorAnnotation(ambiguous, text)).toBeNull();
    const disambiguated = syntheticAnnotation("p1", text, "at night", {
      target: {
        source: "s",
        selector: [{ type: "TextQuoteSelector", exact: "at night", suffix: " matters" }],
      },
    });
    expect(anchorAnnotation(disambiguated, text)?.start).toBe(text.lastIndexOf("at night"));
  });

  it("returns null when the quote is missing", () => {
    const missing = syntheticAnnotation("p1", text, "Light", {
      target: { source: "s", selector: [{ type: "TextQuoteSelector", exact: "absent words" }] },
    });
    expect(anchorAnnotation(missing, text)).toBeNull();
    expect(quotedText(missing)).toBe("absent words");
  });
});

describe("placeAnnotations and toRecogitoAnnotation", () => {
  it("places annotations on rendered paragraphs with the paragraph as offset reference", () => {
    const container = document.createElement("div");
    container.innerHTML =
      '<p data-paragraph-id="p1">Synthetic first paragraph.</p>' +
      '<p data-paragraph-id="p.2">Synthetic second paragraph.</p>';
    const placed = placeAnnotations(
      [
        syntheticAnnotation("p.2", "Synthetic second paragraph.", "second"),
        syntheticAnnotation("missing", "x", "x"),
      ],
      container,
    );
    expect(placed).toHaveLength(1);
    const [only] = placed;
    const selector = only?.recogito.target.selector[0];
    expect(selector).toMatchObject({ quote: "second", start: 10, end: 16 });
    expect(selector?.offsetReference).toBe(container.querySelector('[data-paragraph-id="p.2"]'));
    expect(only?.recogito.bodies[0]?.value).toBe("Synthetic explanation.");
  });

  it("keeps the annotation ID across models", () => {
    const annotation = syntheticAnnotation("p1", "abc", "b");
    const element = document.createElement("p");
    const recogito = toRecogitoAnnotation(annotation, { start: 1, end: 2, quote: "b" }, element);
    expect(recogito.id).toBe(annotation.id);
    expect(recogito.target.annotation).toBe(annotation.id);
  });
});
