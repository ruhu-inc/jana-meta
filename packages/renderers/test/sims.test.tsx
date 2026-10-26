// @vitest-environment happy-dom
// The S2 simulations (VSL-30, VSL-31, VSL-32): deterministic step functions, readouts that match the verification
// tools at the declared sample points, and controls a keyboard and a screen reader can use.
import fs from "node:fs";
import path from "node:path";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { describe, expect, test } from "vitest";
import { CLIENT_KEYS } from "../src/generated/keys.js";
import { SIM_SETUPS, circuitModel, projectileModel, runToEnd, sig, titrationModel, type ResolvedSpec, type SimEvent } from "../src/index.js";
import type { SimModel, Values } from "../src/sims/models.js";
import { FIXTURES, fixtures, rendererOf, t } from "./helpers.js";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const FIDELITY = JSON.parse(fs.readFileSync(path.join(FIXTURES, "sim_fidelity.json"), "utf8")) as {
  g: number;
  projectile_sim: { params: Values; readouts: Record<string, string> }[];
  circuit_sim: { params: Values; readouts: Record<string, string> }[];
  titration_sim: { params: Values; samples: { volume: number; "out.ph": string }[]; end_point: string }[];
};
const DT = 1 / CLIENT_KEYS.sim_steps_per_s;
const SF = CLIENT_KEYS.sim_fidelity_sf;

function models(): SimModel<unknown>[] {
  return [projectileModel(FIDELITY.g), circuitModel(["R1", "R2", "R3"]), titrationModel(CLIENT_KEYS.sim_titration_rate_cm3_s)] as SimModel<unknown>[];
}

function seeded(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (Math.imul(a, 1664525) + 1013904223) >>> 0;
    return a / 4294967296;
  };
}

function randomValues(model: SimModel<unknown>, r: () => number): Values {
  const v: Values = { acid_concentration: 0.1, base_concentration: 0.1, acid_volume: 25 };
  for (const p of model.params) {
    if (p.kind === "range") {
      const steps = Math.round(((p.max ?? 1) - (p.min ?? 0)) / (p.step ?? 1));
      v[p.id] = Number(((p.min ?? 0) + Math.floor(r() * (steps + 1)) * (p.step ?? 1)).toFixed(6));
    } else if (p.kind === "choice") v[p.id] = p.choices![Math.floor(r() * p.choices!.length)]!.value;
    else v[p.id] = r() < 0.5;
  }
  if (v.mode === "horizontal" && v.height === 0) v.height = 1;
  return v;
}

describe("VSL-30", () => {
  test("vsl30_sim_deterministic", () => {
    for (const model of models()) {
      for (let seed = 1; seed <= 1000; seed += 1) {
        const values = randomValues(model, seeded(seed));
        const run = () => {
          let state = Object.freeze(model.init(values));
          const trace: unknown[] = [];
          for (let i = 0; i < 30; i += 1) {
            state = Object.freeze(model.next(state, values, DT));
            trace.push(state, model.read(state, values));
          }
          return JSON.stringify(trace);
        };
        expect(run(), `${model.kind} seed ${seed}`).toBe(run());
      }
      // The contract's declared parts: parameters with ranges and defaults, readouts with units and precision.
      for (const p of model.params) {
        expect(p.labelKey).toMatch(/^sim\./);
        if (p.kind === "range") expect([p.min, p.max, p.step].every((x) => typeof x === "number")).toBe(true);
      }
      for (const r of model.readouts) expect(r.sf).toBeGreaterThan(0);
    }
  });
});

describe("VSL-31", () => {
  test("vsl31_sim_matches_tools", () => {
    let points = 0;
    const projectile = projectileModel(FIDELITY.g);
    for (const row of FIDELITY.projectile_sim) {
      const read = projectile.read(runToEnd(projectile, row.params, DT), row.params);
      for (const [id, tool] of Object.entries(row.readouts)) {
        expect(sig(read[id]!, SF), `projectile ${JSON.stringify(row.params)} ${id}`).toBe(sig(Number(tool), SF));
        points += 1;
      }
    }
    for (const row of FIDELITY.circuit_sim) {
      const ids = Object.keys(row.params).filter((k) => /^R\d$/.test(k)).sort();
      const model = circuitModel(ids);
      const read = model.read(model.init(row.params), { ...row.params, switch: true });
      for (const [id, tool] of Object.entries(row.readouts)) {
        expect(sig(read[id]!, SF), `circuit ${JSON.stringify(row.params)} ${id}`).toBe(sig(Number(tool), SF));
        points += 1;
      }
    }
    const titration = titrationModel(CLIENT_KEYS.sim_titration_rate_cm3_s);
    for (const row of FIDELITY.titration_sim) {
      for (const sample of row.samples) {
        const read = titration.read({ volume: sample.volume }, row.params);
        expect(sig(read["out.ph"]!, SF), `titration ${JSON.stringify(row.params)} at ${sample.volume}`).toBe(sig(Number(sample["out.ph"]), SF));
        points += 1;
      }
      expect(sig(titration.read({ volume: 0 }, row.params)["out.end_point"]!, SF)).toBe(sig(Number(row.end_point), SF));
    }
    expect(points).toBeGreaterThanOrEqual(30);
  });

  test("an angled launch matches phys_projectile: 30° and 60° land together, 45° goes furthest", () => {
    const projectile = projectileModel(FIDELITY.g);
    // The tool's own angled samples are in the fidelity table (generated against phys_projectile).
    const angled = FIDELITY.projectile_sim.filter((row) => row.params.mode === "angled");
    expect(angled.map((row) => row.params.angle)).toEqual(expect.arrayContaining([30, 45, 60]));
    const tool = (angle: number) => angled.find((row) => row.params.angle === angle && row.params.speed === 20 && row.params.height === 0)!.readouts;
    expect(tool(30)["out.range"]).toBe(tool(60)["out.range"]);
    const landed = (angle: number, speed = 20) => {
      const values: Values = { mode: "angled", speed, angle, height: 0 };
      return projectile.read(runToEnd(projectile, values, DT), values);
    };
    for (const angle of [30, 45, 60]) {
      const read = landed(angle);
      for (const id of ["out.time", "out.range", "out.max_height"]) expect(sig(read[id]!, SF), `${angle}° ${id}`).toBe(sig(Number(tool(angle)[id]), SF));
      // Where it lands: the ball's own position at the end of the flight is the range, at ground level.
      expect(read["out.x"]!).toBeCloseTo(read["out.range"]!, 9);
      expect(read["out.y"]!).toBeCloseTo(0, 9);
    }
    // Complementary angles land together at every speed; the slider's 45° goes furthest, and the steeper flight is
    // higher and longer.
    for (const speed of [5, 12, 20, 40]) {
      for (const angle of [5, 15, 30, 40]) expect(landed(angle, speed)["out.range"]!).toBeCloseTo(landed(90 - angle, speed)["out.range"]!, 9);
      const ranges = Array.from({ length: 17 }, (_, i) => 5 + 5 * i).map((angle) => [angle, landed(angle, speed)["out.range"]!] as const);
      expect(ranges.reduce((a, b) => (b[1] > a[1] ? b : a))[0], `${speed} m/s`).toBe(45);
    }
    expect(landed(60)["out.max_height"]!).toBeGreaterThan(landed(30)["out.max_height"]!);
    expect(landed(60)["out.time"]!).toBeGreaterThan(landed(30)["out.time"]!);
    // The other launches are unchanged by the angle: it applies to an angled launch only.
    const horizontal: Values = { mode: "horizontal", speed: 12, angle: 60, height: 20 };
    expect(projectile.read(runToEnd(projectile, horizontal, DT), horizontal)["out.range"]!).toBeCloseTo(projectile.read(runToEnd(projectile, { ...horizontal, angle: 10 }, DT), { ...horizontal, angle: 10 })["out.range"]!, 12);
    expect(projectile.params.find((p) => p.id === "angle")).toMatchObject({ labelKey: "sim.projectile.angle", unit: "°", min: 5, max: 85, step: 5, default: 45, when: { mode: "angled" } });
  });
});

async function mount(spec: ResolvedSpec, reducedMotion: boolean, events: SimEvent[] = [], focus: string[] = [], spotlight = false) {
  const R = rendererOf(spec.type);
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  await act(async () => {
    root.render(<R.Component spec={spec} step={0} labels="shown" focus={focus} spotlight={spotlight} size={{ width: 480, height: 320 }} reducedMotion={reducedMotion} onPartActivate={() => undefined} t={t} onSimEvent={(e) => events.push(e)} visible />);
  });
  return { container, unmount: () => act(async () => root.unmount()).then(() => container.remove()) };
}

describe("VSL-32", () => {
  test("vsl32_sim_a11y_audit", async () => {
    const axe = (await import("axe-core")).default;
    // The free simulations; a predict scenario's flow has its own audit in predict.test.tsx (VSL-47).
    // The free S2 simulations; the S3 ones have their own audit in science.test.tsx.
    const sims = fixtures().filter((f) => f.kind.endsWith("_sim") && SIM_SETUPS[f.kind] === undefined && (f.spec.params as { predict?: string }).predict === undefined);
    expect(sims.map((f) => f.kind).sort()).toEqual(["circuit_sim", "projectile_sim", "titration_sim"]);
    for (const f of sims) {
      const events: SimEvent[] = [];
      const { container, unmount } = await mount(f.spec, true, events);
      // Every control is a native, labelled control; ranges say their unit and their value.
      const controls = [...container.querySelectorAll<HTMLInputElement | HTMLSelectElement>("input, select")];
      expect(controls.length, f.id).toBeGreaterThanOrEqual(2);
      for (const c of controls) {
        const label = container.querySelector(`label[for="${c.id}"]`);
        expect((label?.textContent ?? "").trim().length, `${f.id}: ${c.id} has a visible label`).toBeGreaterThan(0);
        if (c instanceof HTMLInputElement && c.type === "range") {
          expect(c.getAttribute("step"), `${f.id}: ${c.id} steps`).not.toBeNull();
          expect(c.getAttribute("aria-valuetext") ?? "", `${f.id}: ${c.id} announces its value`).toContain(c.value);
          const unit = (label?.textContent ?? "").match(/\(([^)]+)\)/)?.[1];
          if (unit !== undefined) expect(c.getAttribute("aria-valuetext") ?? "", `${f.id}: ${c.id} unit`).toContain(unit);
          if (c.disabled) continue;
          // Page keys move ten steps.
          const before = Number(c.value);
          const step = Number(c.getAttribute("step"));
          await act(async () => {
            c.dispatchEvent(new KeyboardEvent("keydown", { key: "PageUp", bubbles: true }));
          });
          const after = Number((container.querySelector<HTMLInputElement>(`#${CSS.escape(c.id)}`)!).value);
          expect(after, `${f.id}: ${c.id} PageUp`).toBeCloseTo(Math.min(Number(c.getAttribute("max")), before + 10 * step), 6);
        }
      }
      expect(events.some((e) => e.type === "sim.param_changed"), f.id).toBe(true);
      // Readouts go to a polite live region, and the text mode is one control away.
      const live = container.querySelector("[aria-live='polite']");
      expect(live, f.id).not.toBeNull();
      const toggle = [...container.querySelectorAll("button")].find((b) => b.textContent === t("sim.show_table"))!;
      expect(toggle, f.id).toBeDefined();
      await act(async () => toggle.click());
      expect(container.querySelector("[data-sim-table]"), f.id).not.toBeNull();
      const reset = [...container.querySelectorAll("button")].find((b) => b.textContent === t("sim.reset"))!;
      await act(async () => reset.click());
      expect(events.some((e) => e.type === "sim.reset"), f.id).toBe(true);
      const record = [...container.querySelectorAll("button")].find((b) => b.textContent === t("sim.record"))!;
      await act(async () => record.click());
      expect(events.find((e) => e.type === "sim.reading_recorded")?.reading, f.id).toBeDefined();
      const result = await axe.run(container, { rules: { "color-contrast": { enabled: false }, region: { enabled: false } } });
      expect(result.violations.map((v) => `${v.id}: ${v.help}`), f.id).toEqual([]);
      await unmount();
    }
  }, 120_000);

  test("reduced motion shows each change's final state, and readouts are announced at most once a second", async () => {
    const projectile = fixtures().find((f) => f.id === "projectile-sim")!;
    const { container, unmount } = await mount(projectile.spec, true);
    const range = (projectile.spec.computed as { labels: Record<string, string> }).labels["out.range"]!;
    const readouts = [...container.querySelectorAll("dd")].map((d) => d.textContent ?? "");
    expect(readouts.some((r) => r.startsWith(range)), "the ball has landed: the distance across is the range").toBe(true);
    const speed = container.querySelector<HTMLInputElement>("input[type=range]")!;
    const live = container.querySelector("[aria-live='polite']")!;
    await act(async () => speed.dispatchEvent(new KeyboardEvent("keydown", { key: "PageUp", bubbles: true })));
    const first = live.textContent;
    await act(async () => speed.dispatchEvent(new KeyboardEvent("keydown", { key: "PageDown", bubbles: true })));
    expect(live.textContent, "a second change within the interval is not announced again").toBe(first);
    await unmount();
  });
});

describe("VSL-30 pointing", () => {
  test("the tutor's pointing rings a readout or a control, and the spotlight dims the rest", async () => {
    const axe = (await import("axe-core")).default;
    const projectile = fixtures().find((f) => f.id === "projectile-sim")!;
    const { container, unmount } = await mount(projectile.spec, true, [], ["out.range"]);
    const range = container.querySelector<HTMLElement>("dd[data-part='out.range']")!;
    expect(range.getAttribute("data-pointed")).toBe("true");
    expect(range.className).toContain("outline-highlight-line");
    expect(range.textContent, "a screen reader hears it was pointed out").toContain(t("visual.part.pointed"));
    expect(container.querySelectorAll("[data-pointed]")).toHaveLength(1);
    expect(container.querySelectorAll("[data-dimmed]"), "no spotlight: nothing dimmed").toHaveLength(0);
    expect((await axe.run(container, { rules: { "color-contrast": { enabled: false }, region: { enabled: false } } })).violations.map((v) => v.id)).toEqual([]);
    await unmount();
    // A control, under the spotlight: it keeps its ring and full opacity, the other controls and readouts are dimmed.
    const lit = await mount(projectile.spec, true, [], ["ctrl.speed"], true);
    const speed = lit.container.querySelector(`input[data-part='ctrl.speed']`)!.closest("label")!;
    expect(speed.getAttribute("data-pointed")).toBe("true");
    expect(speed.style.opacity).toBe("");
    expect(speed.textContent).toContain(t("visual.part.pointed"));
    const dimmed = [...lit.container.querySelectorAll<HTMLElement>("[data-dimmed]")];
    expect(dimmed.length).toBeGreaterThan(2);
    for (const d of dimmed) expect(Number(d.style.opacity)).toBe(CLIENT_KEYS.board_spotlight_dim_opacity);
    expect(lit.container.querySelector("dd[data-part='out.range']")?.getAttribute("data-dimmed")).toBe("true");
    await lit.unmount();
  });

  test("the launch angle is a control only for an angled launch", async () => {
    const projectile = fixtures().find((f) => f.id === "projectile-sim")!;
    const { container, unmount } = await mount(projectile.spec, true);
    const angleOf = () => container.querySelector<HTMLInputElement>(`#${CSS.escape(`${projectile.spec.visual_id}-angle`)}`);
    expect(angleOf(), "a horizontal launch has no angle").toBeNull();
    const mode = container.querySelector<HTMLSelectElement>("select")!;
    await act(async () => {
      mode.value = "angled";
      mode.dispatchEvent(new Event("change", { bubbles: true }));
    });
    expect([angleOf()?.value, angleOf()?.getAttribute("aria-valuetext")]).toEqual(["45", "45°"]);
    expect(container.querySelector(`label[for="${angleOf()!.id}"]`)?.textContent).toContain(`${t("sim.projectile.angle")} (°)`);
    await unmount();
  });
});
