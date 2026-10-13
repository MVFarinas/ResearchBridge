/**
 * The original paper text: sections, paragraphs and figure captions, rendered
 * as plain text exactly as the API returns it (so annotation offsets line up,
 * and no markup from the source is ever injected).
 */
import { createElement } from "react";

import type { Section } from "@/lib/api/types";
import { headingLevel, sectionHeading } from "@/lib/paper-view";

/** Props of {@link OriginalText}. */
export interface OriginalTextProps {
  /** Sections in document order. */
  sections: Section[];
}

/**
 * The paper's sections with headings at their nesting level.
 *
 * @returns The rendered text.
 */
export function OriginalText({ sections }: OriginalTextProps) {
  return (
    <div className="reading" lang="en">
      {sections.map((section) => {
        const heading = sectionHeading(section);
        return (
          <section key={section.id} aria-label={heading || undefined}>
            {heading
              ? createElement(
                  `h${headingLevel(section.depth)}`,
                  { id: `section-${section.id}` },
                  heading,
                )
              : null}
            {section.paragraphs.map((paragraph) => (
              <p
                key={paragraph.id}
                id={`p-${paragraph.id}`}
                data-paragraph-id={paragraph.id}
                className={paragraph.kind === "p" ? undefined : `para-${paragraph.kind}`}
              >
                {paragraph.text}
              </p>
            ))}
            {section.figures.map((figure) => (
              <figure key={figure.id} id={`figure-${figure.id}`}>
                <figcaption>
                  {figure.label ? <strong>{figure.label}. </strong> : null}
                  {figure.caption_title ? <span>{figure.caption_title} </span> : null}
                  {figure.caption}
                </figcaption>
                <p className="small muted">
                  {figure.kind === "table" ? "Table contents" : "The image"} not shown here; see
                  the original paper.
                </p>
              </figure>
            ))}
          </section>
        );
      })}
    </div>
  );
}
