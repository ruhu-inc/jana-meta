// SPEC §10.7: the unit field and the unit chips (°C, Ω, powers) show only when the item's answer has a unit.
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { EMPTY_PRACTICE, type PracticeItem } from "@jana/client-core";
import { LocaleProvider } from "../src/i18n.js";
import { PracticeContent } from "../src/learn/Practice.js";

afterEach(cleanup);

const item = (unitExpected: boolean | undefined, unitPrompt: string | null = null): PracticeItem => ({
  item_id: "itm.mth.o.number.0001", pack_id: "pack.mth.o", pack_version: "1.0.0", kc_ids: ["kc.mth.o.number.x"],
  kind: "numeric", stem: "Synthetic question.", visual: null, marks: 1,
  parts: [{ part_id: "a", prompt: "Give your answer.", uses_parts: [], marks: 1,
    input: { kind: "numeric", unit_prompt: unitPrompt, ...(unitExpected === undefined ? {} : { unit_expected: unitExpected }) } }],
});

function show(question: PracticeItem, onAnswer = vi.fn()) {
  render(<LocaleProvider locale="en"><PracticeContent
    view={{ ...EMPTY_PRACTICE, status: "ready", item: question, subject: "mathematics", total: 1, number: 1 }}
    actions={{ onAnswer, onNext: vi.fn(), onEnd: vi.fn() }} /></LocaleProvider>);
  return onAnswer;
}

test("a unitless numeric answer has no unit field and no unit chips", () => {
  const onAnswer = show(item(false));
  expect(screen.queryByRole("textbox", { name: "Unit" })).toBeNull();
  expect(screen.queryByRole("button", { name: /degrees Celsius/i })).toBeNull();
  expect(screen.queryByRole("button", { name: /ohm/i })).toBeNull();
  expect(screen.queryByText("°C")).toBeNull();
  expect(screen.queryByText("Ω")).toBeNull();
  fireEvent.change(screen.getByRole("textbox", { name: "Your answer" }), { target: { value: "12" } });
  fireEvent.click(screen.getByRole("button", { name: "Check my answer" }));
  expect(onAnswer.mock.calls[0]?.[0]).toEqual([{ part_id: "a", kind: "numeric", value: "12", unit: null }]);
});

test.each([[true, null], [true, "°C"], [undefined, null]] as const)("an answer with a unit keeps the field and the chips (expected %s, prompt %s)", (expected, prompt) => {
  show(item(expected, prompt));
  expect(screen.getByRole("textbox", { name: "Unit" })).toBeTruthy();
  expect(screen.getByText("°C")).toBeTruthy();
  expect(screen.getByText("Ω")).toBeTruthy();
});
