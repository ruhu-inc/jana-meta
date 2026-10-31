// SPEC §20.9 `study-link-add.test.tsx` (W9): Add a YouTube video asks for the link, the transcript (with the
// three-step hint) and a title prefilled "YouTube video"; the refusals are said in the form's words (not a YouTube
// link, past two hours); a paste with no timestamps is saved as text and the form says so.
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { StudyLinkAdd } from "../src/learn/StudyLinkAdd.js";
import { LocaleProvider } from "../src/i18n.js";

afterEach(cleanup);
const URL_ = "https://www.youtube.com/watch?v=dQw4w9WgXcQ";

function show(onAdd: (url: string, transcript: string, title: string) => Promise<"timed" | "plain" | null>, error: string | null = null) {
  const view = render(<LocaleProvider locale="en"><StudyLinkAdd busy={false} error={error} onAdd={onAdd} /></LocaleProvider>);
  return { view, url: screen.getByLabelText("Link to the video"), transcript: screen.getByLabelText(/Its transcript/), title: screen.getByLabelText("Material title") as HTMLInputElement };
}

test("the form takes the link, the pasted transcript and a prefilled title, and adds the video", async () => {
  const onAdd = vi.fn(async () => "timed" as const);
  const { url, transcript, title } = show(onAdd);
  expect(title.value).toBe("YouTube video");
  expect(screen.getByText(/open the description, choose Show transcript, select all, copy/)).toBeTruthy();
  expect(screen.getByText(/Nothing is downloaded/)).toBeTruthy();
  expect(screen.getByRole("button", { name: "Add video" }).hasAttribute("disabled")).toBe(true);
  fireEvent.change(url, { target: { value: URL_ } });
  fireEvent.change(transcript, { target: { value: "0:00\nin this lecture\n0:04\nwe look at projectile motion" } });
  fireEvent.change(title, { target: { value: "Projectile motion" } });
  fireEvent.click(screen.getByRole("button", { name: "Add video" }));
  await waitFor(() => expect(onAdd).toHaveBeenCalledWith(URL_, "0:00\nin this lecture\n0:04\nwe look at projectile motion", "Projectile motion"));
  await waitFor(() => expect((screen.getByLabelText("Link to the video") as HTMLInputElement).value).toBe(""));
  expect(screen.queryByRole("status")).toBeNull();
});

test("a paste without timestamps is saved as text and the form says so", async () => {
  const { url, transcript } = show(vi.fn(async () => "plain" as const));
  fireEvent.change(url, { target: { value: URL_ } });
  fireEvent.change(transcript, { target: { value: "A lecture with no timestamps." } });
  fireEvent.click(screen.getByRole("button", { name: "Add video" }));
  await waitFor(() => expect(screen.getByRole("status").textContent).toContain("saved as text"));
});

test("the refusals are named: not a YouTube link, and a transcript past two hours", () => {
  show(vi.fn(async () => null), "unsupported_link");
  expect(screen.getByText(/That is not a YouTube link/)).toBeTruthy();
  cleanup();
  show(vi.fn(async () => null), "transcript_too_long");
  expect(screen.getByText(/runs past two hours/)).toBeTruthy();
  cleanup();
  show(vi.fn(async () => null), "source_too_large");
  expect(screen.queryByText(/YouTube link|two hours/)).toBeNull(); // another error is the workspace's to say
});
