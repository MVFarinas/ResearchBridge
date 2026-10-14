/**
 * Paragraph-aligned reading: each original paragraph beside its plain-English
 * version on wide screens, stacked on narrow ones. Rewrites are aligned by
 * paragraph ID (the alignment unit of decisions.md §1.4), so a paragraph
 * without a rewrite shows the original alone.
 */
import type { Paragraph } from "@/lib/api/types";

/** A plain-English paragraph aligned to an original one. */
export interface RewrittenParagraph {
  /** The original paragraph's stable ID. */
  id: string;
  /** The plain-English text. */
  text: string;
}

/** Props of {@link AlignedParagraphs}. */
export interface AlignedParagraphsProps {
  /** Original paragraphs in order. */
  paragraphs: Paragraph[];
  /** Plain-English paragraphs, by original paragraph ID. */
  rewritten: RewrittenParagraph[];
}

/**
 * Rows of original and plain-English paragraphs.
 *
 * @returns The aligned rows.
 */
export function AlignedParagraphs({ paragraphs, rewritten }: AlignedParagraphsProps) {
  const byId = new Map(rewritten.map((item) => [item.id, item.text]));
  return (
    <div className="aligned reading">
      {paragraphs.map((paragraph) => {
        const plain = byId.get(paragraph.id);
        return (
          <div
            key={paragraph.id}
            className={`aligned-row${plain === undefined ? "" : " has-pair"}`}
            data-row={paragraph.id}
          >
            {plain === undefined ? null : (
              <div>
                <div className="aligned-label">Plain English</div>
                <p>{plain}</p>
              </div>
            )}
            <div>
              <div className="aligned-label">Original</div>
              <p data-paragraph-id={paragraph.id}>{paragraph.text}</p>
            </div>
          </div>
        );
      })}
    </div>
  );
}
