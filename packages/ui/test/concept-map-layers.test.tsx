// The learner's map layers on the skill map (SPEC §21.1, §21.5, §21.8; W10): the layer switch over the same drawing,
// a legend per layer, a table column per layer, every layer's words in each box's label (never colour alone), the
// Freshness steps drawn with the mastery looks and their tokens.json patterns, the Mistakes layer ringing an active
// and a disputed misconception with their words, and "since last time" outlined with the pulse left to the drawing,
// which is told when Reduce motion is on. The drawing is a stand-in (the UI never imports renderers, ARC-18); the
// renderer's own tests draw the marks. The map is the Physics reply the core serves (test_concept_map.py), with this
// file's synthetic layer facts on three skills.
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, test, vi } from "vitest";
import { EMPTY_LENS, type ConceptMap, type MapLayer, type MapLens } from "@jana/client-core";
import { LocaleProvider } from "../src/i18n.js";
import { ConceptMapContent, ConceptMapRendererProvider, type ConceptMapRenderer } from "../src/learn/ConceptMap.js";
import { VisualSettingsProvider } from "../src/visuals/VisualViewer.js";

import { BASE, FALL, SPEED, VT, layered } from "./learner-map-fixtures.js";

const Drawing: ConceptMapRenderer = ({ nodes, label, onActivate, reducedMotion }) => (
  <div role="group" aria-label={label} data-reduced={String(reducedMotion)}>
    {nodes.map((n) => (
      <button type="button" key={n.id} data-kc-node={n.id} data-look={n.layer?.look} data-pattern={n.layer?.pattern} data-rings={n.layer?.rings} data-dots={n.layer?.dots}
        data-pin={n.layer?.pin ? "" : undefined} data-dashed={n.layer?.dashed ? "" : undefined} data-changed={n.changed} onClick={() => onActivate(n.id)}>
        {[n.title, n.layer?.word ?? n.stateWord, ...(n.layer?.words ?? []), ...(n.changed !== undefined ? [n.changed] : [])].join(", ")}
      </button>
    ))}
  </div>
);

afterEach(() => cleanup());

function draw(layer: MapLayer, { onLayer = () => undefined, reduced = false, map = layered() }: { onLayer?: (l: MapLayer) => void; reduced?: boolean; map?: ConceptMap } = {}) {
  const lens: MapLens = { ...EMPTY_LENS, layer };
  const node: ReactNode = (
    <LocaleProvider locale="en"><VisualSettingsProvider settings={{ reducedMotion: reduced, textScale: 1 }}><ConceptMapRendererProvider value={Drawing}>
      <ConceptMapContent view={{ status: "ready", subjectId: "cur.phy.o", map, gap: null }} lens={{ lens, onLayer, onScrub: () => undefined, onLinks: () => undefined, today: "2026-10-31" }} />
    </ConceptMapRendererProvider></VisualSettingsProvider></LocaleProvider>
  );
  return render(node);
}

const box = (kc: string) => document.querySelector<HTMLElement>(`[data-kc-node="${kc}"]`)!;

describe("learner's map layers", () => {
  test("the_switch_offers_every_layer_and_says_which_is_shown", () => {
    const onLayer = vi.fn();
    draw("mastery", { onLayer });
    const radios = screen.getAllByRole("radio").map((r) => r.textContent);
    expect(radios).toEqual(expect.arrayContaining(["Mastery", "Freshness", "Mistakes", "Study", "Notes", "Tutor's topics"]));
    fireEvent.click(screen.getByRole("radio", { name: "Freshness" }));
    expect(onLayer).toHaveBeenCalledWith("freshness");
    expect(document.querySelector("[data-map-lens]")!.getAttribute("data-map-lens")).toBe("mastery");
  });

  test("freshness_paints_five_steps_with_patterns_and_words_and_refresh_due_dashed", () => {
    draw("freshness");
    expect(box(VT).dataset).toMatchObject({ look: "ready_to_check", pattern: "dots-dense" });
    expect(box(VT).getAttribute("data-dashed")).toBe("");
    expect(box(VT).textContent).toContain("Practised this week, Refresh due");
    expect(box(SPEED).dataset).toMatchObject({ look: "mastered", pattern: "solid" });
    expect(box(SPEED).textContent).toContain("Practised today");
    expect(box(FALL).dataset).toMatchObject({ look: "not_started", pattern: "none" });
    expect(box(FALL).textContent).toContain("Not practised yet");
    // The legend says what each step means, in words.
    const legend = document.querySelector<HTMLElement>("[data-concept-legend]")!;
    expect(legend.dataset.conceptLegend).toBe("freshness");
    for (const word of ["Practised today", "Practised this week", "Practised this month", "Practised longer ago", "Not practised yet", "Dashed outline: refresh due"]) {
      expect(within(legend).getByText(word)).toBeTruthy();
    }
  });

  test("mistakes_ring_an_active_and_a_disputed_misconception_with_their_words", () => {
    draw("mistakes");
    expect(box(VT).dataset.rings).toBe("2");
    expect(box(VT).textContent).toContain("2 mistakes: Still happening, You said this isn't right");
    expect(document.querySelector("[data-legend-layer]")!.textContent).toBe("A ring for each mistake being watched, with its word");
    fireEvent.click(screen.getByRole("radio", { name: "Table" }));
    const row = document.querySelector<HTMLElement>(`[data-row-kc="${VT}"]`)!;
    expect(row.querySelector("[data-layer-cell]")!.textContent).toBe("2 mistakes: Still happening, You said this isn't right");
    expect(document.querySelector(`[data-row-kc="${FALL}"] [data-layer-cell]`)!.textContent).toBe("No mistakes being watched");
    expect(screen.getByRole("columnheader", { name: "Mistakes being watched" })).toBeTruthy();
  });

  test("study_notes_and_tracked_have_marks_columns_and_words", () => {
    const { unmount } = draw("study");
    expect(box(VT).dataset.dots).toBe("4");
    expect(box(VT).textContent).toContain("2 materials, 1 lecture moment, 1 card due");
    fireEvent.click(screen.getByRole("radio", { name: "Table" }));
    expect(screen.getByRole("columnheader", { name: "In Study" })).toBeTruthy();
    expect(document.querySelector(`[data-row-kc="${FALL}"] [data-layer-cell]`)!.textContent).toBe("Nothing in Study yet");
    unmount();
    draw("notes");
    expect(box(VT).getAttribute("data-pin")).toBe("");
    expect(box(VT).textContent).toContain("1 note from your tutor");
    expect(box(FALL).getAttribute("data-pin")).toBeNull();
    cleanup();
    draw("tracked");
    expect(box(VT).textContent).toContain("Your tutor is tracking this");
    fireEvent.click(screen.getByRole("radio", { name: "Table" }));
    expect(screen.getByRole("columnheader", { name: "Topics your tutor is tracking" })).toBeTruthy();
    expect(document.querySelector(`[data-row-kc="${FALL}"] [data-layer-cell]`)!.textContent).toBe("Not one of your tutor's topics right now");
  });

  test("since_last_time_outlined_in_words_and_the_drawing_told_about_reduce_motion", () => {
    draw("mastery", { reduced: true });
    expect(box(VT).dataset.changed).toBe("Up since last time");
    expect(box(SPEED).dataset.changed).toBe("New since last time");
    expect(box(FALL).dataset.changed).toBeUndefined();
    expect(document.querySelector("[data-reduced]")!.getAttribute("data-reduced")).toBe("true");
    expect(document.querySelector("[data-legend-changed]")!.textContent).toBe("Bold outline: moved since you last opened the map");
    fireEvent.click(screen.getByRole("radio", { name: "Table" }));
    expect(screen.getByRole("columnheader", { name: "Since last time" })).toBeTruthy();
    expect(document.querySelector(`[data-row-kc="${VT}"]`)!.textContent).toContain("Up since last time");
    cleanup();
    draw("mastery", { reduced: false });
    expect(document.querySelector("[data-reduced]")!.getAttribute("data-reduced")).toBe("false");
  });

  test("a_map_from_a_core_before_w10_shows_mastery_and_reads_as_not_yet", () => {
    draw("freshness", { map: BASE });
    expect(box(FALL).textContent).toContain("Not practised yet");
    expect(document.querySelector("[data-legend-changed]")).toBeNull();
  });
});
