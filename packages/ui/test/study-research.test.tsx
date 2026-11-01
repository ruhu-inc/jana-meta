// SPEC §18: the research agent's study packs in Study. A short conversation with quick replies and "Skip", a plan the
// learner edits before anything is searched, then the pack's progress and "Open the pack". Every reply is synthetic.
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { StrictMode } from "react";
import { afterEach, describe, expect, test, vi } from "vitest";
import { CommandError, type ResearchContracts as R, type StudyWorkspaceController } from "@jana/client-core";
import { StudyResearch } from "../src/learn/StudyResearch.js";
import { LocaleProvider } from "../src/i18n.js";

afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.useRealTimers(); });

const BRIEF: R.Brief = { title: "How the heart pumps blood", subject: "biology", level: "o_level", purpose: "exam",
  known: "the four chambers", focus: "the valves",
  sub_questions: ["What do the heart valves do?", "How does the left ventricle pump blood?", "What is the cardiac cycle?", "Why is the left wall thicker?"],
  outputs: ["concept_map", "flashcards", "quiz"], length: "short" };
const QUESTION: R.ChatTurn = { kind: "question", question: "What is this pack for?", chips: ["An exam", "Curiosity"], asks: "purpose", brief: null };
const ID = `rsr_${"1".repeat(26)}`;

function record(status: R.Record["status"], extra: Partial<R.Record> = {}): R.Record {
  return { research_id: ID, status, brief: BRIEF, capture_id: null, pages: status === "ready" ? 3 : 0, failure: null,
    source_id: status === "ready" ? `src_${"2".repeat(26)}` : null, created_at: 1, updated_at: 2,
    sub_questions: BRIEF.sub_questions.map((text) => ({ text, state: status === "researching" ? "searching" : "done", sources: 2 })),
    parts: status === "ready" ? [{ kind: "concept_map", job_id: null, aid_id: null, state: "ready" }, { kind: "quiz", job_id: null, aid_id: null, state: "failed" }] : [],
    ...extra } as R.Record;
}

function controller(replies: R.ChatTurn[], reads: R.Record[] = []) {
  const fake = {
    researchChat: vi.fn(async (_body: R.ChatRequest) => replies.shift() as R.ChatTurn),
    startResearch: vi.fn(async (_brief: R.Brief, _capture: string | null) => record("researching")),
    researchPacks: vi.fn(async () => [] as R.Record[]),
    researchPack: vi.fn(async (_id: string) => reads.shift() ?? record("ready")),
    cancelResearch: vi.fn(async (_id: string) => record("cancelled")),
  };
  return { fake, as: fake as unknown as StudyWorkspaceController };
}

function show(c: StudyWorkspaceController, opened = vi.fn()) {
  return render(<LocaleProvider locale="en"><StudyResearch controller={c} onOpenSource={opened} /></LocaleProvider>);
}

describe("SPEC §18 research agent", () => {
  test("research_talk_then_plan_then_pack", async () => {
    const { fake, as } = controller([QUESTION, { kind: "brief", question: null, chips: [], asks: null, brief: BRIEF }], [record("researching"), record("ready")]);
    const opened = vi.fn();
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const view = show(as, opened);
    fireEvent.change(screen.getByLabelText("What do you want to learn about?"), { target: { value: "how the heart pumps blood" } });
    fireEvent.click(screen.getByRole("button", { name: "Research it" }));
    await screen.findByText("What is this pack for?");
    expect(fake.researchChat.mock.calls[0]?.[0]).toEqual({ start: { topic: "how the heart pumps blood" }, history: [], answer: null, skip: false });
    fireEvent.click(screen.getByRole("button", { name: "An exam" }));
    await screen.findByText("Here's the plan");
    expect(fake.researchChat.mock.calls[1]?.[0].history).toEqual([{ role: "jana", text: "What is this pack for?", asks: "purpose" }]);
    expect(fake.researchChat.mock.calls[1]?.[0].answer).toBe("An exam");
    // Four questions is the least: none can be removed until one is added.
    expect(screen.getByRole("button", { name: "Remove: What do the heart valves do?" })).toHaveProperty("disabled", true);
    fireEvent.change(screen.getByLabelText("Add a question in your own words"), { target: { value: "How do valves fail?" } });
    fireEvent.click(screen.getByRole("button", { name: "Add" }));
    fireEvent.click(screen.getByRole("button", { name: "Remove: What do the heart valves do?" }));
    expect(screen.queryByLabelText("Diagram practice on your photo")).toBeNull(); // no photo, no diagram practice
    fireEvent.click(screen.getByLabelText("Quiz"));
    expect(fake.startResearch).not.toHaveBeenCalled(); // nothing is searched before Start research
    fireEvent.click(screen.getByRole("button", { name: "Start research" }));
    await waitFor(() => expect(fake.startResearch).toHaveBeenCalledTimes(1));
    const [brief, capture] = fake.startResearch.mock.calls[0]!;
    expect(capture).toBeNull();
    expect(brief.sub_questions).toEqual([...BRIEF.sub_questions.slice(1), "How do valves fail?"]);
    expect(brief.outputs).toEqual(["concept_map", "flashcards"]);
    await screen.findByText(/Researching/);
    await vi.advanceTimersByTimeAsync(3100);
    await screen.findByText("Your pack is ready, made from 3 pages.");
    expect(view.container.querySelector('[data-part="quiz"]')?.getAttribute("data-state")).toBe("failed");
    fireEvent.click(screen.getByRole("button", { name: "Open the pack" }));
    expect(opened).toHaveBeenCalledWith(`src_${"2".repeat(26)}`);
  });

  test("research_asks_the_online_tutor_notice_then_sends_the_same_turn_with_the_answer", async () => {
    // A profile that starts in Study has never answered the online tutor's first-use notice (ARC-10): the core says so
    // and the conversation asks it, then sends the same turn with the answer (§19 fix, 2026-10-29).
    const { fake, as } = controller([QUESTION]);
    fake.researchChat.mockImplementationOnce(async () => {
      throw new CommandError(403, "feature_disabled", false, { reason: "notice_required", feature: "cloud_tier" });
    });
    show(as);
    fireEvent.change(screen.getByLabelText("What do you want to learn about?"), { target: { value: "electrolysis of brine" } });
    fireEvent.click(screen.getByRole("button", { name: "Research it" }));
    await screen.findByText("Plan this with the online tutor?");
    expect(screen.queryByText(/isn't available/)).toBeNull(); // not the planner failure
    fireEvent.click(screen.getByRole("button", { name: "OK" }));
    await screen.findByText("What is this pack for?");
    expect(fake.researchChat.mock.calls[1]?.[0]).toEqual({ start: { topic: "electrolysis of brine" }, history: [], answer: null,
      skip: false, cloud_notice: "accepted" });
    expect(screen.queryByText("Plan this with the online tutor?")).toBeNull();
  });

  test("research_skip_goes_straight_to_the_plan", async () => {
    const { fake, as } = controller([QUESTION, { kind: "brief", question: null, chips: [], asks: null, brief: BRIEF }]);
    show(as);
    fireEvent.change(screen.getByLabelText("What do you want to learn about?"), { target: { value: "the heart" } });
    fireEvent.click(screen.getByRole("button", { name: "Research it" }));
    fireEvent.click(await screen.findByRole("button", { name: "Skip, just research it" }));
    await screen.findByText("Here's the plan");
    expect(fake.researchChat.mock.calls[1]?.[0].skip).toBe(true);
  });

  test("research_out_of_scope_says_so_in_janas_words", async () => {
    const { as } = controller([{ kind: "out_of_scope", question: "That isn't something I research yet.", chips: [], asks: null, brief: null }]);
    show(as);
    fireEvent.change(screen.getByLabelText("What do you want to learn about?"), { target: { value: "jazz history" } });
    fireEvent.click(screen.getByRole("button", { name: "Research it" }));
    await screen.findByText("That isn't something I research yet.");
    fireEvent.click(screen.getByRole("button", { name: "Try another topic" }));
    await screen.findByLabelText("What do you want to learn about?");
  });
  test("research_a_handed_over_photo_starts_its_conversation_once", async () => {
    const { fake, as } = controller([QUESTION, QUESTION]);
    const used = vi.fn();
    const cap = `cap_${"3".repeat(26)}`;
    // StrictMode runs effects twice, as the development build that showed the double turn did.
    const view = render(<StrictMode><LocaleProvider locale="en"><StudyResearch controller={as} initialCapture={cap} onCaptureUsed={used} onOpenSource={vi.fn()} /></LocaleProvider></StrictMode>);
    await screen.findByText("What is this pack for?");
    view.rerender(<StrictMode><LocaleProvider locale="en"><StudyResearch controller={as} initialCapture={cap} onCaptureUsed={used} onOpenSource={vi.fn()} /></LocaleProvider></StrictMode>);
    expect(fake.researchChat).toHaveBeenCalledTimes(1);
    expect(fake.researchChat.mock.calls[0]?.[0].start).toEqual({ capture_id: cap });
    expect(screen.getByRole("heading", { name: "Make a study pack" })).toBeTruthy();
  });
});

test("one failed poll is retried, and a pack that reads again clears the error it showed", async () => {
  const { fake, as } = controller([], [record("ready")]);
  fake.researchPacks.mockResolvedValueOnce([record("researching")]);
  fake.researchPack.mockRejectedValueOnce(Object.assign(new Error("down"), { code: "model_unavailable" }));
  vi.useFakeTimers({ shouldAdvanceTime: true });
  const view = show(as);
  fireEvent.click(await screen.findByRole("button", { name: /Researching/ }));
  await screen.findByText("The research planner isn't available right now. Check you're online and try again.");
  await vi.advanceTimersByTimeAsync(3100);
  await screen.findByText("Your pack is ready, made from 3 pages.");
  expect(screen.queryByText("The research planner isn't available right now. Check you're online and try again.")).toBeNull();
  expect(fake.researchPack).toHaveBeenCalledTimes(2);
  view.unmount();
  vi.useRealTimers();
});
