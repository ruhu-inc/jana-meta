// An own-course learner's flashcards come back on Home when they are due.
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { LocaleProvider } from "../src/i18n.js";
import { DueToday, type DueSet } from "../src/home/DueToday.js";

afterEach(cleanup);
const show = (sets: DueSet[], hasCards = true, onReview = vi.fn()) => {
  render(<LocaleProvider locale="en"><DueToday sets={sets} hasCards={hasCards} onReview={onReview} /></LocaleProvider>);
  return onReview;
};

test("the sets most due come first and each opens its own deck", () => {
  const onReview = show([{ aid_id: "a", title: "Monopoly", due: 1 }, { aid_id: "b", title: "Lasso", due: 5 }]);
  const rows = screen.getAllByRole("listitem").map((row) => row.textContent);
  expect(rows[0]).toContain("Lasso: 5 cards due");
  expect(rows[1]).toContain("Monopoly: 1 card due");
  fireEvent.click(screen.getAllByRole("button", { name: "Review" })[0]!);
  expect(onReview).toHaveBeenCalledWith("b");
});

test("a private set never shows a title it does not have", () => {
  show([{ aid_id: "a", due: 2 }]);
  expect(screen.getByRole("listitem").textContent).toContain("Private material: 2 cards due");
});

test("at most three sets show, so Home stays quiet", () => {
  show([1, 2, 3, 4].map((n) => ({ aid_id: `a${n}`, title: `Set ${n}`, due: n })));
  expect(screen.getAllByRole("listitem")).toHaveLength(3);
});

test("nothing due shows nothing once the learner has cards, and a pointer before they do", () => {
  const { container } = render(<LocaleProvider locale="en"><DueToday sets={[]} hasCards onReview={vi.fn()} /></LocaleProvider>);
  expect(container.textContent).toBe("");
  cleanup();
  show([], false);
  expect(screen.getByText(/Make flashcards from a material/)).toBeTruthy();
});
