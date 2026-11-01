// Practice keeps two controls while answering (W11, "Simpler by default"): Check my answer and Need help?. Need help?
// discloses every kind of help that exists (ASM-28: the hint, walk-through and explain-simply chips, and "Don't know"),
// the separate Stuck? panel is gone, and tries before the newest fold into a collapsed "Earlier attempts" disclosure.
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { EMPTY_PRACTICE, type PracticeItem, type PracticeMarked, type PracticeTry } from "@jana/client-core";
import { LocaleProvider } from "../src/i18n.js";
import { PracticeContent, type PracticeActions } from "../src/learn/Practice.js";

afterEach(cleanup);

const ITEM: PracticeItem = {
  item_id: "itm.mth.o.number.0001", pack_id: "pack.mth.o", pack_version: "1.0.0", kc_ids: ["kc.mth.o.number.add"],
  kind: "numeric", stem: "Synthetic: 2 + 3.", visual: null, marks: 1,
  parts: [{ part_id: "a", prompt: "Give your answer.", uses_parts: [], marks: 1, input: { kind: "numeric" } }],
} as PracticeItem;

function tryOf(verdict: PracticeMarked["verdict"], value: string, n: number): PracticeTry {
  const marked = { attempt_id: `att_${String(n).repeat(26)}`, verdict, marks_awarded: verdict === "correct" ? 1 : 0, marks_total: 1, feedback_key: "",
    first_error: null, mastery_change: { kc_id: "kc.mth.o.number.add", band_before: "learning", band_after: "learning" }, next_item: null } as unknown as PracticeMarked;
  return { answers: [{ part_id: "a", kind: "numeric", value, unit: null }], marked } as PracticeTry;
}

function show(tries: PracticeTry[], closed: boolean, actions: Partial<PracticeActions> = {}) {
  const all: PracticeActions = { onAnswer: vi.fn(), onNext: vi.fn(), onEnd: vi.fn(), onHelp: vi.fn(), onDontKnow: vi.fn(), ...actions };
  render(<LocaleProvider locale="en"><PracticeContent view={{ ...EMPTY_PRACTICE, status: "ready", item: ITEM, subject: "mathematics", total: 2, number: 1, closed, tries }} actions={all} /></LocaleProvider>);
  return all;
}

test("while answering, only Check my answer and Need help? are offered and no Stuck? panel sits beside the question", () => {
  show([], false);
  const buttons = screen.getAllByRole("button").map((b) => b.textContent);
  expect(buttons).toContain("Check my answer");
  expect(buttons).toContain("Need help?");
  expect(buttons).not.toContain("Don't know");
  expect(buttons).not.toContain("Give me a hint");
  expect(screen.queryByRole("heading", { name: "Stuck?" })).toBeNull();
  expect(screen.queryByRole("complementary")).toBeNull();
  expect(screen.getByRole("button", { name: "Need help?" }).getAttribute("aria-expanded")).toBe("false");
});

test("Need help? reveals every help kind with the same semantics as before", () => {
  const actions = show([], false);
  const need = screen.getByRole("button", { name: "Need help?" });
  fireEvent.click(need);
  expect(need.getAttribute("aria-expanded")).toBe("true");
  const panel = document.getElementById(need.getAttribute("aria-controls")!)!;
  expect(within(panel).getByText("Have a go first")).toBeDefined(); // PED-05: hints follow a first attempt
  const chips = within(panel).getByRole("group", { name: "Help with this question" });
  for (const name of ["Give me a hint", "Walk me through it", "Explain simply"]) fireEvent.click(within(chips).getByRole("button", { name }));
  expect(vi.mocked(actions.onHelp!).mock.calls.map((c) => c[0])).toEqual(["hint", "walk_through", "explain_simply"]);
  fireEvent.click(within(panel).getByRole("button", { name: "Don't know" }));
  expect(actions.onDontKnow).toHaveBeenCalledTimes(1);
  fireEvent.click(need);
  expect(need.getAttribute("aria-expanded")).toBe("false");
  expect(screen.queryByRole("button", { name: "Give me a hint" })).toBeNull(); // folded away again
});

test("a first miss keeps the question open with a second try and help, and never shows the answer", () => {
  show([tryOf("incorrect", "4", 1)], false);
  expect(screen.getByRole("button", { name: "Check again" })).toBeDefined();
  fireEvent.click(screen.getByRole("button", { name: "Need help?" }));
  expect(screen.getByText("Hints are open")).toBeDefined();
  expect(document.querySelector("[data-second-try]")).not.toBeNull();
  expect(document.querySelector("[data-worked]")).toBeNull();
  expect(screen.queryByRole("button", { name: /earlier attempt/ })).toBeNull(); // one try: nothing to fold
});

test("earlier attempts are collapsed under the newest mark until opened", () => {
  show([tryOf("incorrect", "4", 1), tryOf("correct", "5", 2)], true);
  expect(within(document.querySelector<HTMLElement>("[data-latest-try]")!).getByText(/Try 2/)).toBeDefined();
  const fold = screen.getByRole("button", { name: "1 earlier attempt" });
  expect(fold.getAttribute("aria-expanded")).toBe("false");
  const first = document.querySelector<HTMLElement>("[data-try='1']")!;
  expect(first.closest("[aria-hidden='true']")).not.toBeNull();
  fireEvent.click(fold);
  expect(fold.getAttribute("aria-expanded")).toBe("true");
  expect(first.closest("[aria-hidden='true']")).toBeNull();
  expect(within(document.querySelector<HTMLElement>("[data-earlier-attempts]")!).getByText(/Try 1/)).toBeDefined();
});
