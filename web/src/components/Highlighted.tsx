/** Renders a search snippet with its matched words marked, as text (never HTML). */
import { splitHighlights } from "@/lib/highlight";

/** Props of {@link Highlighted}. */
export interface HighlightedProps {
  /** Snippet with the API's highlight markers. */
  snippet: string;
}

/**
 * The snippet with `<mark>` around matched words.
 *
 * @returns The rendered snippet.
 */
export function Highlighted({ snippet }: HighlightedProps) {
  return (
    <>
      {splitHighlights(snippet).map((segment, index) =>
        segment.highlighted ? <mark key={index}>{segment.text}</mark> : segment.text,
      )}
    </>
  );
}
