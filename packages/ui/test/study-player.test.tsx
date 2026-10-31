// SPEC §20.9 `study-player.test.tsx` (W9): a YouTube video has no player (JM-D42): the transcript pane shows its
// chapters and lines, each with Open at m:ss and Watch on YouTube, every one through the controller's moment opener
// (the app's external-link opener); Ask about this moment hands the moment to the app; a video file gets a <video>
// element where a recording has <audio>, with the filmstrip of frames read as text and the screened count.
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import type { StudyContracts as W } from "@jana/client-core";
import { StudyPlayer, framesOf } from "../src/learn/StudyPlayer.js";
import { LocaleProvider } from "../src/i18n.js";

afterEach(cleanup);
const sid = `src_${"0".repeat(26)}`, now = "2026-10-31T00:00:00Z";
const base = { source_id: sid, revision: 1, state: "ready", private: false, created_at: now, updated_at: now, readable_units: 2, unreadable_units: [], sha256: "0".repeat(64) } as const;
const link: W.Source = { ...base, kind: "video_link", title: "Projectile motion", link: { provider: "youtube", video_id: "dQw4w9WgXcQ", url: "https://www.youtube.com/watch?v=dQw4w9WgXcQ" }, transcript_kind: "timed", duration_ms: 275000,
  chapters: [{ start_ms: 0, end_ms: 230000, title: "Introduction" }, { start_ms: 230000, end_ms: 275000, title: "The range equation" }] };
const chunk = (i: number, start: number, end: number, text: string): W.Chunk => ({ chunk_id: `sck_${String(i).repeat(26)}`, source_id: sid, revision: 1, ordinal: i, locator: { kind: "time", start_ms: start, end_ms: end }, text, sha256: "0".repeat(64) });
const chunks = [
  chunk(0, 0, 230000, "[0:00] in this lecture we look at projectile motion\n[0:29] derive the range equation"),
  chunk(1, 230000, 275000, "[3:50] now let's derive how far the ball travels\n[4:12] substituting gives the range equation"),
];

function show(source: W.Source, extra: Partial<Parameters<typeof StudyPlayer>[0]> = {}) {
  const props = { onSeek: vi.fn(), onOpenMoment: vi.fn(), onAskMoment: vi.fn(), onCite: vi.fn(), onMakeChapters: vi.fn(), onMakeOutline: vi.fn(), loadMedia: vi.fn(async () => null), canMakeChapters: true, canOutline: true, busy: false, chapters: null, playhead: null, ...extra };
  render(<LocaleProvider locale="en"><StudyPlayer source={source} chunks={extra.chunks ?? chunks} {...props} /></LocaleProvider>);
  return props;
}

test("a YouTube video has no player: every line and chapter opens the moment through the opener", () => {
  const props = show(link);
  expect(screen.queryByLabelText("Video player")).toBeNull();
  expect(screen.queryByLabelText("Recording player")).toBeNull();
  expect(document.querySelector("video, audio, iframe")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Watch on YouTube" }));
  expect(props.onOpenMoment).toHaveBeenLastCalledWith(0);
  // Each transcript line carries its own moment, parsed from the chunk's [m:ss] prefixes.
  fireEvent.click(screen.getByRole("button", { name: "Open the video at 4:12 on YouTube" }));
  expect(props.onOpenMoment).toHaveBeenLastCalledWith(252000);
  fireEvent.click(screen.getByRole("button", { name: "Open the video at 0:29 on YouTube" }));
  expect(props.onOpenMoment).toHaveBeenLastCalledWith(29000);
  // The chapters by code, each with Open at.
  const chapters = within(screen.getByRole("region", { name: /Chapters/ }).parentElement as HTMLElement);
  fireEvent.click(chapters.getByRole("button", { name: "3:50 · The range equation" }));
  expect(props.onOpenMoment).toHaveBeenLastCalledWith(230000);
  // Ask about this moment hands the line's moment to the app; nothing is sent.
  fireEvent.click(screen.getByRole("button", { name: "Ask your tutor about the moment at 4:12" }));
  expect(props.onAskMoment).toHaveBeenLastCalledWith(252000);
  expect(props.onSeek).not.toHaveBeenCalled();
  // What this video teaches starts the outline job.
  fireEvent.click(screen.getByRole("button", { name: "What this video teaches" }));
  expect(props.onMakeOutline).toHaveBeenCalledTimes(1);
});

test("a chapters aid's summaries show over the code chapters, and a plain transcript shows no moments", () => {
  const aidChapters: W.Chapter[] = [{ start_ms: 0, end_ms: 275000, title: "All of it", summary: [{ text: "The lecture derives the range.", citations: [{ source_id: sid, revision: 1, chunk_id: chunks[1]!.chunk_id, start: 7, end: 19, quote: "substituting" }] }] }];
  show(link, { chapters: aidChapters });
  expect(screen.getByRole("button", { name: "0:00 · All of it" })).toBeTruthy();
  expect(screen.getByText("The lecture derives the range.")).toBeTruthy();
  expect(screen.queryByText(/The range equation/)).toBeNull();
});

test("a video file plays in a <video> element and shows the frames read as text, with the screened count", async () => {
  const file: W.Source = { ...base, kind: "video", title: "lecture.mp4", duration_ms: 95000, frames: 3, screened_frames: 1 };
  const frame: W.Chunk = { chunk_id: `sck_${"9".repeat(26)}`, source_id: sid, revision: 1, ordinal: 2, locator: { kind: "frame", at_ms: 40000, frame_id: `frm_${"A".repeat(26)}` }, text: "On screen at 0:40:\nR = u^2 sin 2theta / g", sha256: "0".repeat(64) };
  const fileChunks = [chunk(0, 0, 60000, "Today we derive the range equation."), chunk(1, 60000, 95000, "The range depends on the angle."), frame];
  expect(framesOf(fileChunks)).toEqual([{ frame_id: `frm_${"A".repeat(26)}`, at_ms: 40000, text: "R = u^2 sin 2theta / g" }]);
  const blob = new Blob(["x"], { type: "video/mp4" });
  const createObjectURL = vi.fn(() => "blob:video"), revokeObjectURL = vi.fn();
  Object.assign(URL, { createObjectURL, revokeObjectURL });
  const props = show(file, { chunks: fileChunks, loadMedia: vi.fn(async () => blob) });
  expect(screen.queryByRole("button", { name: "Watch on YouTube" })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Play video" }));
  await screen.findByLabelText("Video player");
  expect(document.querySelector("video")).toBeTruthy();
  expect(document.querySelector("audio")).toBeNull();
  const strip = screen.getByRole("region", { name: "On screen" });
  expect(within(strip).getByText("R = u^2 sin 2theta / g")).toBeTruthy();
  expect(within(strip).getByText(/Not read because someone was in the picture: 1/)).toBeTruthy();
  fireEvent.click(within(strip).getByRole("button", { name: /0:40 · on screen/ }));
  expect(props.onSeek).toHaveBeenLastCalledWith(40000);
  // A file's transcript lines seek the player rather than opening a browser.
  fireEvent.click(screen.getByRole("button", { name: /1:00\s*The range depends on the angle\./ }));
  expect(props.onSeek).toHaveBeenLastCalledWith(60000);
  expect(props.onOpenMoment).not.toHaveBeenCalled();
});

test("a recording keeps its audio player, its transcript and the chapters button", () => {
  const recording: W.Source = { ...base, kind: "recording", title: "lecture.wav", duration_ms: 120000 };
  show(recording, { chunks: [chunk(0, 0, 60000, "Enzymes are catalysts."), chunk(1, 60000, 120000, "Respiration releases energy.")] });
  expect(screen.getByRole("button", { name: "Play recording" })).toBeTruthy();
  expect(screen.getByRole("button", { name: "Make chapters" })).toBeTruthy();
  expect(screen.queryByRole("button", { name: /Open the video at/ })).toBeNull();
  expect(screen.getByRole("button", { name: /0:00\s*Enzymes are catalysts\./ })).toBeTruthy();
});
