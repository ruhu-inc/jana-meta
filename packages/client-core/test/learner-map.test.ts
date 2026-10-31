// The learner's map in the client core (SPEC §21, W10): the scrubber's weekly dates (at most 26 weeks, from the first
// learning event), a node's layer facts (codes the UI words; a reply from a core before W10 reads as "not yet"), the
// layer and the scrubber kept in memory only and dropped on lock, a dated map replacing the shown one and "Today"
// restoring the live one without a read, a skill's links read once, and the overview checked at the boundary.
// Against the fake core; synthetic data.
import { describe, expect, test } from "vitest";
import { ConceptMapController, MapOverviewController, ProfileController, StoreHolder, layerFacts, weeklyDates, type ConceptMap, type ConceptNode, type KcLinks } from "../src/index.js";
import { FakeProfileCore, PROFILES } from "./profilecore.js";

const BEN = PROFILES[1]!;
const SUBJECT = "cur.phy.o";
const VT = "kc.phy.o.motion.velocity_time_gradient";

const node = (band: ConceptNode["band"], extra: Partial<ConceptNode> = {}): ConceptNode => ({
  kc_id: VT, code: "1.2", statement: "Find acceleration from the gradient", subject_id: SUBJECT, topic_id: "cur.phy.o.motion", topic_title: "Motion",
  exam_weight: 0.4, state: band === "secure" ? "mastered" : band === "learning" ? "learning" : "not_started", band, linked: false, ...extra,
});

const mapOf = (n: ConceptNode, asOf: string | null = null): ConceptMap => ({
  subject_id: SUBJECT, subject: "physics", level: "O", status: "ready", pack: { pack_id: "pack.phy.o", version: "0.1.0" },
  nodes: [n], edges: [], next: [], questions: [], as_of: asOf, first_day: "2026-09-01",
  mistakes: [
    { misconception_id: "mc.phy.o.a", kc_id: VT, name: "A", status: "active", times: 2, last_seen_at: 1, root_kc_id: null, idea: null, reviewed: null, gap_path: [] },
    { misconception_id: "mc.phy.o.b", kc_id: VT, name: "B", status: "disputed", times: 1, last_seen_at: 1, root_kc_id: null, idea: null, reviewed: null, gap_path: [] },
    { misconception_id: "mc.phy.o.c", kc_id: VT, name: "C", status: "resolved", times: 1, last_seen_at: 1, root_kc_id: null, idea: null, reviewed: null, gap_path: [] },
  ],
});

const LINKS: KcLinks = { kc_id: VT, materials: [], moments: [{ source_id: "src_01HZZZZZZZZZZZZZZZZZZZZZZZ", at_ms: 252_000, title: "Lecture" }], notes: [], tracked: true, misconceptions: [] };

async function unlocked(core = new FakeProfileCore()) {
  const profiles = new ProfileController(core.launch, new StoreHolder(), { fetch: core.fetch });
  await profiles.load();
  expect(await profiles.unlock(BEN.profile_id)).toBe(true);
  return { core, profiles };
}

describe("learner's map", () => {
  test("weekly_dates_from_the_first_event_at_most_26_weeks", () => {
    expect(weeklyDates("2026-10-20", "2026-10-31")).toEqual(["2026-10-17", "2026-10-24", "2026-10-31"]);
    expect(weeklyDates(null, "2026-10-31")).toEqual(["2026-10-31"]);
    const long = weeklyDates("2020-01-01", "2026-10-31");
    expect(long).toHaveLength(27);
    expect(long[0]).toBe("2026-05-02");
  });

  test("layer_facts_are_codes_and_an_old_core_reads_as_not_yet", () => {
    const facts = layerFacts(mapOf(node("learning", { freshness: "week", refresh_due: false, changed_since: "new", study: { materials: 2, moments: 1, cards_due: 1 }, notes: 1, tracked: true })), node("learning"));
    expect(facts).toMatchObject({ freshness: "never", rings: ["active", "disputed"], changed: null });
    const n = node("learning", { freshness: "week", refresh_due: false, changed_since: "new", study: { materials: 2, moments: 1, cards_due: 1 }, notes: 1, tracked: true });
    expect(layerFacts(mapOf(n), n)).toEqual({ freshness: "week", refreshDue: false, rings: ["active", "disputed"], study: { materials: 2, moments: 1, cards_due: 1 }, notes: 1, tracked: true, changed: "new" });
  });

  test("layer_and_scrubber_in_memory_today_restores_without_a_read", async () => {
    const { core, profiles } = await unlocked();
    core.conceptMaps.set(SUBJECT, mapOf(node("secure")));
    core.datedMaps.set(`${SUBJECT}@2026-10-03`, mapOf(node("not_started"), "2026-10-03"));
    const controller = new ConceptMapController(profiles);
    await controller.load(SUBJECT);
    controller.setLayer("freshness");
    expect(controller.getLens().layer).toBe("freshness");
    await controller.scrub("2026-10-03");
    expect(controller.getLens()).toMatchObject({ asOf: "2026-10-03", scrubbing: false, layer: "freshness" });
    expect(controller.getView().map?.nodes[0]?.band).toBe("not_started");
    const reads = () => core.log.filter((l) => l.path === `/v1/curriculum/${SUBJECT}/concept-map`).length;
    const before = reads();
    await controller.scrub(null);
    expect(reads()).toBe(before);
    expect(controller.getView().map?.nodes[0]?.band).toBe("secure");
    // A date the core refuses keeps the map shown.
    await controller.scrub("2020-01-01");
    expect(controller.getLens().scrubFailed).toBe(true);
    expect(controller.getView().map?.nodes[0]?.band).toBe("secure");
    await profiles.lock();
    expect(controller.getLens()).toEqual({ layer: "mastery", asOf: null, scrubbing: false, scrubFailed: false, links: {} });
  });

  test("links_read_once_and_the_overview_checked", async () => {
    const { core, profiles } = await unlocked();
    core.conceptMaps.set(SUBJECT, mapOf(node("secure")));
    core.kcLinks.set(VT, LINKS);
    const controller = new ConceptMapController(profiles);
    await controller.load(SUBJECT);
    await controller.links(VT);
    await controller.links(VT);
    expect(controller.getLens().links[VT]).toEqual(LINKS);
    expect(core.log.filter((l) => l.path.endsWith("/links")).length).toBe(1);
    const overview = new MapOverviewController(profiles);
    core.overview = { subjects: "lots" };
    await overview.load();
    expect(overview.getView().status).toBe("failed");
    core.overview = { subjects: [{ subject_id: SUBJECT, subject: "physics", level: "O", topics: [] }] };
    await overview.load();
    expect(overview.getView()).toMatchObject({ status: "ready" });
    await profiles.lock();
    expect(overview.getView()).toEqual({ status: "idle", overview: null });
  });
});
