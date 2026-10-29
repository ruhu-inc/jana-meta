// SPEC §19.9 `knows-confidence.test.tsx` (W8 phase 3, §19.5.6, §19.6): on "What the tutor knows", each note says where
// it stands, from the fields the core derives (never a model's): tentative or supported, fading, and the number of
// sessions the tutor recalled it in; a note waiting for the student's decision says "Not sure this is still right"; a
// note the scrub kept from the online tutor is marked as kept on this computer. Under "Why your plan looks like this",
// the companion's rolling summary shows its topics with session counts and its next step, as labels. An older core's
// note (no derived fields) reads as tentative and nothing more.
import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, test } from "vitest";
import { EMPTY_KNOWS, type KnowsNote, type KnowsView } from "@jana/client-core";
import { LocaleProvider } from "../src/i18n.js";
import { KnowsContent } from "../src/memory/KnowsPage.js";

afterEach(() => cleanup());

const note = (n: number, extra: Partial<KnowsNote>): KnowsNote => ({
  note_id: `mem_${String(n).padStart(26, "0")}`, text: `Note ${n}`, status: "active", source: "reflector", flagged: false, subject: "physics",
  created_ts: 1_760_000_000_000 - n, updated_ts: 1_760_000_000_000 - n, ...extra,
});

const NOTES: KnowsNote[] = [
  note(1, { text: "Starts projectile questions by drawing the axes.", confidence: "supported", fading: false, recall_sessions: 4, withheld_online: false }),
  note(2, { text: "Mixes up <b>mass</b> and weight.", confidence: "tentative", fading: false, recall_sessions: 1 }),
  note(3, { text: "Prefers worked examples first.", confidence: "supported", fading: true, recall_sessions: 0, withheld_online: true }),
  note(4, { text: "Revises on Sunday evenings.", status: "pending_review", confidence: "tentative" }),
  note(5, { text: "Likes short sessions." }), // an older core: no derived fields
];

function view(extra: Partial<KnowsView> = {}): KnowsView {
  return { ...EMPTY_KNOWS, status: "ready", about: { level: "O", subjects: ["physics"], exam_date: null }, memory_saving: true, sharing: null, notes: NOTES, ...extra };
}

const page = (v: KnowsView) => render(<LocaleProvider locale="en"><KnowsContent view={v} onForget={() => undefined} /></LocaleProvider>);
const row = (container: HTMLElement, n: number) => container.querySelector(`[data-note-id="${NOTES[n - 1]!.note_id}"]`) as HTMLElement;
const labels = (el: HTMLElement) => [...el.querySelectorAll("[data-note-label]")].map((l) => l.textContent?.replace(/^·\s*/, ""));

describe("W8 note lifecycle on the knows page", () => {
  test("each note is labelled tentative or supported, and fading after 90 days without new evidence", () => {
    const { container } = page(view());
    expect(labels(row(container, 1))).toEqual(["Supported"]);
    expect(labels(row(container, 2))).toEqual(["Tentative"]);
    expect(labels(row(container, 3))).toEqual(["Supported", "Fading"]);
    expect(row(container, 3).getAttribute("data-fading")).toBe("true");
    expect(labels(row(container, 5))).toEqual(["Tentative"]); // an older core: the defaults
    expect(container.querySelector('[data-section="notes"]')?.textContent).toContain("A note is tentative until");
  });

  test("the recall count is shown when the tutor recalled the note, in sessions", () => {
    const { container } = page(view());
    expect(row(container, 1).querySelector("[data-note-recalled]")?.textContent).toBe("· Recalled in 4 sessions");
    expect(row(container, 2).querySelector("[data-note-recalled]")?.textContent).toBe("· Recalled in 1 session");
    for (const n of [3, 4, 5]) expect(row(container, n).querySelector("[data-note-recalled]")).toBeNull();
  });

  test("a note withheld from the online tutor is marked as kept on this computer", () => {
    const { container } = page(view());
    expect(row(container, 3).querySelector("[data-note-withheld]")?.textContent).toBe("Kept on this computer: the online tutor doesn't see this note.");
    for (const n of [1, 2, 4, 5]) expect(row(container, n).querySelector("[data-note-withheld]")).toBeNull();
  });

  test("a note waiting for the student's decision says it may no longer be right", () => {
    const { container } = page(view());
    expect(row(container, 4).querySelector("[data-note-pending]")?.textContent).toBe("Not sure this is still right");
    for (const n of [1, 2, 3, 5]) expect(row(container, n).querySelector("[data-note-pending]")).toBeNull();
  });

  test("note text stays text", () => {
    const { container } = page(view());
    expect(row(container, 2).querySelector("b")).toBeNull();
    expect(row(container, 2).textContent).toContain("Mixes up <b>mass</b> and weight.");
  });
});

describe("W8 the companion's rolling summary under the plan", () => {
  test("its topics with session counts and its next step show under Why your plan looks like this", () => {
    const { container } = page(view({
      plan_reason: "weak_high_value",
      companion_summary: {
        version: 4, cursor_seq: 120, updated_at: "2026-10-29T10:00:00Z", episodes: 3,
        topics: [
          { kc_id: "kc.phy.o.motion.solve_with_equation", label: "Equations of motion", sessions: 3, last_at: "2026-10-28T18:00:00Z" },
          { kc_id: "kc.phy.o.forces.weight", label: "Mass and weight", sessions: 1, last_at: "2026-10-27T18:00:00Z" },
        ],
        misconceptions: [],
        next_step: { text: "Practise equations of motion", reason_code: "weak_high_value", updated_at: "2026-10-29T07:00:00Z" },
      },
    }));
    const plan = container.querySelector('[data-section="plan"]') as HTMLElement;
    expect(plan.querySelector("h2")?.textContent).toBe("Why your plan looks like this");
    const summary = plan.querySelector("[data-companion-summary]") as HTMLElement;
    expect([...summary.querySelectorAll("[data-summary-kc]")].map((l) => l.textContent)).toEqual(["Equations of motion · 3 sessions", "Mass and weight · 1 session"]);
    expect(summary.querySelector("[data-summary-next]")?.textContent).toBe("Next step: Practise equations of motion");
    expect(summary.textContent).not.toContain("kc.phy");
  });

  test("nothing is added without a summary or with an empty one", () => {
    for (const companion_summary of [undefined, null, { version: 0, cursor_seq: 0, updated_at: null, topics: [], misconceptions: [], next_step: null, episodes: 0 }]) {
      const { container } = page(view(companion_summary === undefined ? {} : { companion_summary }));
      expect(container.querySelector("[data-companion-summary]")).toBeNull();
      cleanup();
    }
  });
});
