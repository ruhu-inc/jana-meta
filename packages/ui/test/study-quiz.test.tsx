// A Study quiz's keyboard: Enter in an answer checks that answer. Only Finish quiz submits the whole quiz.
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";
import type { StudyContracts as W } from "@jana/client-core";
import { StudyQuiz } from "../src/learn/StudyQuiz.js";
import { LocaleProvider } from "../src/i18n.js";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

const ITEM = (id: string) => ({ item_id: id, type: "short_answer", stem: { text: `Question ${id}` } }) as unknown as W.QuizItem;
const QUIZ = { quiz_id: "quz_1", status: "ready", items: [ITEM("a"), ITEM("b")], draft: null } as unknown as W.QuizView;

function show() {
  const onCheck = vi.fn(async (_id: string, _value: string) => true), onSubmit = vi.fn();
  render(<LocaleProvider locale="en"><StudyQuiz quiz={QUIZ} result={null} resultAnswers={{}} feedback={{}} busy={false} accessBlocked={false} stale={false}
    quizHelp={null} helpJob={undefined} helpPending={false} safeHelp={false} helpAids={[]} claim={() => null} jobs={() => null}
    onDraft={vi.fn()} onCheck={onCheck} onSubmit={onSubmit} onClearResult={vi.fn()} onHelp={vi.fn()} onFollowUp={vi.fn(async () => true)} /></LocaleProvider>);
  return { onCheck, onSubmit };
}

describe("StudyQuiz navigation", () => {
  const items = [ITEM("a"), ITEM("b"), ITEM("c")];
  const three = { ...QUIZ, items } as unknown as W.QuizView;
  const verdict = { verdict: "correct", marking: "judged" };

  function quiz(feedback: Record<string, unknown> = {}) {
    const onSubmit = vi.fn();
    render(<LocaleProvider locale="en"><StudyQuiz quiz={three} result={null} resultAnswers={{}} feedback={feedback as never} busy={false} accessBlocked={false} stale={false}
      quizHelp={null} helpJob={undefined} helpPending={false} safeHelp={false} helpAids={[]} claim={() => null} jobs={() => null}
      onDraft={vi.fn()} onCheck={vi.fn(async () => true)} onSubmit={onSubmit} onClearResult={vi.fn()} onHelp={vi.fn()} onFollowUp={vi.fn(async () => true)} /></LocaleProvider>);
    return { onSubmit };
  }

  // A browser submits the form when the button under the click has become a submit button by the time the click
  // finishes. Finish quiz must therefore be a new element, never Next question with its type changed.
  test("next_question_onto_the_last_question_does_not_become_finish_quiz", () => {
    const { onSubmit } = quiz();
    fireEvent.click(screen.getByRole("button", { name: "Next question" }));
    const next = screen.getByRole("button", { name: "Next question" });
    fireEvent.click(next);
    expect(screen.getByText("Question 3 of 3")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Finish quiz" })).not.toBe(next);
    expect(next.isConnected).toBe(false);
    expect(onSubmit).not.toHaveBeenCalled();
  });

  test("next_question_onto_a_checked_last_question_does_not_become_finish_quiz", async () => {
    const { onSubmit } = quiz({ a: verdict, b: verdict, c: verdict });
    for (const id of ["a", "b", "c"]) {
      fireEvent.change(screen.getByRole("textbox"), { target: { value: "answer" } });
      fireEvent.click(screen.getByRole("button", { name: "Check answer" }));
      await waitFor(() => expect(screen.queryByRole("button", { name: "Check answer" })).toBeNull());
      if (id !== "c") fireEvent.click(screen.getByRole("button", { name: "Next question" }));
    }
    fireEvent.click(screen.getByRole("button", { name: "Previous question" }));
    const next = await screen.findByRole("button", { name: "Next question" });
    fireEvent.click(next);
    expect(screen.getByRole("button", { name: "Finish quiz" })).not.toBe(next);
    expect(next.isConnected).toBe(false);
    expect(onSubmit).not.toHaveBeenCalled();
  });
});

describe("StudyQuiz verdicts", () => {
  const verdict = { item_id: "a", verdict: "correct", marking: "judged" };
  const saved = { ...QUIZ, draft: { answers: [{ item_id: "a", answer: "photosynthesis" }], position: 0 } } as unknown as W.QuizView;
  function mount(quiz: W.QuizView, checkedAnswers?: Record<string, string>) {
    return render(<LocaleProvider locale="en"><StudyQuiz quiz={quiz} result={null} resultAnswers={{}} feedback={{ a: verdict } as never} {...(checkedAnswers ? { checkedAnswers } : {})} busy={false} accessBlocked={false} stale={false}
      quizHelp={null} helpJob={undefined} helpPending={false} safeHelp={false} helpAids={[]} claim={() => null} jobs={() => null}
      onDraft={vi.fn()} onCheck={vi.fn(async () => true)} onSubmit={vi.fn()} onClearResult={vi.fn()} onHelp={vi.fn()} onFollowUp={vi.fn(async () => true)} /></LocaleProvider>);
  }

  test("a_checked_answer_keeps_its_verdict_when_the_quiz_comes_back", () => {
    mount(saved, { a: "photosynthesis" });
    expect(screen.getByRole("region", { name: "Answer feedback" })).toBeTruthy();
  });

  test("a_changed_answer_does_not_show_the_old_verdict", () => {
    mount(saved, { a: "something else" });
    expect(screen.queryByRole("region", { name: "Answer feedback" })).toBeNull();
  });

  test("an_empty_answer_after_a_retake_does_not_show_the_old_verdict", () => {
    mount(QUIZ);
    expect(screen.queryByRole("region", { name: "Answer feedback" })).toBeNull();
  });
});

describe("StudyQuiz keyboard", () => {
  test("enter_checks_the_answer_and_never_submits_the_quiz", async () => {
    const { onCheck, onSubmit } = show();
    const field = screen.getByRole("textbox");
    fireEvent.change(field, { target: { value: "photosynthesis" } });
    const notPrevented = fireEvent.keyDown(field, { key: "Enter" });
    expect(notPrevented).toBe(false); // the browser's implicit submission is stopped
    await waitFor(() => expect(onCheck).toHaveBeenCalledWith("a", "photosynthesis"));
    expect(onSubmit).not.toHaveBeenCalled();
  });

  test("enter_on_an_empty_answer_does_nothing", () => {
    const { onCheck, onSubmit } = show();
    fireEvent.keyDown(screen.getByRole("textbox"), { key: "Enter" });
    expect(onCheck).not.toHaveBeenCalled();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  test("enter_does_not_check_the_same_answer_twice", async () => {
    const { onCheck } = show();
    const field = screen.getByRole("textbox");
    fireEvent.change(field, { target: { value: "x" } });
    fireEvent.keyDown(field, { key: "Enter" });
    await waitFor(() => expect(onCheck).toHaveBeenCalledTimes(1));
    await new Promise((done) => setTimeout(done));
    fireEvent.keyDown(field, { key: "Enter" });
    expect(onCheck).toHaveBeenCalledTimes(1);
  });
});

describe("a finished quiz", () => {
  const FINISHED = { attempt_id: "att_1", results: [{ item_id: "a", verdict: "incorrect", label: "Judged, not checked", explanation: { text: "Because.", citations: [] } }, { item_id: "b", verdict: "correct", label: "Judged, not checked", explanation: { text: "Yes.", citations: [] } }] } as unknown as W.QuizResult;
  const results = (extra: Record<string, unknown> = {}) => {
    const onRetake = vi.fn();
    render(<LocaleProvider locale="en"><StudyQuiz quiz={QUIZ} result={FINISHED} resultAnswers={{ a: "x", b: "y" }} feedback={{}} busy={false} accessBlocked={false} stale={false}
      quizHelp={{}} helpJob={undefined} helpPending={false} safeHelp={false} helpAids={[]} claim={(c) => <p>{c.text}</p>} jobs={() => null} onDraft={vi.fn()} onCheck={vi.fn(async () => true)} onSubmit={vi.fn()} onClearResult={vi.fn()} onHelp={vi.fn()} onFollowUp={vi.fn(async () => true)} onRetake={onRetake} {...extra} /></LocaleProvider>);
    return onRetake;
  };
  test("can be retaken from the start", () => {
    const onRetake = results();
    fireEvent.click(screen.getByRole("button", { name: "Retake quiz" }));
    expect(onRetake).toHaveBeenCalledTimes(1);
  });
  test("says practice from one's own material stays with that material when there is no curriculum", () => {
    results({ ownCourse: true });
    expect(screen.getByText("Saved as practice with this material.")).toBeTruthy();
    expect(screen.queryByText(/Lessons or Practice/)).toBeNull();
  });
  test("says how practice reaches the map when there is a curriculum", () => {
    results();
    expect(screen.getByText(/shown on your map/)).toBeTruthy();
  });
});
