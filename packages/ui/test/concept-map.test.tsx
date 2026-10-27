// The subject map's "Map" mode (UXS-22 map view) against the fake core, with the Physics reply the core serves for a
// synthetic learner (test/fixtures/concept-map.phy.json, written by services/agent-core/tests/test_concept_map.py).
// The switch loads the concept map; "What to do next" words each skill's reason; a skill's sheet lists the learner's
// questions (one whose words were purged says so) and mistakes, and a mistake's root gap says it was not reviewed and
// lights its gap path; open questions go to the tutor in the learner's words; the table carries the same skills.
// The drawing is the app's (the UI never imports renderers, ARC-18): a stand-in here; the renderer's own tests draw it.
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import fs from "node:fs";
import path from "node:path";
import type { ReactNode } from "react";
import { afterEach, describe, expect, test, vi } from "vitest";
import { ConceptMapController, ProfileController, StoreHolder, SubjectMapController, readConceptMap, type ConceptMap, type SubjectMap as Map } from "@jana/client-core";
import { FakeProfileCore, PROFILES } from "../../client-core/test/profilecore.js";
import { STATES } from "../gallery/index.js";
import { LocaleProvider } from "../src/i18n.js";
import { ConceptMapContent, ConceptMapRendererProvider, type ConceptMapRenderer } from "../src/learn/ConceptMap.js";
import { SubjectMap } from "../src/learn/SubjectMap.js";

const BEN = PROFILES[1]!;
const CONCEPT = readConceptMap(JSON.parse(fs.readFileSync(path.join(import.meta.dirname, "fixtures", "concept-map.phy.json"), "utf8"))) as ConceptMap;
const MAP = STATES.find((s) => s.id === "subject-map.canonical.topic-sheet")!.payload as { map: Map };
const VT = "kc.phy.o.motion.velocity_time_gradient";
const GRADIENT = "kc.mth.o.coordinate_geometry.gradient";

const Drawing: ConceptMapRenderer = ({ nodes, gap, label, onActivate }) => (
  <div role="group" aria-label={label} data-stub-gap={(gap ?? []).join(" ")}>
    {nodes.map((n) => <button type="button" key={n.id} data-kc-node={n.id} data-asked={n.asked} data-mistakes={n.mistakes} onClick={() => onActivate(n.id)}>{n.title}, {n.stateWord}</button>)}
  </div>
);

afterEach(() => cleanup());

function wrap(children: ReactNode) {
  return <LocaleProvider locale="en"><ConceptMapRendererProvider value={Drawing}>{children}</ConceptMapRendererProvider></LocaleProvider>;
}

async function unlocked() {
  const core = new FakeProfileCore();
  const profiles = new ProfileController(core.launch, new StoreHolder(), { fetch: core.fetch });
  await profiles.load();
  expect(await profiles.unlock(BEN.profile_id)).toBe(true);
  return { core, profiles };
}

describe("concept map view", () => {
  test("map_mode_loads_ranks_and_takes_open_questions_to_the_tutor", async () => {
    const { core, profiles } = await unlocked();
    core.maps.set("cur.phy.o", MAP.map);
    core.conceptMaps.set("cur.phy.o", CONCEPT);
    const asked = vi.fn();
    render(wrap(<SubjectMap controller={new SubjectMapController(profiles)} concept={new ConceptMapController(profiles)} subjectId="cur.phy.o" onAskQuestion={asked} />));
    await waitFor(() => expect(screen.getByRole("radio", { name: "Map" })).toBeTruthy());
    expect(core.log.some((l) => l.path.endsWith("/concept-map"))).toBe(false); // read only when the map is shown
    fireEvent.click(screen.getByRole("radio", { name: "Map" }));
    await waitFor(() => expect(document.querySelector("[data-concept-ready]")).not.toBeNull());
    // Every skill is drawn, the learner's badges with it.
    expect(document.querySelectorAll("[data-kc-node]")).toHaveLength(CONCEPT.nodes.length);
    expect(document.querySelector(`[data-kc-node="${VT}"]`)!.getAttribute("data-asked")).toBe("4");
    expect(document.querySelector(`[data-kc-node="${VT}"]`)!.getAttribute("data-mistakes")).toBe("1");
    // What next: each ranked skill with a worded reason.
    const next = document.querySelectorAll("[data-next-kc]");
    expect(next.length).toBe(CONCEPT.next.length);
    expect(next[0]!.textContent).toMatch(/^1\. /);
    expect(next[0]!.textContent).toMatch(/Worth (a lot|a fair amount|a little) in the exam/);
    // The photographed question that matches no skill is an open question, taken to the tutor in its own words.
    const open = document.querySelector("[data-open-question]")!;
    expect(within(open as HTMLElement).getByText("What does this circuit symbol mean?")).toBeTruthy();
    expect(within(open as HTMLElement).getByText("Open question · From a photo")).toBeTruthy();
    fireEvent.click(within(open as HTMLElement).getByRole("button", { name: "Ask the tutor" }));
    expect(asked).toHaveBeenCalledWith("What does this circuit symbol mean?");
  });

  test("sheet_lists_questions_and_mistakes_and_lights_the_unreviewed_gap_path", async () => {
    const { profiles } = await unlocked();
    const controller = new ConceptMapController(profiles);
    // A view with the map already read.
    const view = { status: "ready" as const, subjectId: "cur.phy.o", map: CONCEPT, gap: null };
    const { rerender } = render(wrap(<ConceptMapContent view={view} onShowGap={(g) => controller.showGap(g)} />));
    fireEvent.click(document.querySelector<HTMLButtonElement>(`[data-kc-node="${VT}"]`)!);
    const sheet = document.querySelector<HTMLElement>(`[data-concept-sheet="${VT}"]`)!;
    expect(sheet).not.toBeNull();
    expect(document.activeElement?.tagName).toBe("H2"); // focus moves to the sheet's heading
    expect(sheet.querySelectorAll("[data-question]")).toHaveLength(4);
    expect(within(sheet).getByText("An earlier question (its words are no longer kept)")).toBeTruthy();
    expect(within(sheet).getAllByText("Spoken")).toHaveLength(1);
    expect(within(sheet).getByText("Acceleration from a single point (seen 3 times)")).toBeTruthy();
    // Never shown as curated: the drafted root-gap link says it was not reviewed.
    expect(within(sheet).getByText("Suggested link: not yet reviewed by a teacher.")).toBeTruthy();
    expect(within(sheet).getByText(/This is really about the gradient of a straight line/)).toBeTruthy();
    const showGap = vi.spyOn(controller, "showGap");
    fireEvent.click(within(sheet).getByRole("button", { name: "Show the gap path" }));
    expect(showGap).toHaveBeenCalledWith({ misconceptionId: "mc.phy.o.vt_gradient_from_one_point", rootKcId: GRADIENT, kcId: VT });
    // The lit path reaches the drawing and the banner names its ends.
    rerender(wrap(<ConceptMapContent view={{ ...view, gap: { path: [GRADIENT, VT], misconceptionId: "mc.phy.o.vt_gradient_from_one_point" } }} onClearGap={() => undefined} />));
    expect(document.querySelector("[data-stub-gap]")!.getAttribute("data-stub-gap")).toBe(`${GRADIENT} ${VT}`);
    expect(document.querySelector("[data-gap-banner]")!.textContent).toContain("Gap path: from");
    fireEvent.keyDown(document.querySelector(`[data-concept-sheet="${VT}"]`)!, { key: "Escape" });
    expect(document.querySelector("[data-concept-sheet]")).toBeNull();
  });

  test("table_alternative_has_every_skill_and_its_links_in_words", () => {
    render(wrap(<ConceptMapContent view={{ status: "ready", subjectId: "cur.phy.o", map: CONCEPT, gap: null }} />));
    fireEvent.click(screen.getByRole("radio", { name: "Table" }));
    const table = document.querySelector<HTMLTableElement>("[data-concept-table]")!;
    expect(table.querySelectorAll("tbody tr")).toHaveLength(CONCEPT.nodes.length);
    const row = table.querySelector<HTMLElement>(`[data-row-kc="${VT}"]`)!;
    expect(row.textContent).toContain("may be the root of: Acceleration from a single point; not yet reviewed");
    expect(row.textContent).toContain("Asked 4 times");
    expect(row.textContent).toContain("Mistake: Acceleration from a single point");
  });

  test("states_without_a_map", () => {
    render(wrap(<ConceptMapContent view={{ status: "failed", subjectId: "cur.phy.o", map: null, gap: null }} onRetry={() => undefined} />));
    expect(screen.getByRole("alert").textContent).toContain("The map could not be loaded");
    cleanup();
    render(wrap(<ConceptMapContent view={{ status: "ready", subjectId: "cur.chm.o", map: { ...CONCEPT, status: "not_installed", nodes: [], edges: [], next: [], questions: [], mistakes: [] }, gap: null }} />));
    expect(document.querySelector("[data-concept-ready]")).toBeNull();
  });
});
