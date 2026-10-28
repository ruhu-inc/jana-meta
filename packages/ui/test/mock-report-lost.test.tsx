// The mock report's "Where the marks went": marks lost on questions left unanswered are counted as such, never as
// method, accuracy or independent marks the learner lost on an answer they gave. Rendered from the gallery's
// data-only marked state (engine output).
import { cleanup, render } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";
import { EMPTY_MOCKS, type MockView } from "@jana/client-core";
import { STATES } from "../gallery/index.js";
import { MockContent, type MockActions } from "../src/mock/MockExam.js";
import { LocaleProvider } from "../src/i18n.js";

afterEach(() => cleanup());

const noop = () => undefined;
const actions: MockActions = { onChoose: noop, onOpen: noop, onStart: noop, onPause: noop, onResume: noop, onShow: noop, onAnswer: noop, onFlag: noop,
  onClear: noop, onSubmit: noop, onRetryMark: noop, onLeave: noop };

function report(change: (result: NonNullable<MockView["result"]>) => NonNullable<MockView["result"]> = (r) => r) {
  const found = STATES.find((s) => s.id === "mock-sitting.canonical.marked");
  expect(found).toBeDefined();
  const view = (found!.payload as { view: Partial<MockView> }).view;
  const { container } = render(<LocaleProvider locale="en"><MockContent view={{ ...EMPTY_MOCKS, status: "ready", ...view, result: change(view.result!), readAt: 0, listedAt: 0 }}
    now={0} actions={actions} subjects={[{ subject: "physics", label: "Physics" }]} names={{ topic: (t) => t, kc: (k) => k }} /></LocaleProvider>);
  return container.textContent ?? "";
}

test("marks lost on an unanswered question are reported as not answered", () => {
  // Question 4 (one B mark) was not answered: the answered questions lost 1 accuracy and 1 independent mark.
  const text = report();
  expect(text).toContain("Marks lost on your answers: 0 for method, 1 for accuracy, 1 for independent marks");
  expect(text).toContain("1 mark on questions you didn’t answer");
});

test("a paper left entirely unanswered never reports lost answer marks", () => {
  const text = report((r) => ({ ...r, score: 0, unanswered: r.criteria!.map((row) => row.question_id),
    criteria: r.criteria!.map((row) => ({ ...row, criteria: row.criteria.map((c) => ({ ...c, awarded: 0 })) })) }));
  expect(text).not.toContain("Marks lost on your answers");
  expect(text).not.toContain("marked on their own");
  expect(text).toContain("5 marks on questions you didn’t answer");
});
