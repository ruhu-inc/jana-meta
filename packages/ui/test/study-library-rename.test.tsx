// A material can be renamed, so two rows called "YouTube video" can be told apart.
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import type { StudyContracts as W } from "@jana/client-core";
import { LocaleProvider } from "../src/i18n.js";
import { StudyLibrary } from "../src/learn/StudyLibrary.js";

afterEach(cleanup);
const NOW = "2026-11-02T00:00:00Z";
const source = { source_id: "src_1", revision: 1, kind: "video_link", title: "YouTube video", state: "ready", private: false, created_at: NOW, updated_at: NOW, readable_units: 1, unreadable_units: [], sha256: "a".repeat(64) } as unknown as W.SourceList["items"][number];

test("renaming asks for the new name and hands it over", () => {
  const onRename = vi.fn();
  render(<LocaleProvider locale="en"><StudyLibrary sources={[source]} sets={[]} archivedIds={[]} busy={false} onOpen={vi.fn()} onArchive={vi.fn()} onRename={onRename} /></LocaleProvider>);
  fireEvent.click(screen.getByRole("button", { name: /Actions for YouTube video/ }));
  fireEvent.click(screen.getByRole("menuitem", { name: "Rename" }));
  const dialog = screen.getByRole("dialog");
  fireEvent.change(within(dialog).getByRole("textbox"), { target: { value: "Projectile lecture" } });
  fireEvent.click(within(dialog).getByRole("button", { name: "Save name" }));
  expect(onRename).toHaveBeenCalledWith(["src_1"], "Projectile lecture");
});
