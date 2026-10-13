/**
 * Snippet highlighting. The search API marks matched words with two
 * private-use characters instead of HTML, so snippets can be rendered as React
 * text (never as HTML) and still show highlights.
 */

/** Start-of-highlight marker used by the API (U+E000). */
export const HIGHLIGHT_START = "";
/** End-of-highlight marker used by the API (U+E001). */
export const HIGHLIGHT_STOP = "";

/** One run of snippet text. */
export interface Segment {
  /** The text. */
  text: string;
  /** Whether it matched the query. */
  highlighted: boolean;
}

/**
 * Split a marked snippet into plain and highlighted runs.
 *
 * Unbalanced markers are tolerated: a missing stop ends the highlight at the
 * end of the text, and stray stops are dropped.
 *
 * @param snippet - Text with highlight markers.
 * @returns Non-empty segments in order.
 */
export function splitHighlights(snippet: string): Segment[] {
  const segments: Segment[] = [];
  let current = "";
  let highlighted = false;
  // Walk the text once, closing a segment at every marker that changes state.
  for (const char of snippet) {
    if (char === HIGHLIGHT_START || char === HIGHLIGHT_STOP) {
      const next = char === HIGHLIGHT_START;
      if (next !== highlighted) {
        if (current) segments.push({ text: current, highlighted });
        current = "";
        highlighted = next;
      }
      continue;
    }
    current += char;
  }
  if (current) segments.push({ text: current, highlighted });
  return segments;
}
