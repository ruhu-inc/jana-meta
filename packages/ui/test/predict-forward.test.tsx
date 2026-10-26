// Predict before you see in a session (VSL-47): the viewer sends the learner's locked-in prediction and their
// explanation of the result to the session, which answers with a tutor turn pointing at the result. Other simulation
// events stay in the client, a read-only history replay sends nothing, and a simulation shown outside a session sends
// nothing. The renderer is a stub that raises the events a predict-first simulation raises.
import { readFileSync } from "node:fs";
import path from "node:path";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";
import type { SessionController } from "@jana/client-core";
import { LocaleProvider } from "../src/i18n.js";
import { RegistryProvider } from "../src/registry/registry.js";
import { StoreProvider } from "../src/store.js";
import { defaultRegistry } from "../src/transcript/parts.js";
import { VisualViewer, type VisualHooks, type VisualSpec } from "../src/visuals/VisualViewer.js";
import { Fixture } from "./harness.js";

const SCENARIO = "poe.phy.projectile_angle_30_60.v1";
// The renderer package's projectile fixture, a valid resolved spec, as a predict-first simulation.
const FIXTURE = JSON.parse(readFileSync(path.join(import.meta.dirname, "../../renderers/fixtures/visuals/projectile-sim.json"), "utf8")) as { spec: VisualSpec };
const SPEC: VisualSpec = { ...FIXTURE.spec, params: { ...(FIXTURE.spec.params as object), predict: SCENARIO } };
const VISUAL = SPEC.visual_id;
const HOOKS: VisualHooks = {
  check: () => [], labelModes: ["shown"], Fallback: () => <p>fallback</p>,
  View: ({ onSimEvent }) => (
    <div>
      <button onClick={() => onSimEvent({ type: "sim.param_changed", visual_id: VISUAL, param: "angle", value: 40 })}>move</button>
      <button onClick={() => onSimEvent({ type: "sim.prediction_committed", visual_id: VISUAL, scenario_id: SCENARIO, misconception_id: "mc.phy.o.steeper_launch_goes_further",
        prediction: "The 60 degree ball, it goes higher.", choice: "further", correct: false, common_guess: true })}>lock</button>
      <button onClick={() => onSimEvent({ type: "sim.explained", visual_id: VISUAL, scenario_id: SCENARIO, misconception_id: "mc.phy.o.steeper_launch_goes_further", explanation: "It is slower going forward." })}>explain</button>
    </div>
  ),
};

afterEach(() => cleanup());

function show(session: SessionController | null, readOnly = false) {
  const f = new Fixture();
  render(<LocaleProvider locale="en"><RegistryProvider registry={defaultRegistry()}>
    <StoreProvider holder={f.holder} session={session} readOnly={readOnly}><VisualViewer spec={SPEC} hooks={HOOKS} /></StoreProvider>
  </RegistryProvider></LocaleProvider>);
}

describe("VSL-47 in a session", () => {
  test("the prediction and its explanation go to the session; the client never says whether it matched", () => {
    const simPrediction = vi.fn(() => Promise.resolve());
    show({ simPrediction } as unknown as SessionController);
    fireEvent.click(screen.getByText("move"));
    expect(simPrediction).not.toHaveBeenCalled();
    fireEvent.click(screen.getByText("lock"));
    expect(simPrediction).toHaveBeenLastCalledWith(VISUAL, "committed", SCENARIO, "further", "The 60 degree ball, it goes higher.");
    fireEvent.click(screen.getByText("explain"));
    expect(simPrediction).toHaveBeenLastCalledWith(VISUAL, "explained", SCENARIO, null, "It is slower going forward.");
    expect(simPrediction).toHaveBeenCalledTimes(2);
  });

  test("a replayed history and a simulation outside a session send nothing", () => {
    const simPrediction = vi.fn(() => Promise.resolve());
    show({ simPrediction } as unknown as SessionController, true);
    fireEvent.click(screen.getByText("lock"));
    expect(simPrediction).not.toHaveBeenCalled();
    cleanup();
    show(null);
    fireEvent.click(screen.getByText("lock")); // no session: nothing to send, and nothing throws
  });
});
