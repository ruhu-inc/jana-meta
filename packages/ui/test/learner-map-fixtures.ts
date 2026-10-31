// The learner's map test data (SPEC §21, W10): the Physics reply the core serves (test_concept_map.py) and the same
// map with synthetic layer facts on three skills. Every learner here is synthetic.
import fs from "node:fs";
import path from "node:path";
import { readConceptMap, type ConceptMap } from "@jana/client-core";

export const VT = "kc.phy.o.motion.velocity_time_gradient";
export const SPEED = "kc.phy.o.motion.average_speed";
export const FALL = "kc.phy.o.motion.free_fall";
export const BASE = readConceptMap(JSON.parse(fs.readFileSync(path.join(import.meta.dirname, "fixtures", "concept-map.phy.json"), "utf8"))) as ConceptMap;

/** The Physics map with layer facts: v-t gradient practised this week, refresh due, up since last time, Study, a note
 * and tracked; average speed practised today and new; free fall never practised. */
export function layered(): ConceptMap {
  return readConceptMap({
    ...BASE,
    nodes: BASE.nodes.map((n) => n.kc_id === VT
      ? { ...n, state: "needs_review", band: "learning", freshness: "week", refresh_due: true, changed_since: "up", study: { materials: 2, moments: 1, cards_due: 1 }, notes: 1, tracked: true }
      : n.kc_id === SPEED ? { ...n, freshness: "today", refresh_due: false, changed_since: "new", study: { materials: 0, moments: 0, cards_due: 0 }, notes: 0, tracked: false }
        : n.linked ? n : { ...n, freshness: "never", refresh_due: false, changed_since: null, study: { materials: 0, moments: 0, cards_due: 0 }, notes: 0, tracked: false }),
  }) as ConceptMap;
}

