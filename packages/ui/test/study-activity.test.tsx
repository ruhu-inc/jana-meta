// SPEC §19.1 (W8 phase 1) on screen: what the learner did in Study shows on Progress as one quiet "Study activity"
// line and on "What the tutor knows" as evidence the tutor saw, in the pack's words, never as a mastery claim.
import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, test } from "vitest";
import { EMPTY_KNOWS, type KnowsView, type ProgressView } from "@jana/client-core";
import { STATES } from "../gallery/index.js";
import { LocaleProvider } from "../src/i18n.js";
import { KnowsContent } from "../src/memory/KnowsPage.js";
import { ProgressContent } from "../src/progress/Progress.js";

afterEach(() => cleanup());

const base = () => STATES.find((s) => s.id === "progress.canonical")!.payload.progress as ProgressView;

function progress(activity: ProgressView["study_activity"]) {
  const view = { ...base(), ...(activity !== undefined ? { study_activity: activity } : {}) };
  return render(
    <LocaleProvider locale="en">
      <ProgressContent state={{ status: "ready", progress: view }} names={{ subject: () => "Physics", kc: () => null }} actions={{ onRetry: () => undefined }} />
    </LocaleProvider>,
  );
}

describe("W8 Study activity", () => {
  test("Progress says the week's Study activity in one line, and nothing when there was none", () => {
    const { container } = progress({ quiz_items: 3, quiz_correct: 2, cards_reviewed: 1, aids_made: 2 });
    const line = container.querySelector("[data-progress-study]") as HTMLElement;
    expect(line.textContent).toBe("Study activity this week: 3 quiz questions, 2 right · 1 card reviewed · 2 study aids made");
    cleanup();
    expect(progress({ quiz_items: 0, quiz_correct: 0, cards_reviewed: 0, aids_made: 0 }).container.querySelector("[data-progress-study]")).toBeNull();
    cleanup();
    expect(progress(undefined).container.querySelector("[data-progress-study]")).toBeNull(); // an older core
  });

  test("the knows page lists Study activity as evidence the tutor saw, and says it never moves mastery", () => {
    const view: KnowsView = {
      ...EMPTY_KNOWS, status: "ready", about: { level: "O", subjects: ["physics"], exam_date: null }, memory_saving: true, sharing: null,
      activity: [
        { activity: "quiz_item", kc_id: "kc.phy.o.motion.solve_with_equation", statement: "Solve for an unknown quantity with an equation of uniform acceleration",
          result: "incorrect", aid_kind: null, count: null, day: "2026-11-04" },
        { activity: "card_review", kc_id: null, statement: null, result: "again", aid_kind: null, count: null, day: "2026-11-04" },
        { activity: "aid_made", kc_id: null, statement: null, result: null, aid_kind: "flashcards", count: 10, day: "2026-11-03" },
      ],
    };
    const { container } = render(<LocaleProvider locale="en"><KnowsContent view={view} onForget={() => undefined} /></LocaleProvider>);
    const section = container.querySelector('[data-section="study"]') as HTMLElement;
    const lines = [...section.querySelectorAll("[data-study-activity]")].map((l) => l.textContent);
    expect(lines).toEqual([
      "Study quiz: Solve for an unknown quantity with an equation of uniform acceleration · not right yet · 2026-11-04",
      "Study review: your own material · again · 2026-11-04",
      "Made flashcards (10) · 2026-11-03",
    ]);
    expect(section.textContent).toContain("never changes how secure an idea is marked");
    expect(section.textContent).not.toContain("kc.phy");
  });
});
