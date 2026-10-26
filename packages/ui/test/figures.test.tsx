// Checked figures (VSL-12, VSL-13): a worked example draws the figure the pack build resolved and checked, and a lesson
// visual draws its resolved spec, not the raw params a renderer cannot validate. The renderer is a stub registered for
// the kind; the spec is the renderer package's own motion-graph fixture.
import { cleanup, render, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, test } from "vitest";
import { LessonController, ProfileController, StoreHolder, type WorkedExampleView } from "@jana/client-core";
import { FakeProfileCore, PROFILES } from "../../client-core/test/profilecore.js";
import { STATES } from "../gallery/index.js";
import fixture from "../../renderers/fixtures/visuals/motion-graph.json" with { type: "json" };
import { LocaleProvider } from "../src/i18n.js";
import { ExampleBoard, LessonPlayer } from "../src/learn/LessonPlayer.js";
import { RegistryProvider } from "../src/registry/registry.js";
import { defaultRegistry } from "../src/transcript/parts.js";

const SPEC = fixture.spec as unknown as NonNullable<WorkedExampleView["visual"]>;
const LESSON = STATES.find((s) => s.id === "lesson-player.canonical")!.payload as { lesson: { lesson_id: string; blocks: unknown[] } };

afterEach(() => cleanup());

function show(node: ReactNode) {
  const registry = defaultRegistry();
  registry.register("visual:motion_graph", { schema: "visuals/visual-spec#/$defs/resolved", renderClass: "card",
    Component: ({ data }) => <svg data-drawn={(data as { visual_id: string }).visual_id} />, Fallback: () => <p data-words />,
  });
  return render(<LocaleProvider locale="en"><RegistryProvider registry={registry}>{node}</RegistryProvider></LocaleProvider>);
}

const EXAMPLE: WorkedExampleView = {
  worked_example_id: "wex.phy.o.motion.0002", problem: "A car speeds up steadily from 10 m/s to 25 m/s in 5.0 s. Find its acceleration.",
  steps: [{ n: 1, latex: "a = \\frac{v - u}{t}", reason: "Acceleration is change in velocity over time", check_id: null }],
  final_answer: { latex: "3.0\\ \\text{m/s}^2", check_id: "chk_build_phy_w_0002" }, faded_steps: [], visual: SPEC,
};

describe("checked figures", () => {
  test("a worked example draws its build-checked figure", () => {
    show(<ExampleBoard example={EXAMPLE} />);
    expect(document.querySelector(`[data-drawn="${SPEC.visual_id}"]`)).not.toBeNull();
  });

  test("a worked example with no figure draws none", () => {
    show(<ExampleBoard example={{ ...EXAMPLE, visual: null }} />);
    expect(document.querySelector("[data-drawn]")).toBeNull();
  });

  test("a lesson visual draws its resolved spec, not its raw params", async () => {
    const core = new FakeProfileCore();
    const profiles = new ProfileController(core.launch, new StoreHolder(), { fetch: core.fetch });
    await profiles.load();
    expect(await profiles.unlock(PROFILES[1]!.profile_id)).toBe(true);
    const visual = { type: "visual", visual: { visual_type: "motion_graph", params: { graph: "velocity_time" }, resolved: SPEC }, caption: null };
    core.lessons.set(LESSON.lesson.lesson_id, { ...LESSON.lesson, blocks: [visual, ...LESSON.lesson.blocks] });
    show(<LessonPlayer controller={new LessonController(profiles)} lessonId={LESSON.lesson.lesson_id} />);
    await waitFor(() => expect(document.querySelector(`[data-drawn="${SPEC.visual_id}"]`)).not.toBeNull());
    expect(document.querySelector("[data-words]")).toBeNull();
  });
});
