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
