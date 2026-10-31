// The skill sheet on the learner's map (SPEC §21.1, §21.8; W10): it reads the skill's links once (the reply the core
// serves, test_w10_kc_links.py) and lists the Study materials and the lecture moments (each opens in Study), the cards
// due, the tutor's notes about the skill (they open "What your tutor knows"), whether the tutor is tracking it, and
// three actions that exist elsewhere: Make flashcards, Research this, Ask your tutor about this. A note pin on the
// Notes layer opens the sheet and its note opens the knows page. The drawing is a stand-in; synthetic data.
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import fs from "node:fs";
import path from "node:path";
import { afterEach, describe, expect, test, vi } from "vitest";
import { EMPTY_LENS, readKcLinks, type ConceptMap, type KcLinks, type MapLayer } from "@jana/client-core";
import { LocaleProvider } from "../src/i18n.js";
import { ConceptMapContent, ConceptMapRendererProvider, type ConceptActions, type ConceptMapRenderer } from "../src/learn/ConceptMap.js";
import { VT, layered } from "./learner-map-fixtures.js";

const LINKS = readKcLinks(JSON.parse(fs.readFileSync(path.join(import.meta.dirname, "fixtures", "kc-links.json"), "utf8")));
const Drawing: ConceptMapRenderer = ({ nodes, onActivate }) => (
  <div>{nodes.map((n) => <button type="button" key={n.id} data-kc-node={n.id} data-pin={n.layer?.pin ? "" : undefined} onClick={() => onActivate(n.id)}>{n.title}</button>)}</div>
);

afterEach(() => cleanup());

function sheetOf(links: KcLinks | "loading" | undefined, actions: ConceptActions, layer: MapLayer = "mastery", map: ConceptMap = layered(), onLinks = vi.fn()) {
  const lens = { ...EMPTY_LENS, layer, links: links === undefined ? {} : { [VT]: links } };
  render(
    <LocaleProvider locale="en"><ConceptMapRendererProvider value={Drawing}>
      <ConceptMapContent view={{ status: "ready", subjectId: "cur.phy.o", map, gap: null }} actions={actions}
        lens={{ lens, onLayer: () => undefined, onScrub: () => undefined, onLinks, today: "2026-10-31" }} />
    </ConceptMapRendererProvider></LocaleProvider>,
  );
  fireEvent.click(document.querySelector<HTMLButtonElement>(`[data-kc-node="${VT}"]`)!);
  return { sheet: document.querySelector<HTMLElement>(`[data-concept-sheet="${VT}"]`)!, onLinks };
}

describe("learner's map sheet", () => {
  test("opening_a_skill_reads_its_links_once_and_waits_in_words", () => {
    const { sheet, onLinks } = sheetOf(undefined, {});
    expect(onLinks).toHaveBeenCalledWith(VT);
    expect(within(sheet).getByText("Opening what's linked to this skill")).toBeTruthy();
  });

  test("a_material_and_a_moment_open_in_study", () => {
    const onOpenMaterial = vi.fn(), onOpenMoment = vi.fn();
    const { sheet } = sheetOf(LINKS, { onOpenMaterial, onOpenMoment });
    const study = sheet.querySelector<HTMLElement>("[data-sheet-study]")!;
    expect(within(study).getByText("In Study")).toBeTruthy();
    fireEvent.click(within(study).getByRole("button", { name: "Practice questions" }));
    expect(onOpenMaterial).toHaveBeenCalledWith(LINKS.materials[0]);
    fireEvent.click(within(study).getByRole("button", { name: "Kinematics lecture at 04:12" }));
    expect(onOpenMoment).toHaveBeenCalledWith({ source_id: LINKS.moments[0]!.source_id, at_ms: 252_000, title: "Kinematics lecture" });
    expect(within(study).getByText("1 card due")).toBeTruthy();
  });

  test("a_note_pin_opens_the_sheet_and_its_note_opens_the_knows_page", () => {
    const onOpenKnows = vi.fn();
    const { sheet } = sheetOf(LINKS, { onOpenKnows }, "notes");
    expect(document.querySelector(`[data-kc-node="${VT}"]`)!.getAttribute("data-pin")).toBe("");
    const notes = sheet.querySelector<HTMLElement>("[data-sheet-notes]")!;
    expect(within(notes).getByText("Draws the graph before calculating")).toBeTruthy();
    expect(within(notes).getByText("Seen once")).toBeTruthy();
    fireEvent.click(within(notes).getByRole("button", { name: "Open what your tutor knows" }));
    expect(onOpenKnows).toHaveBeenCalledTimes(1);
    expect(within(sheet).getByText("Your tutor is tracking this topic.")).toBeTruthy();
  });

  test("the_three_actions_hand_over_the_skill", () => {
    const onMakeFlashcards = vi.fn(), onResearch = vi.fn(), onAskTutor = vi.fn();
    const { sheet } = sheetOf(LINKS, { onMakeFlashcards, onResearch, onAskTutor });
    const actions = sheet.querySelector<HTMLElement>("[data-sheet-actions]")!;
    fireEvent.click(within(actions).getByRole("button", { name: "Make flashcards" }));
    expect(onMakeFlashcards.mock.calls[0]![0].kc_id).toBe(VT);
    expect(onMakeFlashcards.mock.calls[0]![1]).toBe(LINKS);
    fireEvent.click(within(actions).getByRole("button", { name: "Research this" }));
    expect(onResearch.mock.calls[0]![0].statement).toBe("Find acceleration from the gradient of a velocity-time graph");
    fireEvent.click(within(actions).getByRole("button", { name: "Ask your tutor about this" }));
    expect(onAskTutor.mock.calls[0]![0].kc_id).toBe(VT);
  });

  test("nothing_linked_says_so_and_offers_no_flashcards", () => {
    const empty: KcLinks = { ...LINKS, materials: [], moments: [], notes: [], tracked: false };
    const onMakeFlashcards = vi.fn();
    const map = layered();
    map.nodes = map.nodes.map((n) => (n.kc_id === VT ? { ...n, study: { materials: 0, moments: 0, cards_due: 0 } } : n));
    const { sheet } = sheetOf(empty, { onMakeFlashcards, onResearch: () => undefined }, "mastery", map);
    expect(within(sheet).getByText("Nothing in Study is linked to this skill yet.")).toBeTruthy();
    expect(within(sheet).queryByRole("button", { name: "Make flashcards" })).toBeNull();
    expect(screen.queryByText("Your tutor is tracking this topic.")).toBeNull();
  });
});
