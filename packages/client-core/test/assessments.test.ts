import { expect, test } from "vitest";
import { AssessmentController, EMPTY_ASSESSMENTS, readAssessment } from "../src/assessments.js";
import { ProfileController } from "../src/profiles.js";
import { StoreHolder } from "../src/session.js";
import { EXPLAINING, FOLLOW_UP, assessment, assessmentCore } from "./assessmentcore.js";
import { PROFILES } from "./profilecore.js";
const answer = [{ part_id: "a", kind: "mcq" as const, option_id: "a" }];
async function start(explains = false) {
  const fake = assessmentCore({ explains }), profiles = new ProfileController(fake.core.launch, new StoreHolder(), { fetch: fake.fetch });
  await profiles.load(); await profiles.unlock(PROFILES[0]!.profile_id);
  const checks = new AssessmentController(profiles); await checks.load();
  return { ...fake, profiles, checks };
}
test("diagnostic starts without a tutor or network and resumes the next unanswered item after restart", async () => {
  const s = await start();
  await s.checks.start({ kind: "diagnostic", subject: "physics" });
  await s.checks.answer(null); await s.checks.action("stop");
  const restarted = new AssessmentController(s.profiles); await restarted.load();
  expect(restarted.getView().assessments[0]?.answered_count).toBe(1);
  await restarted.open(s.checks.getView().current!.assessment_id); await restarted.action("resume");
  expect(restarted.getView().current?.current_item?.item_id).toBe("itm.phy.o.synthetic.0002");
  await restarted.answer(answer);
  expect(restarted.getView().current?.state).toBe("completed");
  expect(s.core.log.filter((r) => /turns|consents|egress/.test(r.path))).toEqual([]);
});
test("lost answer response retries the original body and key once committed", async () => {
  const s = await start(); await s.checks.start({ kind: "diagnostic", subject: "physics" });
  s.lose(true); expect(await s.checks.answer(answer)).toBe(false);
  expect(s.checks.getView().uncertain).toBe(true);
  s.lose(false); expect(await s.checks.answer(null)).toBe(true);
  const posts = s.writes.filter((r) => r.path.endsWith("/answers"));
  expect(posts).toHaveLength(3); expect(posts[1]).toEqual(posts[0]); expect(posts[2]).toEqual(posts[0]);
  expect(s.checks.getView().current?.answered_count).toBe(1);
});
test("mastery checks show the core's spacing and never offer diagnostic skipping", async () => {
  const s = await start(); await s.checks.start({ kind: "mastery_check", subject: "physics", kc_id: "kc.phy.o.synthetic" });
  expect(await s.checks.answer(null)).toBe(false);
  await s.checks.answer(answer); await s.checks.answer(answer);
  expect(s.checks.getView().current).toMatchObject({ state: "waiting", available_at: "2026-10-20T10:00:00Z", last_mark: { verdict: "correct" } });
});
test("the mock lock is a definitive refusal and can be retried after submission", async () => {
  const s = await start(); s.fail("tutor_locked");
  expect(await s.checks.start({ kind: "diagnostic", subject: "physics" })).toBe(false);
  expect(s.checks.getView()).toMatchObject({ error: "tutor_locked", uncertain: false });
  s.fail(null); expect(await s.checks.start({ kind: "diagnostic", subject: "physics" })).toBe(true);
});
test("profile switching clears saved assessments and drops late responses", async () => {
  const s = await start(); await s.checks.start({ kind: "diagnostic", subject: "physics" });
  const late = s.checks.answer(answer);
  await s.profiles.unlock(PROFILES[1]!.profile_id); await late;
  expect(s.checks.getView()).toEqual(EMPTY_ASSESSMENTS);
  await s.checks.load(); expect(s.checks.getView().assessments).toEqual([]);
});
test("presentation boundary refuses marks in a diagnostic and private answer fields", () => {
  const valid = assessment(); expect(readAssessment(valid)).toMatchObject(valid);
  expect(() => readAssessment({ ...valid, current_item: { ...valid.current_item, marks: 1 } })).toThrow("invalid_reply");
  expect(() => readAssessment({ ...valid, current_item: { ...valid.current_item, answer: "private answer" } })).toThrow("invalid_reply");
});
test("explain it back: a passed check waits for the learner's own explanation before it is mastered", async () => {
  const s = await start(true); await s.checks.start({ kind: "mastery_check", subject: "physics", kc_id: "kc.phy.o.synthetic" });
  await s.checks.answer(answer); await s.checks.answer(answer);
  const list = s.rows.get(PROFILES[0]!.profile_id)!; // the spacing has passed: the third question is served
  list.splice(0, 1, { ...assessment("mastery_check", 2), kc_id: "kc.phy.o.synthetic" });
  await s.checks.open(list[0]!.assessment_id); await s.checks.answer(answer);
  expect(s.checks.getView().current).toMatchObject({ state: "explaining", explain: EXPLAINING, current_item: null });
  expect(await s.checks.explain("   ")).toBe(false); // nothing to judge is never sent
  expect(await s.checks.explain("It is how fast it goes.")).toBe(true);
  expect(s.checks.getView().current).toMatchObject({ state: "explaining", explain: { outcome: "follow_up", follow_up: FOLLOW_UP, attempts: 1 } });
  expect(await s.checks.explain("The change in velocity divided by the time.", "spoken")).toBe(true);
  expect(s.checks.getView().current).toMatchObject({ state: "completed", explain: { outcome: "passed" } });
  const sent = s.writes.filter((w) => w.path.endsWith("/explain")).map((w) => w.body);
  expect(sent.map((b) => [b.text, b.modality])).toEqual([["It is how fast it goes.", "typed"], ["The change in velocity divided by the time.", "spoken"]]);
});
test("explain it back: the reader refuses an explaining check with no explanation and a malformed one", () => {
  const waiting = { ...assessment("mastery_check", 3), state: "explaining" as const, current_item: null, explain: { ...EXPLAINING } };
  expect(readAssessment(waiting)).toMatchObject({ state: "explaining" });
  expect(() => readAssessment({ ...waiting, explain: undefined })).toThrow("invalid_reply");
  expect(() => readAssessment({ ...waiting, explain: { ...EXPLAINING, outcome: "answer_shown" } })).toThrow("invalid_reply");
  expect(() => readAssessment({ ...assessment(), explain: { ...EXPLAINING } })).toThrow("invalid_reply"); // never on a diagnostic
});
