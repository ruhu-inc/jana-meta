// The mock paper catalogue (UXS-25) after the "long catalogue" review finding: a subject first, then that subject's
// papers as compact rows by paper kind, each with its time and question count and one action. Rendered from the
// gallery's data-only states (engine output).
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";
import { EMPTY_MOCKS, type MockView } from "@jana/client-core";
import { GalleryView, STATES } from "../gallery/index.js";
import { MockContent, type MockActions, type MockSubject } from "../src/mock/MockExam.js";
import { LocaleProvider } from "../src/i18n.js";

afterEach(() => cleanup());

const state = (id: string) => {
  const found = STATES.find((s) => s.id === id);
  expect(found, id).toBeDefined();
  return found!;
};

const noop = () => undefined;
const SUBJECTS: MockSubject[] = [{ subject: "mathematics", label: "Mathematics" }, { subject: "physics", label: "Physics" }];

function catalogue(change: (view: Partial<MockView>) => Partial<MockView> = (v) => v, subjects: MockSubject[] = SUBJECTS, actions: Partial<MockActions> = {}) {
  const payload = state("mock-papers.canonical").payload as { view: Partial<MockView>; extraPercent: number };
  const all: MockActions = { onChoose: noop, onOpen: noop, onStart: noop, onPause: noop, onResume: noop, onShow: noop, onAnswer: noop, onFlag: noop,
    onClear: noop, onSubmit: noop, onRetryMark: noop, onLeave: noop, ...actions };
  return render(<LocaleProvider locale="en"><MockContent view={{ ...EMPTY_MOCKS, status: "ready", ...change(payload.view), readAt: 0, listedAt: 0 }} now={0} actions={all}
    subjects={subjects} extraPercent={payload.extraPercent} names={{ topic: (t) => t, kc: (k) => k }} /></LocaleProvider>);
}

const rows = (container: HTMLElement) => [...container.querySelectorAll("[data-paper-id]")].map((n) => n.getAttribute("data-paper-id"));

test("the catalogue asks for a subject first and lists compact rows with duration and question count", () => {
  const { container } = render(<GalleryView state={state("mock-papers.canonical")} />);
  const choice = screen.getByRole("radiogroup", { name: "Subject" });
  expect(within(choice).getAllByRole("radio").map((r) => r.textContent)).toEqual(["Mathematics", "Physics"]);
  expect(within(choice).getByRole("radio", { name: "Mathematics" }).getAttribute("aria-checked")).toBe("true");
  // Only the chosen subject's papers show, as rows, not cards: the maths paper, under its kind.
  expect(rows(container)).toEqual(["mck.mth.o.0006"]);
  expect(container.querySelector("[data-mock-subject]")?.getAttribute("data-mock-subject")).toBe("mathematics");
  expect(container.querySelector('[data-paper-kind="section_mock"] h3')?.textContent).toContain("Section mock");
  const row = container.querySelector('[data-paper-id="mck.mth.o.0006"]')!;
  expect(row.textContent).toContain("30 minutes · 24 questions · No calculator · With your extra time: 38 minutes");
  expect(row.textContent).not.toContain("24 marks");
  expect(within(row as HTMLElement).getAllByRole("button").map((b) => b.textContent)).toEqual(["Start"]);
  // The other subject is one click away, its papers grouped by paper kind.
  fireEvent.click(within(choice).getByRole("radio", { name: "Physics" }));
  expect(rows(container)).toEqual(["mck.phy.o.0001", "mck.phy.o.0003"]);
  expect([...container.querySelectorAll("[data-paper-kind]")].map((n) => n.getAttribute("data-paper-kind"))).toEqual(["paper_1_objective", "paper_2_structured"]);
  expect(container.querySelector('[data-paper-id="mck.phy.o.0001"]')?.textContent).toContain("60 minutes · 4 questions · Calculator allowed");
  // The student's mocks keep their list above the papers.
  expect(container.querySelector('[data-sitting-state="marked"]')?.textContent).toContain("31 out of 40");
});

test("starting a paper from its row chooses that paper", () => {
  const chosen: string[] = [];
  const { container } = catalogue((v) => v, SUBJECTS, { onChoose: (paperId) => chosen.push(paperId) });
  fireEvent.click(within(container.querySelector('[data-paper-id="mck.mth.o.0006"]') as HTMLElement).getByRole("button", { name: "Start" }));
  expect(chosen).toEqual(["mck.mth.o.0006"]);
});

test("with one subject installed it is preselected and the subject choice is not shown", () => {
  const { container } = catalogue((v) => v, [{ subject: "physics", label: "Physics" }]);
  expect(screen.queryByRole("radiogroup")).toBeNull();
  expect(container.querySelector("[data-mock-subject]")?.getAttribute("data-mock-subject")).toBe("physics");
  expect(rows(container)).toEqual(["mck.phy.o.0001", "mck.phy.o.0003"]);
});

test("the paper of an open sitting offers Continue while the other papers wait", () => {
  const opened: string[] = [];
  const { container } = catalogue((v) => ({ ...v, sittings: [{ exam_id: "exm_01JABCDEFGHJKMNPQRSTVWXYZ9", paper_id: "mck.phy.o.0001", state: "paused", remaining_ms: 600000, score: null, max_score: null }] }),
    SUBJECTS, { onOpen: (examId) => opened.push(examId) });
  expect(container.textContent).toContain("Finish or submit the mock you've started before choosing another.");
  expect(within(container.querySelector('[data-paper-id="mck.mth.o.0006"]') as HTMLElement).getByRole("button", { name: "Start" })).toHaveProperty("disabled", true);
  fireEvent.click(screen.getByRole("radio", { name: "Physics" }));
  const paused = container.querySelector('[data-paper-id="mck.phy.o.0001"]') as HTMLElement;
  expect(within(paused).queryByRole("button", { name: "Start" })).toBeNull();
  fireEvent.click(within(paused).getByRole("button", { name: "Continue" }));
  expect(opened).toEqual(["exm_01JABCDEFGHJKMNPQRSTVWXYZ9"]);
  expect(within(container.querySelector('[data-paper-id="mck.phy.o.0003"]') as HTMLElement).getByRole("button", { name: "Start" })).toHaveProperty("disabled", true);
});

test("imported past papers are compact rows with their time, question count, marking and actions", () => {
  const { container } = render(<GalleryView state={state("past-papers.canonical")} />);
  const row = container.querySelector("[data-past-paper-id]") as HTMLElement;
  expect(row.textContent).toContain("Physics paper 2 (practice)");
  expect(row.textContent).toContain("Physics · 60 minutes · 3 questions · 3 parts checked · 1 part judged");
  expect(within(row).getAllByRole("button").map((b) => b.textContent)).toEqual(["Sit this paper", "Remove"]);
});
