// My map on Progress (SPEC §21.1, §21.8, §22.1, JM-D35, TABLE UXS-22a; W10, W11): "Show my map" opens every installed
// subject as topic tiles, the overview the core serves (test_w10_overview.py writes it); each tile is drawn in its
// rule's look with the rule's word, its secure count and its freshness in words (never colour alone); the tiles open on
// Mastery and "Layers" reveals the switch, whose Freshness layer redraws them; a tap opens the subject's map; "What
// moved today" leads the page and, while the map is open, the tiles holding the ideas that moved are outlined. Through
// the real controllers against the fake core; synthetic data.
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

async function shown({ layer = "mastery" as MapLayer, onLayer = vi.fn(), onOpen = vi.fn(), open = true } = {}) {
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
  await waitFor(() => expect(document.querySelector("[data-progress-moved]")).not.toBeNull());
  if (open) {
    fireEvent.click(screen.getByRole("button", { name: "Show my map" }));
    await waitFor(() => expect(document.querySelector("[data-map-overview]")!.getAttribute("data-map-overview")).toBe("ready"));
  }
  return { onLayer, onOpen, core };
}

const tile = (topic: string) => document.querySelector<HTMLButtonElement>(`[data-overview-topic="${topic}"]`)!;

describe("my map", () => {
  test("every installed subject shows as tiles with the rule, the bands and the freshness in words", async () => {
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

  test("what moved today leads, and the map opens from Show my map with the moved tiles outlined", async () => {
    await shown({ open: false });
    // The map is not on the first screen: nothing is read until the learner asks for it.
    expect(document.querySelector("[data-map-overview]")).toBeNull();
    expect(screen.queryByText("Outlined on the map: the ideas that moved today")).toBeNull();
    const button = screen.getByRole("button", { name: "Show my map" });
    expect(button.getAttribute("aria-expanded")).toBe("false");
    fireEvent.click(button);
    await waitFor(() => expect(document.querySelector("[data-map-overview]")!.getAttribute("data-map-overview")).toBe("ready"));
    expect(screen.getByRole("button", { name: "Hide my map" }).getAttribute("aria-expanded")).toBe("true");
    const map = document.querySelector("[data-map-overview]")!;
    const moved = document.querySelector("[data-progress-moved]")!;
    // What moved today comes first; the map sits under the controls row and before the subject card.
    expect(moved.compareDocumentPosition(map) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(map.compareDocumentPosition(document.querySelector("[data-progress-subject]")!) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(tile(MOTION).getAttribute("data-moved")).toBe("");
    expect(tile(MOTION).getAttribute("aria-label")).toContain("Outlined on the map: the ideas that moved today");
    expect(screen.getByText("Outlined on the map: the ideas that moved today")).toBeTruthy();
    // Hiding it takes the outline note away with it.
    fireEvent.click(screen.getByRole("button", { name: "Hide my map" }));
    expect(document.querySelector("[data-map-overview]")).toBeNull();
    expect(screen.queryByText("Outlined on the map: the ideas that moved today")).toBeNull();
  });

  test("the overview opens on Mastery and Layers reveals the switch", async () => {
    const { onLayer } = await shown();
    expect(screen.queryByRole("radiogroup", { name: "Show on the map" })).toBeNull();
    expect(within(tile(MOTION)).getByText("Learning")).toBeTruthy();
    const layers = screen.getByRole("button", { name: "Layers" });
    expect(layers.getAttribute("aria-expanded")).toBe("false");
    fireEvent.click(layers);
    expect(layers.getAttribute("aria-expanded")).toBe("true");
    const group = screen.getByRole("radiogroup", { name: "Show on the map" });
    expect(within(group).getAllByRole("radio").map((r) => r.textContent)).toEqual(["Mastery", "Freshness", "Mistakes"]);
    expect(within(group).getByRole("radio", { name: "Mastery" }).getAttribute("aria-checked")).toBe("true");
    fireEvent.click(within(group).getByRole("radio", { name: "Freshness" }));
    expect(onLayer).toHaveBeenCalledWith("freshness");
  });

  test("a layer chosen elsewhere arrives with the switch already shown, redraws the tiles, and a tap opens the subject map", async () => {
    const { onLayer, onOpen } = await shown({ layer: "freshness" });
    expect(within(tile(MOTION)).getByText("Practised today")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Layers" }).getAttribute("aria-expanded")).toBe("true");
    fireEvent.click(screen.getByRole("radio", { name: "Mistakes" }));
    expect(onLayer).toHaveBeenCalledWith("mistakes");
    fireEvent.click(tile(MOTION));
    expect(onOpen).toHaveBeenCalledWith("cur.phy.o", MOTION);
    fireEvent.click(screen.getByRole("button", { name: "Open the Physics map" }));
    expect(onOpen).toHaveBeenLastCalledWith("cur.phy.o");
  });

  test("no probability and no blame on the map", async () => {
    await shown();
    const text = document.querySelector("[data-map-overview]")!.textContent ?? "";
    // Counts and words only (a topic may be called "Probability of one event": that is the syllabus, not the learner).
    expect(text).not.toMatch(/\d\.\d|%/);
    expect(text).not.toMatch(/behind|failing|weak/i);
  });
});
