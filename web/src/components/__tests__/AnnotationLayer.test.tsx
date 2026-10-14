import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { annotator, createTextAnnotator } = vi.hoisted(() => {
  const mock = {
    setAnnotations: vi.fn(),
    on: vi.fn(),
    scrollIntoView: vi.fn(() => true),
    destroy: vi.fn(),
  };
  return { annotator: mock, createTextAnnotator: vi.fn(() => mock) };
});
vi.mock("@recogito/text-annotator", () => ({ createTextAnnotator }));
vi.mock("@recogito/text-annotator/text-annotator.css", () => ({}));

import { AnnotationLayer } from "@/components/AnnotationLayer";
import { syntheticAnnotation } from "@/test/fixtures";

const TEXT = "Synthetic text about circadian rhythms.";

/**
 * Render the layer over one synthetic paragraph and let the dynamic import settle.
 *
 * @param annotations - Annotations to pass.
 */
async function renderLayer(annotations: Parameters<typeof AnnotationLayer>[0]["annotations"]) {
  render(
    <AnnotationLayer annotations={annotations}>
      <p data-paragraph-id="p1">{TEXT}</p>
    </AnnotationLayer>,
  );
  await act(async () => {
    await Promise.resolve();
    await new Promise((resolve) => setTimeout(resolve, 0));
  });
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("AnnotationLayer", () => {
  it("does not load the annotator when there are no annotations", async () => {
    await renderLayer([]);
    expect(createTextAnnotator).not.toHaveBeenCalled();
    expect(screen.getByText(TEXT)).toBeInTheDocument();
    expect(screen.queryByText("Explanations in this paper")).not.toBeInTheDocument();
  });

  it("highlights placed annotations read-only and lists every explanation", async () => {
    const llm = syntheticAnnotation("p1", TEXT, "circadian rhythms");
    const human = syntheticAnnotation("p1", TEXT, "Synthetic", {
      provenance: "human",
      needs_disclaimer: false,
      model: null,
      prompt_version: null,
    });
    await renderLayer([llm, human]);

    expect(createTextAnnotator).toHaveBeenCalledWith(
      expect.any(HTMLElement),
      expect.objectContaining({ annotatingEnabled: false }),
    );
    const [placed] = annotator.setAnnotations.mock.calls[0] as unknown as [
      { id: string; target: { selector: { start: number; end: number }[] } }[],
    ];
    expect(placed.map((item) => item.id)).toEqual([llm.id, human.id]);
    expect(placed[0]?.target.selector[0]).toMatchObject({ start: 21, end: 38 });

    // Both explanations are listed; only the AI one carries the disclaimer.
    expect(screen.getByRole("heading", { name: "Explanations in this paper" })).toBeInTheDocument();
    expect(screen.getByText("AI-written draft")).toBeInTheDocument();
    expect(screen.getByText("Written by a person")).toBeInTheDocument();
    expect(screen.getAllByRole("note")).toHaveLength(1);
  });

  it("scrolls to an explanation's passage on request", async () => {
    const annotation = syntheticAnnotation("p1", TEXT, "circadian");
    await renderLayer([annotation]);
    await userEvent.click(screen.getByRole("button", { name: "Show in the text" }));
    expect(annotator.scrollIntoView).toHaveBeenCalledWith(annotation.id);
    expect(screen.getByRole("heading", { name: "Selected explanation" })).toBeInTheDocument();
  });

  it("leaves superseded annotations out", async () => {
    await renderLayer([syntheticAnnotation("p1", TEXT, "text", { superseded: true })]);
    expect(createTextAnnotator).not.toHaveBeenCalled();
  });
});
