/**
 * Anchoring W3C annotations to the rendered paragraphs.
 *
 * The API stores selectors relative to one paragraph's plain text, counting
 * Unicode code points (the W3C model's "characters"); the DOM counts UTF-16
 * code units, so positions are converted. If the position does not match the
 * quote (it should, since the API withholds annotations whose paragraph text
 * changed), the quote itself is searched for, using its prefix and suffix to
 * choose among repeats; an annotation that cannot be placed unambiguously is
 * left out rather than shown in the wrong place.
 *
 * Written for ResearchBridge. The Hypothesis client's fuzzy anchoring
 * (BSD-2-Clause) was considered and not needed: the server guarantees exact
 * text, so exact matching with this fallback is sufficient.
 */
import type { TextAnnotation } from "@recogito/text-annotator";

import type { ApiAnnotation } from "@/lib/api/types";

/** Where an annotation sits in its paragraph, in UTF-16 offsets. */
export interface AnchoredSpan {
  /** Start offset (UTF-16 code units). */
  start: number;
  /** End offset, exclusive. */
  end: number;
  /** The quoted text. */
  quote: string;
}

/**
 * Convert a code-point offset into a UTF-16 offset in the same string.
 *
 * @param text - The text.
 * @param offset - Offset in Unicode code points.
 * @returns The UTF-16 offset, or null if the offset is negative or beyond the text.
 */
export function codePointOffsetToUtf16(text: string, offset: number): number | null {
  if (!Number.isInteger(offset) || offset < 0) return null;
  let codePoints = 0;
  let units = 0;
  // Walk code points until the requested one, counting code units as we go.
  for (const char of text) {
    if (codePoints === offset) return units;
    codePoints += 1;
    units += char.length;
  }
  return codePoints === offset ? units : null;
}

/**
 * Find where an annotation sits in its paragraph's text.
 *
 * @param annotation - The annotation.
 * @param paragraphText - The paragraph's text exactly as rendered.
 * @returns The span, or null when it cannot be placed unambiguously.
 */
export function anchorAnnotation(
  annotation: ApiAnnotation,
  paragraphText: string,
): AnchoredSpan | null {
  const quote = annotation.target.selector.find((s) => s.type === "TextQuoteSelector");
  const position = annotation.target.selector.find((s) => s.type === "TextPositionSelector");
  if (!quote || quote.type !== "TextQuoteSelector" || !quote.exact) return null;

  // First choice: the position selector, if it still points at the quote.
  if (position && position.type === "TextPositionSelector") {
    const start = codePointOffsetToUtf16(paragraphText, position.start);
    const end = codePointOffsetToUtf16(paragraphText, position.end);
    if (start !== null && end !== null && paragraphText.slice(start, end) === quote.exact) {
      return { start, end, quote: quote.exact };
    }
  }

  // Fallback: the quote, disambiguated by its prefix and suffix.
  const candidates: number[] = [];
  for (let at = paragraphText.indexOf(quote.exact); at !== -1; ) {
    const before = paragraphText.slice(0, at);
    const after = paragraphText.slice(at + quote.exact.length);
    const prefixOk = !quote.prefix || before.endsWith(quote.prefix);
    const suffixOk = !quote.suffix || after.startsWith(quote.suffix);
    if (prefixOk && suffixOk) candidates.push(at);
    at = paragraphText.indexOf(quote.exact, at + 1);
  }
  const [only] = candidates;
  if (candidates.length !== 1 || only === undefined) return null;
  return { start: only, end: only + quote.exact.length, quote: quote.exact };
}

/**
 * Express an anchored annotation in Recogito's native model.
 *
 * Offsets are relative to the paragraph element (`offsetReference`), which is
 * how the Text Annotator supports offsets inside one part of a larger container.
 *
 * @param annotation - The API annotation.
 * @param span - Where it sits.
 * @param paragraph - The rendered paragraph element.
 * @returns The Recogito annotation.
 */
export function toRecogitoAnnotation(
  annotation: ApiAnnotation,
  span: AnchoredSpan,
  paragraph: HTMLElement,
): TextAnnotation {
  return {
    id: annotation.id,
    bodies: [
      {
        id: `${annotation.id}#body`,
        annotation: annotation.id,
        purpose: annotation.motivation,
        value: annotation.body.value,
      },
    ],
    target: {
      annotation: annotation.id,
      selector: [
        { quote: span.quote, start: span.start, end: span.end, offsetReference: paragraph },
      ],
    },
  };
}

/** An annotation placed on a rendered paragraph. */
export interface PlacedAnnotation {
  /** The API annotation. */
  annotation: ApiAnnotation;
  /** The same annotation in Recogito's model. */
  recogito: TextAnnotation;
}

/**
 * Place annotations on the paragraphs rendered inside a container.
 *
 * Paragraph elements carry `data-paragraph-id`; their text content is the
 * paragraph's plain text, so offsets line up exactly.
 *
 * @param annotations - Annotations from the API.
 * @param container - The element holding the rendered paragraphs.
 * @returns The annotations that could be placed (others are left out).
 */
export function placeAnnotations(
  annotations: ApiAnnotation[],
  container: HTMLElement,
): PlacedAnnotation[] {
  const placed: PlacedAnnotation[] = [];
  for (const annotation of annotations) {
    const paragraph = container.querySelector<HTMLElement>(
      `[data-paragraph-id="${CSS.escape(annotation.paragraph_id)}"]`,
    );
    const span = paragraph ? anchorAnnotation(annotation, paragraph.textContent ?? "") : null;
    if (paragraph && span) {
      placed.push({ annotation, recogito: toRecogitoAnnotation(annotation, span, paragraph) });
    }
  }
  return placed;
}

/**
 * The quoted passage of an annotation.
 *
 * @param annotation - The annotation.
 * @returns Its TextQuoteSelector's exact text, or "".
 */
export function quotedText(annotation: ApiAnnotation): string {
  const quote = annotation.target.selector.find((s) => s.type === "TextQuoteSelector");
  return quote && quote.type === "TextQuoteSelector" ? quote.exact : "";
}
