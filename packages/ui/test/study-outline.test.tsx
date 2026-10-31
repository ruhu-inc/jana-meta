// SPEC §20.9 `study-outline.test.tsx` (W9): the outline shows objectives with their moments, worked examples,
// concepts with skill chips (a tap opens the learner's map) or "outside the packs", what the video assumes, "Not
// covered here" worded without blame, and "For you" as band words; every moment opens through the moment opener.
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import type { StudyContracts as W } from "@jana/client-core";
import { StudyOutline } from "../src/learn/StudyOutline.js";
import { LocaleProvider } from "../src/i18n.js";

afterEach(cleanup);
const sid = `src_${"0".repeat(26)}`, cid = `sck_${"0".repeat(26)}`;
const RANGE = "kc.phy.o.projectiles.range", FLIGHT = "kc.phy.o.projectiles.time_of_flight", DRAG = "kc.phy.o.projectiles.drag";
const cite = (quote: string): W.Citation[] => [{ source_id: sid, revision: 1, chunk_id: cid, start: 0, end: quote.length, quote }];
const chunk: W.Chunk = { chunk_id: cid, source_id: sid, revision: 1, ordinal: 0, locator: { kind: "time", start_ms: 0, end_ms: 600000 }, text: "[0:29] derive the range equation", sha256: "0".repeat(64) };
const outline: NonNullable<W.Aid["outline"]> = {
  objectives: [{ text: "Derive the range equation", at_ms: 29000, citations: cite("derive") }, { text: "Find the time of flight", at_ms: 35000, citations: cite("derive") }],
  examples: [{ text: "A ball kicked at thirty degrees", at_ms: 580000, citations: cite("derive") }],
  concepts: [
    { name: "Range", at_ms: 252000, citations: cite("derive"), kc_ids: [RANGE], outside_packs: false },
    { name: "Time of flight", at_ms: 400000, citations: cite("derive"), kc_ids: [FLIGHT], outside_packs: false },
    { name: "Air resistance", at_ms: 11000, citations: cite("derive"), kc_ids: [], outside_packs: true },
  ],
  assumes: [{ text: "Resolving a vector into components", citations: cite("derive") }],
  skips: [{ kc_id: DRAG, statement: "Describe the effect of drag on a projectile's path" }],
  for_you: [{ kc_id: RANGE, band: "secure" }, { kc_id: FLIGHT, band: "not_started" }],
};

test("the outline shows what the video teaches, mapped to skills, skips and the learner's bands", () => {
  const onOpenMoment = vi.fn(), onSkill = vi.fn(), onCite = vi.fn();
  const names: Record<string, string> = { [RANGE]: "Derive and use the range equation", [FLIGHT]: "Find the time of flight of a projectile" };
  render(<LocaleProvider locale="en"><StudyOutline outline={outline} sourceTitle="Projectile motion" chunks={[chunk]} busy={false} onOpenMoment={onOpenMoment} onCite={onCite} onSkill={onSkill} skillName={(kc) => names[kc] ?? null} /></LocaleProvider>);
  const objectives = within(screen.getByRole("region", { name: "Objectives" }));
  expect(objectives.getAllByRole("listitem").map((li) => li.textContent)).toEqual(expect.arrayContaining([expect.stringContaining("Derive the range equation")]));
  fireEvent.click(objectives.getByRole("button", { name: "Open the video at 0:29 on YouTube" }));
  expect(onOpenMoment).toHaveBeenLastCalledWith(29000);
  expect(within(screen.getByRole("region", { name: "Worked examples" })).getByText("A ball kicked at thirty degrees")).toBeTruthy();
  const concepts = within(screen.getByRole("region", { name: "Concepts" }));
  fireEvent.click(concepts.getByRole("button", { name: "Derive and use the range equation: secure" }));
  expect(onSkill).toHaveBeenLastCalledWith(RANGE);
  expect(concepts.getByRole("button", { name: "Find the time of flight of a projectile: not started" })).toBeTruthy();
  expect(concepts.getByText("outside the packs")).toBeTruthy();
  fireEvent.click(concepts.getByRole("button", { name: "Open the video at 4:12 on YouTube" }));
  expect(onOpenMoment).toHaveBeenLastCalledWith(252000);
  expect(within(screen.getByRole("region", { name: "Assumes you know" })).getByText("Resolving a vector into components")).toBeTruthy();
  const skips = within(screen.getByRole("region", { name: "Not covered here" }));
  expect(skips.getByText("Describe the effect of drag on a projectile's path")).toBeTruthy();
  expect(skips.getByText(/Nothing to fix/)).toBeTruthy();
  const forYou = screen.getByRole("region", { name: "For you" });
  expect(forYou.textContent).toContain("Derive and use the range equation· secure");
  expect(forYou.textContent).toContain("Find the time of flight of a projectile· not started");
  expect(screen.queryByText(/%|0\.\d/)).toBeNull(); // bands as words, never a probability
  // A citation badge opens the cited passage.
  fireEvent.click(screen.getAllByRole("button", { name: "Projectile motion · At 00:00" })[0]!);
  expect(onCite).toHaveBeenCalled();
});

test("without a map or skill names the chips still name the skill and cannot be pressed", () => {
  render(<LocaleProvider locale="en"><StudyOutline outline={outline} sourceTitle="Projectile motion" chunks={[chunk]} busy={false} onOpenMoment={vi.fn()} onCite={vi.fn()} /></LocaleProvider>);
  const chip = screen.getByRole("button", { name: "range: secure" });
  expect(chip.hasAttribute("disabled")).toBe(true);
  expect(screen.queryByRole("button", { name: "On the map" })).toBeNull();
});
