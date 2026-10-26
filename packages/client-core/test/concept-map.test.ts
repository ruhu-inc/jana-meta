// The concept map in the client core (UXS-22 map view): the reply is checked against the contract; node badges count
// the learner's questions and gather their mistakes; open questions are the kept ones with no KC; a root-gap card
// lights the mistake's gap path (or the shortest chain when the mistake is not on the map yet); a mastery change
// re-reads only a map the KC is on; and locking the profile drops the map. Against the fake core; synthetic data.
import { describe, expect, test, vi } from "vitest";
import { ConceptMapController, ProfileController, StoreHolder, nodeBadges, openQuestions, pathOn, type ConceptMap, type ConceptNode } from "../src/index.js";
import { FakeProfileCore, PROFILES } from "./profilecore.js";

const BEN = PROFILES[1]!;
const SUBJECT = "cur.phy.o";
const VT = "kc.phy.o.motion.velocity_time_gradient";
const SPEED = "kc.phy.o.motion.average_speed";
const GRADIENT = "kc.mth.o.coordinate_geometry.gradient";

const node = (kc_id: string, state: ConceptNode["state"] = "not_started", linked = false): ConceptNode => ({
  kc_id, code: `C-${kc_id.length}`, statement: `Skill ${kc_id}`, subject_id: linked ? "cur.mth.o" : SUBJECT, topic_id: "cur.phy.o.motion", topic_title: "Motion",
  exam_weight: 0.4, state, band: state === "mastered" ? "secure" : state === "not_started" ? "not_started" : "learning", linked,
});

function conceptMap(): ConceptMap {
  return {
    subject_id: SUBJECT, subject: "physics", level: "O", status: "ready", pack: { pack_id: "pack.phy.o", version: "0.1.0" },
    nodes: [node(SPEED, "mastered"), node(VT, "explaining"), node(GRADIENT, "not_started", true)],
    edges: [
      { from: SPEED, to: VT, kind: "prerequisite", strength: "required" },
      { from: GRADIENT, to: VT, kind: "root_gap", misconception_id: "mc.phy.o.vt_gradient_from_one_point", misconception_name: "Acceleration from a single point", idea: "the gradient of a straight line", reviewed: false },
    ],
    next: [{ kc_id: VT, reason: "ready", weight: "medium", needs: [] }],
    questions: [
      { question_id: "msg_1", session_id: "ses_1", kc_id: VT, text: "How do I get acceleration?", input: "typed", asked_at: 3, kept: true },
      { question_id: "msg_2", session_id: "ses_2", kc_id: VT, text: "Why the change?", input: "spoken", asked_at: 2, kept: true },
      { question_id: "ses_3", session_id: "ses_3", kc_id: VT, text: null, input: "typed", asked_at: 1, kept: false },
      { question_id: "msg_4", session_id: "ses_4", kc_id: null, text: "What does this symbol mean?", input: "photo", asked_at: 4, kept: true },
    ],
    mistakes: [{
      misconception_id: "mc.phy.o.vt_gradient_from_one_point", kc_id: VT, name: "Acceleration from a single point", status: "active", times: 3, last_seen_at: 5,
      root_kc_id: GRADIENT, idea: "the gradient of a straight line", reviewed: false, gap_path: [GRADIENT, VT],
    }],
  };
}

async function unlocked(core = new FakeProfileCore()) {
  const profiles = new ProfileController(core.launch, new StoreHolder(), { fetch: core.fetch });
  await profiles.load();
  expect(await profiles.unlock(BEN.profile_id)).toBe(true);
  return { core, profiles };
}

describe("concept map", () => {
  test("badges_count_questions_and_gather_mistakes", () => {
    const badges = nodeBadges(conceptMap());
    expect(badges.get(VT)).toMatchObject({ asked: 3 });
    expect(badges.get(VT)!.mistakes.map((m) => m.name)).toEqual(["Acceleration from a single point"]);
    expect(badges.get(SPEED)).toBeUndefined();
    expect(openQuestions(conceptMap()).map((q) => q.text)).toEqual(["What does this symbol mean?"]);
  });

  test("gap_path_from_a_root_gap_card", async () => {
    const { core, profiles } = await unlocked();
    core.conceptMaps.set(SUBJECT, conceptMap());
    const controller = new ConceptMapController(profiles);
    await controller.load(SUBJECT);
    expect(controller.getView().status).toBe("ready");
    controller.showGap({ misconceptionId: "mc.phy.o.vt_gradient_from_one_point", rootKcId: GRADIENT, kcId: VT });
    expect(controller.getView().gap).toEqual({ path: [GRADIENT, VT], misconceptionId: "mc.phy.o.vt_gradient_from_one_point" });
    // A misconception not on the learner's list yet still lights the shortest chain of map edges.
    controller.showGap({ misconceptionId: "mc.phy.o.other", rootKcId: SPEED, kcId: VT });
    expect(controller.getView().gap?.path).toEqual([SPEED, VT]);
    controller.showGap({ rootKcId: VT, kcId: SPEED });
    expect(controller.getView().gap).toBeNull();
    expect(pathOn(conceptMap(), GRADIENT, SPEED)).toEqual([]);
    controller.showGap({ rootKcId: GRADIENT, kcId: VT });
    controller.clearGap();
    expect(controller.getView().gap).toBeNull();
  });

  test("a_gap_asked_before_the_map_is_read_lights_once_it_is", async () => {
    const { core, profiles } = await unlocked();
    core.conceptMaps.set(SUBJECT, conceptMap());
    const controller = new ConceptMapController(profiles);
    controller.showGapOn(SUBJECT, { misconceptionId: "mc.phy.o.vt_gradient_from_one_point", rootKcId: GRADIENT, kcId: VT });
    expect(controller.getView().gap).toBeNull();
    await controller.load(SUBJECT);
    expect(controller.getView().gap?.path).toEqual([GRADIENT, VT]);
  });

  test("malformed_reply_fails_progress_rereads_lock_clears", async () => {
    const { core, profiles } = await unlocked();
    core.conceptMaps.set(SUBJECT, { ...conceptMap(), nodes: "lots" });
    const controller = new ConceptMapController(profiles);
    await controller.load(SUBJECT);
    expect(controller.getView()).toMatchObject({ status: "failed", map: null });
    core.conceptMaps.set(SUBJECT, conceptMap());
    await controller.load(SUBJECT);
    const reads = () => core.log.filter((l) => l.path === `/v1/curriculum/${SUBJECT}/concept-map`).length;
    expect(reads()).toBe(2);
    controller.onProgress("kc.chm.o.moles.amount");
    expect(reads()).toBe(2);
    controller.onProgress(SPEED);
    await vi.waitFor(() => expect(reads()).toBe(3));
    await profiles.lock();
    expect(controller.getView()).toEqual({ status: "idle", subjectId: null, map: null, gap: null });
  });
});
