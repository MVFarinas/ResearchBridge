"use client";

/**
 * The annotation layer over the original text, using Recogito's Text Annotator
 * (`@recogito/text-annotator`, BSD-3-Clause) to highlight annotated passages.
 *
 * The paper text is server-rendered as children, so it is indexable and
 * readable without JavaScript. When annotations exist, the annotator is loaded
 * in the browser, highlights them read-only, and shows the selected
 * explanation; a list of all explanations below the text keeps them reachable
 * by keyboard and screen reader. With no annotations nothing is loaded.
 */
import "@recogito/text-annotator/text-annotator.css";

import { type ReactNode, useEffect, useRef, useState } from "react";

import { Disclaimer } from "@/components/Disclaimer";
import { placeAnnotations, quotedText } from "@/lib/anchoring";
import type { ApiAnnotation } from "@/lib/api/types";

/** Props of {@link AnnotationLayer}. */
export interface AnnotationLayerProps {
  /** Annotations to show (superseded ones are left out). */
  annotations: ApiAnnotation[];
  /** The rendered original text, with `data-paragraph-id` on each paragraph. */
  children: ReactNode;
}

/** The minimal annotator surface this component uses. */
interface Annotator {
  setAnnotations(annotations: unknown[]): void;
  on(event: "selectionChanged", handler: (selected: { id: string }[]) => void): void;
  scrollIntoView(id: string): boolean;
  destroy(): void;
}

const PROVENANCE_LABELS: Record<ApiAnnotation["provenance"], string> = {
  llm: "AI-written draft",
  llm_edited: "AI draft edited by a person",
  human: "Written by a person",
};

/**
 * The text with highlighted, selectable explanations, followed by the list of explanations.
 *
 * @returns The layer.
 */
export function AnnotationLayer({ annotations, children }: AnnotationLayerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const annotatorRef = useRef<Annotator | null>(null);
  const [placedIds, setPlacedIds] = useState<ReadonlySet<string>>(new Set());
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const visible = annotations.filter((annotation) => !annotation.superseded);

  // Load the annotator only when there is something to show, and tear it down on change.
  useEffect(() => {
    const container = containerRef.current;
    const shown = annotations.filter((annotation) => !annotation.superseded);
    if (!container || shown.length === 0) return;
    let cancelled = false;
    let annotator: Annotator | null = null;
    void import("@recogito/text-annotator").then(({ createTextAnnotator }) => {
      if (cancelled) return;
      const placed = placeAnnotations(shown, container);
      annotator = createTextAnnotator(container, {
        annotatingEnabled: false,
        offsetReferenceSelector: "[data-paragraph-id]",
      }) as unknown as Annotator;
      annotator.setAnnotations(placed.map((item) => item.recogito));
      annotator.on("selectionChanged", (selected) => setSelectedId(selected[0]?.id ?? null));
      annotatorRef.current = annotator;
      setPlacedIds(new Set(placed.map((item) => item.annotation.id)));
    });
    return () => {
      cancelled = true;
      annotator?.destroy();
      annotatorRef.current = null;
    };
  }, [annotations]);

  const selected = visible.find((annotation) => annotation.id === selectedId) ?? null;
  return (
    <>
      <div ref={containerRef} data-annotation-container="">
        {children}
      </div>
      <div aria-live="polite">
        {selected ? <ExplanationCard annotation={selected} heading="Selected explanation" /> : null}
      </div>
      {visible.length > 0 ? (
        <section aria-labelledby="explanations-heading">
          <h2 id="explanations-heading">Explanations in this paper</h2>
          <ul className="explanation-list">
            {visible.map((annotation) => (
              <li key={annotation.id}>
                <ExplanationCard annotation={annotation}>
                  {placedIds.has(annotation.id) ? (
                    <button
                      type="button"
                      className="button secondary"
                      onClick={() => {
                        annotatorRef.current?.scrollIntoView(annotation.id);
                        setSelectedId(annotation.id);
                      }}
                    >
                      Show in the text
                    </button>
                  ) : null}
                </ExplanationCard>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </>
  );
}

/** Props of {@link ExplanationCard}. */
interface ExplanationCardProps {
  /** The annotation. */
  annotation: ApiAnnotation;
  /** Optional heading above it. */
  heading?: string;
  /** Actions shown at the bottom of the card. */
  children?: ReactNode;
}

/**
 * One explanation: the quoted passage, the explanation as plain text, who
 * wrote it, and the disclaimer when an AI wrote it and no person has checked it.
 *
 * @returns The card.
 */
function ExplanationCard({ annotation, heading, children }: ExplanationCardProps) {
  const quote = quotedText(annotation);
  return (
    <div className="panel">
      {heading ? <h3>{heading}</h3> : null}
      {quote ? <blockquote>“{quote}”</blockquote> : null}
      <p>{annotation.body.value}</p>
      <p className="small muted">
        {PROVENANCE_LABELS[annotation.provenance]}
        {annotation.verified ? " · checked by a person" : ""}
      </p>
      {annotation.needs_disclaimer ? <Disclaimer kind="annotation" /> : null}
      {children}
    </div>
  );
}
