// SPEC §10.3: with no tutor to answer, the composer's place says why and offers what still works.
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { LocaleProvider } from "../src/i18n.js";
import { NoTutor } from "../src/composer/NoTutor.js";

afterEach(cleanup);

test.each([
  ["offline", /You're offline and there's no tutor model on this computer/],
  ["switched_off", /The online tutor is switched off and there's no tutor model on this computer/],
] as const)("%s: says so plainly, takes no question and offers practice and a mock exam", (reason, words) => {
  const onPractice = vi.fn(), onMock = vi.fn();
  render(<LocaleProvider locale="en"><NoTutor reason={reason} onPractice={onPractice} onMock={onMock} /></LocaleProvider>);
  const status = screen.getByRole("status");
  expect(status.textContent).toMatch(words);
  expect(status.textContent).toMatch(/Practice and mock exams from your installed packs still work\./);
  expect(status.textContent).not.toMatch(/please/i);
  expect(screen.queryByRole("textbox")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Go to practice" }));
  fireEvent.click(screen.getByRole("button", { name: "Sit a mock exam" }));
  expect(onPractice).toHaveBeenCalledOnce();
  expect(onMock).toHaveBeenCalledOnce();
});
