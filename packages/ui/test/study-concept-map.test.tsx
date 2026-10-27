// A Study concept map in the UI: every box says where it came from in words (from your document, curated skill,
// from Muse Spark with no source, added by you); a document concept's sheet shows its cited summary and the skill it
// matches; a no-source map says so above the map; the learner's rename, merge, remove and add reach the controller as
// edits; the concept actions (ask Jana, flashcards, quiz) carry the concept's name. The drawing is a stand-in (the
// renderer's own tests draw it); the table carries the same concepts.
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, test, vi } from "vitest";
import type { StudyContracts as W } from "@jana/client-core";
import { LocaleProvider } from "../src/i18n.js";
import { ConceptMapRendererProvider, type ConceptMapRenderer } from "../src/learn/ConceptMap.js";
import { StudyConceptMap } from "../src/learn/StudyConceptMap.js";

afterEach(() => cleanup());

const quote = "Acceleration is the rate of change of velocity.";
const cite: W.Claim = { text: quote, citations: [{ source_id: `src_${"1".repeat(26)}`, revision: 1, chunk_id: `sck_${"2".repeat(26)}`, start: 0, end: quote.length, quote }] };
const DOC: W.StudyConceptMap = {
  edited: false,
  concepts: [
    { concept_id: "c1", name: "Velocity", summary: { ...cite, text: "Velocity is speed in a given direction." }, note: null, origin: "document", anchor: { kc_id: "kc.phy.o.motion.distance_or_displacement", statement: "Tell distance from displacement and speed from velocity", how: "glossary" } },
    { concept_id: "c2", name: "Acceleration", summary: cite, note: null, origin: "document", anchor: null },
    { concept_id: "u1", name: "My own idea", summary: null, note: null, origin: "learner", anchor: null },
  ],
  relations: [{ from: "c1", to: "c2", type: "builds_on", claim: cite, origin: "document" }],
};
const SPARK: W.StudyConceptMap = { edited: false, concepts: [{ concept_id: "s1", name: "Refraction", summary: null, note: "Light bends as it enters a new medium.", origin: "model", anchor: null }], relations: [] };

const Drawing: ConceptMapRenderer = ({ nodes, onActivate }) => (
  <div role="group">{nodes.map((n) => <button type="button" key={n.id} data-node={n.id} data-look={n.state} onClick={() => onActivate(n.id)}>{n.title} · {n.stateWord}{n.badge ? ` · ${n.badge}` : ""}</button>)}</div>
);
const claim = (c: W.Claim) => <p data-claim={c.citations.length}>{c.text}</p>;

function show(node: ReactNode) {
  return render(<LocaleProvider locale="en"><ConceptMapRendererProvider value={Drawing}>{node}</ConceptMapRendererProvider></LocaleProvider>);
}

describe("study concept map", () => {
  test("origins_in_words_cited_summary_and_anchor", () => {
    show(<StudyConceptMap map={DOC} claim={claim} />);
    expect(document.querySelector('[data-node="c1"]')!.textContent).toBe("Velocity · From your document · Matches a syllabus skill");
    expect(document.querySelector('[data-node="u1"]')!.textContent).toBe("My own idea · Added by you");
    expect(document.querySelector("[data-no-source]")).toBeNull();
    fireEvent.click(document.querySelector('[data-node="c1"]')!);
    const sheet = document.querySelector<HTMLElement>('[data-study-concept="c1"]')!;
    expect(within(sheet).getByText("Velocity is speed in a given direction.").getAttribute("data-claim")).toBe("1");
    expect(within(sheet).getByText("Matches the syllabus skill: Tell distance from displacement and speed from velocity")).toBeTruthy();
    expect(within(sheet).getByText("Acceleration builds on Velocity")).toBeTruthy();
    expect(sheet.querySelectorAll("[data-claim]")).toHaveLength(2); // the summary and the relation's claim
  });

  test("a_no_source_map_says_so", () => {
    show(<StudyConceptMap map={SPARK} claim={claim} />);
    expect(document.querySelector("[data-no-source]")!.textContent).toContain("no source document");
    expect(document.querySelector('[data-node="s1"]')!.textContent).toBe("Refraction · From Muse Spark, no source");
    fireEvent.click(document.querySelector('[data-node="s1"]')!);
    expect(screen.getByText("Light bends as it enters a new medium.")).toBeTruthy();
  });

  test("edits_and_actions_reach_the_controller", () => {
    const onEdit = vi.fn(), onAsk = vi.fn(), onQuiz = vi.fn(), onFlashcards = vi.fn();
    show(<StudyConceptMap map={DOC} claim={claim} onEdit={onEdit} actions={{ onAsk, onQuiz, onFlashcards }} />);
    fireEvent.click(document.querySelector('[data-node="c2"]')!);
    const sheet = document.querySelector<HTMLElement>('[data-study-concept="c2"]')!;
    fireEvent.click(within(sheet).getByRole("button", { name: "Ask the tutor" }));
    fireEvent.click(within(sheet).getByRole("button", { name: "Quiz me" }));
    fireEvent.click(within(sheet).getByRole("button", { name: "Make flashcards" }));
    expect([onAsk.mock.calls[0], onQuiz.mock.calls[0], onFlashcards.mock.calls[0]]).toEqual([["Acceleration"], ["Acceleration"], ["Acceleration"]]);
    fireEvent.change(within(sheet).getByLabelText("Name"), { target: { value: "Acceleration (a)" } });
    fireEvent.click(within(sheet).getByRole("button", { name: "Rename" }));
    expect(onEdit).toHaveBeenLastCalledWith([{ op: "rename", concept_id: "c2", name: "Acceleration (a)" }]);
    fireEvent.change(within(sheet).getByLabelText("Merge with"), { target: { value: "c1" } });
    fireEvent.click(within(sheet).getByRole("button", { name: "Merge" }));
    expect(onEdit).toHaveBeenLastCalledWith([{ op: "merge", concept_ids: ["c2", "c1"], name: "Acceleration (a)" }]);
    fireEvent.change(screen.getByLabelText("Add a concept"), { target: { value: "Gradient" } });
    fireEvent.click(screen.getByRole("button", { name: "Add" }));
    expect(onEdit).toHaveBeenLastCalledWith([{ op: "add", name: "Gradient", link_to: "c2" }]);
    fireEvent.click(within(sheet).getByRole("button", { name: "Remove from the map" }));
    expect(onEdit).toHaveBeenLastCalledWith([{ op: "remove", concept_id: "c2" }]);
  });

  test("table_alternative", () => {
    show(<StudyConceptMap map={DOC} claim={claim} />);
    fireEvent.click(screen.getByRole("radio", { name: "Table" }));
    const table = document.querySelector<HTMLTableElement>("[data-study-concept-table]")!;
    expect(table.querySelectorAll("tbody tr")).toHaveLength(3);
    expect(table.querySelector('[data-row-concept="c1"]')!.textContent).toContain("Acceleration builds on Velocity");
    expect(table.querySelector('[data-row-concept="c1"]')!.textContent).toContain("Matches a syllabus skill");
  });
  test("a_research_packs_map_says_its_concepts_came_from_the_web", () => {
    show(<StudyConceptMap map={DOC} claim={claim} fromWeb />);
    expect(document.querySelector('[data-node="c1"]')!.textContent).toBe("Velocity · From the web · Matches a syllabus skill");
    expect(document.body.textContent).not.toContain("From your document");
  });
  test("a_research_packs_outline_reads_as_a_tree_from_its_topic", () => {
    const outlined: W.StudyConceptMap = { edited: false,
      concepts: [{ concept_id: "t1", name: "Heart valves", summary: null, note: "Heart valves", origin: "outline", anchor: null },
        { concept_id: "q1", name: "What do the valves do?", summary: null, note: "What do the valves do?", origin: "outline", anchor: null },
        ...DOC.concepts],
      relations: [{ from: "t1", to: "q1", type: "includes", claim: null, origin: "outline" },
        { from: "q1", to: "c1", type: "includes", claim: null, origin: "outline" }, ...DOC.relations] };
    show(<StudyConceptMap map={outlined} claim={claim} fromWeb />);
    expect(document.querySelector('[data-node="t1"]')!.textContent).toBe("Heart valves · Your pack's plan");
    expect(document.body.textContent).toContain("From the topic to each question the research answered");
  });
});
