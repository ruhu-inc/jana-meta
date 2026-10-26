import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { EMPTY_ASSESSMENTS, type Assessment, type AssessmentView } from "@jana/client-core";
import { EXPLAINING, FOLLOW_UP, assessment } from "../../client-core/test/assessmentcore.js";
import { AssessmentContent, type AssessmentActions } from "../src/learn/Assessment.js";

afterEach(cleanup);
const names = { subject: () => "Physics", topic: () => "Motion", kc: () => "Speed" };
function show(current: Assessment | null, flags: Partial<AssessmentView> = {}) {
  const noop = vi.fn();
  const actions: AssessmentActions = { onStart: noop, onOpen: noop, onAnswer: noop, onExplain: vi.fn(), onStop: noop, onResume: noop, onRefresh: noop, onRetry: noop, onList: noop, onClose: noop };
  render(<AssessmentContent view={{ ...EMPTY_ASSESSMENTS, status: "ready", current, ...flags }} subjects={["physics"]} names={names} actions={actions} />);
  return actions;
}
test("uxs40_no_score_shown", () => {
  for (const state of ["in_progress", "completed", "stopped"] as const) {
    show({ ...assessment(), state, current_item: state === "in_progress" ? assessment().current_item : null }, { saved: true, resumed: true });
    expect(document.body.textContent).not.toMatch(/\b(score|percentage|correct|incorrect|marks?)\b|%/i);
    expect(screen.queryByRole("timer")).toBeNull();
    expect(screen.queryByRole("button", { name: /hint|Help me|tutor/ })).toBeNull();
    cleanup();
  }
});
test("diagnostic saves a complete answer, skips unseen material and offers finish later", () => {
  const actions = show(assessment());
  expect((screen.getByRole("button", { name: "Save answer" }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByLabelText("First option"));
  fireEvent.click(screen.getByRole("button", { name: "Save answer" }));
  expect(actions.onAnswer).toHaveBeenCalledWith([{ part_id: "a", kind: "mcq", option_id: "a" }]);
  fireEvent.click(screen.getByRole("button", { name: "I haven't learned this yet" }));
  expect(actions.onAnswer).toHaveBeenCalledWith(null);
  fireEvent.click(screen.getByRole("button", { name: "Finish later" })); expect(actions.onStop).toHaveBeenCalled();
});
test("uxs41_no_help_during_check", () => {
  for (const state of ["in_progress", "waiting", "completed", "failed", "stopped"] as const) {
    show({ ...assessment("mastery_check"), state, current_item: state === "in_progress" ? assessment("mastery_check").current_item : null, retry_at: "2026-10-20T10:00:00Z" });
    expect(screen.queryByRole("button", { name: /hint|Help me|tutor|haven't learned/i })).toBeNull();
    fireEvent.keyDown(document, { altKey: true, key: "h" });
    expect(screen.queryByRole("textbox", { name: /Ask/i })).toBeNull();
    cleanup();
  }
});
test("uxs41_outcome_copy", () => {
  show({ ...assessment("mastery_check"), state: "waiting", current_item: null, available_at: "2026-10-20T10:00:00Z" });
  expect(screen.getByText("Good. The last question comes on 20 October 2026, so we know it sticks.")).toBeTruthy(); cleanup();
  show({ ...assessment("mastery_check"), state: "completed", current_item: null });
  expect(screen.getByText("Speed: Nearly secure to Secure")).toBeTruthy(); cleanup();
  show({ ...assessment("mastery_check"), state: "failed", current_item: null, retry_at: "2026-10-20T10:00:00Z" });
  expect(screen.getByText("Not this time. We'll practise a bit more, and you can try again from 20 October 2026.")).toBeTruthy();
});
test("an uncertain save freezes the original answer until retry resolves it", () => {
  const actions = show(assessment(), { uncertain: true, error: "unreachable" });
  expect((screen.getByLabelText("First option") as HTMLInputElement).disabled || screen.getByLabelText("First option").closest("fieldset[disabled]") !== null).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "Try again" })); expect(actions.onRetry).toHaveBeenCalled();
  expect((screen.getByRole("button", { name: "Close" }) as HTMLButtonElement).disabled).toBe(true);
});
const explaining = (explain: Partial<NonNullable<Assessment["explain"]>> = {}): Assessment =>
  ({ ...assessment("mastery_check", 3), state: "explaining", current_item: null, explain: { ...EXPLAINING, ...explain } });
test("explain it back: after three right answers the learner explains the idea before it counts as Secure", () => {
  const actions = show(explaining());
  expect(screen.getByRole("heading", { name: "Explain it in your own words" })).toBe(document.activeElement);
  expect(screen.getByText(/One more step before this counts as Secure/).textContent).toContain(EXPLAINING.statement);
  const check = screen.getByRole("button", { name: "Check my explanation" }) as HTMLButtonElement;
  expect(check.disabled).toBe(true);
  fireEvent.change(screen.getByLabelText("Your explanation"), { target: { value: "  The change in velocity over the time.  " } });
  fireEvent.click(check);
  expect(actions.onExplain).toHaveBeenCalledWith("The change in velocity over the time.");
  expect(screen.queryByRole("button", { name: /hint|Help me|tutor/i })).toBeNull(); // still no help during a check
});
test("explain it back: a miss shows one follow-up question, never the key point", () => {
  show(explaining({ attempts: 1, outcome: "follow_up", follow_up: FOLLOW_UP }));
  expect(screen.getByText("One more question")).toBeTruthy();
  expect(screen.getByText(FOLLOW_UP)).toBeTruthy();
  cleanup();
  show(explaining({ outcome: "unavailable" }));
  expect(screen.getByText("Your explanation couldn't be checked just now, so it wasn't counted. Try again in a moment.")).toBeTruthy();
  cleanup();
  show({ ...explaining({ attempts: 2, outcome: "not_yet" }), state: "failed", retry_at: "2026-10-20T10:00:00Z" });
  expect(screen.getByText("The answers were right, but the explanation isn't there yet. Practise the idea a little more, then explain it again.")).toBeTruthy();
  expect(screen.queryByLabelText("Your explanation")).toBeNull();
});
