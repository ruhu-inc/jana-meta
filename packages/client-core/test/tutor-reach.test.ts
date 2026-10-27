// SPEC §10.3: whether any tutor can answer now, from the core's model state and the connectivity slice; when neither
// the online tutor nor a model on this computer can, the composer says so instead of taking the question.
import { describe, expect, test } from "vitest";
import { emptyConnectivity, seedConnectivity, type ConnectivityReply, type ConnectivitySlice } from "../src/connectivity.js";
import { tutorReach } from "../src/health.js";

const models = (installed: unknown[], tutorPath = "local") => ({
  installed, available: [], assignment: { fast: null, strong: null }, recommended: { fast: null, strong: null, reason_key: "no_class.no_model_manifest" },
  hardware: { hardware_class: "high", basis: "predicted", provisional: true, shortfalls: [], benchmark: null, benchmark_due: true, class_choice: null, tutor_path: tutorPath, runtime: null },
}) as never;
// The demo host: no model on this computer, the runtime reports ready because the online tutor carries the turns.
const ready = { status: "ok" as const, readiness: "ready" as const, components: { runtime: "ok" as const } };
const none = models([]);
const local = models([{ model_id: "glimmer", pack_version: "1", serving: true }]);

function slice(network: ConnectivityReply["network"], cloud: { enabled: boolean; state?: "idle" | "unavailable" } | null): ConnectivitySlice {
  const features: ConnectivityReply["features"] = { downloads: { enabled: false, state: "idle" } };
  if (cloud !== null) features.cloud_tier = { enabled: cloud.enabled, state: cloud.state ?? "idle" };
  return seedConnectivity(emptyConnectivity(), { network, features } as ConnectivityReply);
}

describe("SPEC §10.3", () => {
  test("no tutor when the online tutor is switched off and there is no model here", () => {
    expect(tutorReach({ health: ready, models: none }, slice("online", { enabled: false }))).toBe("switched_off");
  });

  test("no tutor offline, or when the online tutor cannot be reached, with no model here", () => {
    for (const network of ["offline", "off", "limited"] as const) expect(tutorReach({ health: ready, models: none }, slice(network, { enabled: true }))).toBe("offline");
    expect(tutorReach({ health: ready, models: none }, slice("online", { enabled: true, state: "unavailable" }))).toBe("offline");
  });

  test("the online tutor answers when it is on and reachable", () => {
    expect(tutorReach({ health: ready, models: none }, slice("online", { enabled: true }))).toBe("available");
    expect(tutorReach({ health: ready, models: none }, slice("metered", { enabled: true }))).toBe("available");
  });

  test("a model on this computer answers offline and with the online tutor off", () => {
    expect(tutorReach({ health: ready, models: local }, slice("offline", { enabled: true }))).toBe("available");
    expect(tutorReach({ health: ready, models: local }, slice("online", { enabled: false }))).toBe("available");
  });

  test("a school server answers whatever the online tutor does", () => {
    expect(tutorReach({ health: ready, models: models([], "school_server") }, slice("offline", { enabled: false }))).toBe("available");
  });

  test("nothing is decided before the core has said, nor in a build without the online tutor", () => {
    expect(tutorReach({ health: null, models: null }, slice("offline", { enabled: false }))).toBe("checking");
    expect(tutorReach({ health: ready, models: none }, emptyConnectivity())).toBe("checking");
    expect(tutorReach({ health: ready, models: none }, slice("offline", null))).toBe("available");
  });
});
