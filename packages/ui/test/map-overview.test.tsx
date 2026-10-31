// My map, Progress's hero (SPEC §21.1, §21.8, JM-D35, TABLE UXS-22a; W10): Progress opens on every installed subject
// as topic tiles, the overview the core serves (test_w10_overview.py writes it); each tile is drawn in its rule's look
// with the rule's word, its secure count and its freshness in words (never colour alone); the Freshness layer redraws
// the tiles; a tap opens the subject's map; "What moved today" is the first thing under the hero and the tiles holding
// the ideas that moved are outlined. Through the real controllers against the fake core; synthetic data.
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import fs from "node:fs";
import path from "node:path";
import { afterEach, describe, expect, test, vi } from "vitest";
import { MapOverviewController, ProfileController, ProgressController, StoreHolder, readOverview, type MapLayer, type ProgressView } from "@jana/client-core";
import { FakeProfileCore, PROFILES } from "../../client-core/test/profilecore.js";
import { STATES } from "../gallery/index.js";
import { LocaleProvider } from "../src/i18n.js";
import { Progress } from "../src/progress/Progress.js";

const OVERVIEW = readOverview(JSON.parse(fs.readFileSync(path.join(import.meta.dirname, "fixtures", "curriculum-overview.json"), "utf8")));
const MOTION = "cur.phy.o.motion_forces_and_energy.motion";
const PROGRESS = STATES.find((s) => s.id === "progress.canonical")!.payload.progress as ProgressView;

afterEach(() => cleanup());

async function shown({ layer = "mastery" as MapLayer, onLayer = vi.fn(), onOpen = vi.fn() } = {}) {
  const core = new FakeProfileCore();
  const profiles = new ProfileController(core.launch, new StoreHolder(), { fetch: core.fetch });
  await profiles.load();
  expect(await profiles.unlock(PROFILES[1]!.profile_id)).toBe(true);
  core.overview = OVERVIEW;
  core.progress = PROGRESS;
  const overview = new MapOverviewController(profiles);
  const moved = new Set(PROGRESS.moved_today);
  render(
    <LocaleProvider locale="en">
      <Progress controller={new ProgressController(profiles)} names={{ subject: (s) => s[0]!.toUpperCase() + s.slice(1), kc: () => null }} actions={{}}
        map={{ controller: overview, layer, onLayer, onOpen, tileOf: (kc) => (moved.has(kc) ? MOTION : null) }} />
    </LocaleProvider>,
  );
  await waitFor(() => expect(document.querySelector("[data-map-overview]")!.getAttribute("data-map-overview")).toBe("ready"));
  return { onLayer, onOpen, core };
}

const tile = (topic: string) => document.querySelector<HTMLButtonElement>(`[data-overview-topic="${topic}"]`)!;

describe("my map", () => {
  test("every_installed_subject_as_tiles_with_the_rule_bands_and_freshness_in_words", async () => {
    await shown();
    const subjects = [...document.querySelectorAll("[data-overview-subject]")].map((s) => s.getAttribute("data-overview-subject"));
    expect(subjects.sort()).toEqual(OVERVIEW.subjects.map((s) => s.subject_id).sort());
    for (const subject of OVERVIEW.subjects) {
      for (const topic of subject.topics) {
        const button = tile(topic.topic_id);
        expect(button.dataset.rule).toBe(topic.rule);
        expect(button.dataset.freshness).toBe(topic.freshness);
      }
    }
    const motion = OVERVIEW.subjects.flatMap((s) => s.topics).find((t) => t.topic_id === MOTION)!;
    expect(tile(MOTION).getAttribute("aria-label")).toContain(
      `Motion in a straight line: Learning, ${motion.bands.secure} of ${motion.kcs} secure, Practised today, 1 mistake being watched`);
    expect(within(tile(MOTION)).getByText("Learning")).toBeTruthy();
  });

  test("the_hero_leads_and_what_moved_today_is_first_under_it_with_its_tiles_outlined", async () => {
    await shown();
    await waitFor(() => expect(document.querySelector("[data-progress-moved]")).not.toBeNull());
    const hero = document.querySelector("[data-map-overview]")!;
    const moved = document.querySelector("[data-progress-moved]")!;
    expect(hero.compareDocumentPosition(moved) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    // Nothing else sits between the hero and what moved today.
    expect(hero.nextElementSibling?.contains(moved)).toBe(true);
    expect(tile(MOTION).getAttribute("data-moved")).toBe("");
    expect(tile(MOTION).getAttribute("aria-label")).toContain("Outlined on the map: the ideas that moved today");
    expect(screen.getByText("Outlined on the map: the ideas that moved today")).toBeTruthy();
  });

  test("a_layer_redraws_the_tiles_and_a_tap_opens_the_subject_map", async () => {
    const { onLayer, onOpen } = await shown({ layer: "freshness" });
    expect(within(tile(MOTION)).getByText("Practised today")).toBeTruthy();
    fireEvent.click(screen.getByRole("radio", { name: "Mistakes" }));
    expect(onLayer).toHaveBeenCalledWith("mistakes");
    fireEvent.click(tile(MOTION));
    expect(onOpen).toHaveBeenCalledWith("cur.phy.o", MOTION);
    fireEvent.click(screen.getByRole("button", { name: "Open the Physics map" }));
    expect(onOpen).toHaveBeenLastCalledWith("cur.phy.o");
  });

  test("no_probability_and_no_blame_in_the_hero", async () => {
    await shown();
    const text = document.querySelector("[data-map-overview]")!.textContent ?? "";
    // Counts and words only (a topic may be called "Probability of one event": that is the syllabus, not the learner).
    expect(text).not.toMatch(/\d\.\d|%/);
    expect(text).not.toMatch(/behind|failing|weak/i);
  });
});
