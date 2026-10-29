// SPEC §19.3.4, §19.5.5, §19.5.6, §19.6 on the client (W8 phase 3): the due query is validated and drives the Home
// card (nothing on an older core), dismiss and open go to the commitment's routes, an opened check-in shows the thread
// with its `checkin_id`, a notification carries only the id and kind and only with the setting on and the OS
// permission granted (a refusal turns the setting off), and a lock or profile switch drops the card and cancels what
// was shown. Notes read their lifecycle with defaults; the new online feature and its notice version are known.
import { describe, expect, test } from "vitest";
import { errors } from "@jana/contracts-ts";
import {
  CHECKIN_KINDS, CHECKIN_NOTIFICATION_KEYS, CompanionController, EMPTY_CHECKIN, readCheckinsDue, type CheckinNotifier, type Commitment, type CompanionOpened,
} from "../src/companion.js";
import { CONSENT_FEATURES, CONSENT_NOTICE_VERSIONS, ONLINE_FEATURES } from "../src/connectivity.js";
import { knowsReplyProblems, noteLifecycle, readKnows, type KnowsNote } from "../src/memory.js";
import { ProfileController } from "../src/profiles.js";
import { StoreHolder } from "../src/session.js";
import { FakeProfileCore, PROFILES } from "./profilecore.js";

const CMT = `cmt_${"0".repeat(25)}A`;
const ITEM: Commitment = {
  commitment_id: CMT, kind: "event_checkin", subject: "physics", kc_id: null, text: "How did Saturday's mock paper go?",
  due_from: "2026-10-18T07:00:00+01:00", due_until: "2026-10-21T07:00:00+01:00", dedupe_key: "event_checkin:physics:2026-10-17", confidence: 0.8,
  state: "pending", source: "extractor", source_session_id: null, created_at: "2026-10-15T18:00:00+01:00", shown_at: null, resolved_at: null,
};
const OPENED: CompanionOpened = {
  session_id: PROFILES[0]!.session_id, thread_id: `cth_${"6".repeat(26)}`, resumed: true,
  summary: { version: 1, cursor_seq: 4, updated_at: null, topics: [], misconceptions: [], next_step: null, episodes: 1 },
  opener: { opener_id: "2026-10-18", text: "How did Saturday's mock paper go?", facts: {
    last_session_date: "2026-10-16", last_session_mode: "study_companion", last_subject: "physics", next_step: null, learner_cards_due: 0,
    study_cards_due: 0, exam_distance_days: null, pack_ready: false, checkin_id: CMT,
  } },
};
const ok = (body: unknown) => new Response(JSON.stringify(body), { status: 200, headers: { "content-type": "application/json" } });
const refused = (status: number, code: string) => new Response(JSON.stringify({ error: { code, message: "", retryable: false, action_taken: false, request_id: "req_x" } }), { status });

interface Routes { due?: () => Response; dismiss?: () => Response; open?: () => Response; companion?: () => Response }

/** The fake core with the check-in routes in front of it; every request is logged by path. */
function checkinCore(routes: Routes) {
  const core = new FakeProfileCore();
  const calls: { method: string; path: string; body: string | null }[] = [];
  const fetcher = (async (input, init = {}) => {
    const url = new URL(String(input));
    const method = init.method ?? "GET";
    const route = url.pathname === "/v1/checkins/due" ? routes.due
      : url.pathname === `/v1/checkins/${CMT}/dismiss` ? routes.dismiss
        : url.pathname === `/v1/checkins/${CMT}/open` ? routes.open
          : url.pathname === "/v1/companion" ? routes.companion : undefined;
    if (url.pathname.startsWith("/v1/checkins") || url.pathname === "/v1/companion") {
      calls.push({ method, path: url.pathname, body: typeof init.body === "string" ? init.body : null });
      return route?.() ?? refused(404, "not_found");
    }
    return core.fetch(input, init);
  }) as typeof fetch;
  return { core, fetch: fetcher, calls };
}

function notifier(permission: "granted" | "denied" = "granted") {
  const shown: unknown[] = [];
  let cancelled = 0;
  const value: CheckinNotifier = {
    permission: async () => permission,
    notify: async (checkin) => { shown.push(checkin); },
    cancel: async () => { cancelled += 1; },
  };
  return { value, shown, cancelled: () => cancelled };
}

async function opened(fake: ReturnType<typeof checkinCore>, notify?: CheckinNotifier) {
  const profiles = new ProfileController(fake.core.launch, new StoreHolder(), { fetch: fake.fetch });
  await profiles.load();
  await profiles.unlock(PROFILES[0]!.profile_id);
  const companion = new CompanionController(profiles, { fetch: fake.fetch, ...(notify === undefined ? {} : { notifier: notify }) });
  return { profiles, companion };
}

describe("SPEC §19.3.4 the due query and the card", () => {
  test("the reply is validated: at most one, each a contract Commitment", () => {
    expect(readCheckinsDue({ items: [ITEM] }).items[0]?.commitment_id).toBe(CMT);
    expect(readCheckinsDue({ items: [] }).items).toEqual([]);
    expect(() => readCheckinsDue({ items: [ITEM, { ...ITEM, commitment_id: `cmt_${"1".repeat(26)}` }] })).toThrow();
    expect(() => readCheckinsDue({ items: [{ ...ITEM, text: "x".repeat(141) }] })).toThrow();
    expect(() => readCheckinsDue({ items: [{ ...ITEM, kind: "nag" }] })).toThrow();
    expect(errors("api/commands#/$defs/CheckinsDue", { items: [ITEM] })).toEqual([]);
  });

  test("a due check-in is the card's item; dismiss sends no body and removes it; a 404 or 405 hides the card", async () => {
    const fake = checkinCore({ due: () => ok({ items: [ITEM] }), dismiss: () => ok({ ...ITEM, state: "dismissed" }) });
    const { companion } = await opened(fake);
    expect(companion.getCheckin()).toEqual(EMPTY_CHECKIN);
    await companion.loadCheckins();
    expect(companion.getCheckin()).toMatchObject({ status: "ready", item: ITEM });
    expect(await companion.dismissCheckin(CMT)).toBe(true);
    expect(companion.getCheckin().item).toBeNull();
    expect(fake.calls.filter((c) => c.method === "POST")).toEqual([{ method: "POST", path: `/v1/checkins/${CMT}/dismiss`, body: null }]);
    for (const status of [404, 405]) {
      const older = checkinCore({ due: () => refused(status, status === 404 ? "not_found" : "method_not_allowed") });
      const { companion: other } = await opened(older);
      await other.loadCheckins();
      expect(other.getCheckin()).toEqual({ status: "unavailable", item: null, notice: null });
    }
  });

  test("a refused dismissal brings the card back; a check-in already gone stays gone", async () => {
    const fake = checkinCore({ due: () => ok({ items: [ITEM] }), dismiss: () => refused(409, "conflict") });
    const { companion } = await opened(fake);
    await companion.loadCheckins();
    expect(await companion.dismissCheckin(CMT)).toBe(false);
    expect(companion.getCheckin().item).toEqual(ITEM);
    const gone = checkinCore({ due: () => ok({ items: [ITEM] }), dismiss: () => refused(404, "not_found") });
    const { companion: other } = await opened(gone);
    await other.loadCheckins();
    await other.dismissCheckin(CMT);
    expect(other.getCheckin().item).toBeNull();
  });

  test("open goes through the check-in's route and shows the thread with the check-in as its opener", async () => {
    const fake = checkinCore({ due: () => ok({ items: [ITEM] }), open: () => ok(OPENED), companion: () => ok({ ...OPENED, opener: { ...OPENED.opener, facts: { ...OPENED.opener.facts, checkin_id: null } } }) });
    const { companion } = await opened(fake);
    await companion.loadCheckins();
    await companion.openCheckin(CMT);
    expect(fake.calls.filter((c) => c.method === "POST").map((c) => [c.path, c.body])).toEqual([[`/v1/checkins/${CMT}/open`, null]]);
    expect(companion.getThread()).toMatchObject({ status: "ready", session_id: OPENED.session_id, opener: { facts: { checkin_id: CMT } } });
    expect(companion.getCheckin().item).toBeNull();
    // An open while the check-in's is running shares it: the check-in's opener is the one shown.
    const again = checkinCore({ open: () => ok(OPENED), companion: () => ok(OPENED) });
    const { companion: other } = await opened(again);
    await Promise.all([other.openCheckin(CMT), other.open()]);
    expect(again.calls.filter((c) => c.method === "POST")).toHaveLength(1);
    expect(other.getThread().opener?.facts.checkin_id).toBe(CMT);
    companion.close();
    other.close();
  });

  test("a lock or profile switch drops the card and cancels what was shown; a late reply is dropped", async () => {
    const note = notifier();
    let release: (r: Response) => void = () => undefined;
    let slow = false;
    const fake = checkinCore({ due: () => (slow ? (new Promise<Response>((r) => { release = r; }) as unknown as Response) : ok({ items: [ITEM] })) });
    const { profiles, companion } = await opened(fake, note.value);
    fake.core.settings.get(PROFILES[0]!.profile_id)!.checkin_notifications = true;
    await profiles.loadSettings();
    await companion.loadCheckins();
    expect(note.shown).toHaveLength(1);
    await profiles.unlock(PROFILES[1]!.profile_id);
    expect(companion.getCheckin()).toEqual(EMPTY_CHECKIN);
    expect(note.cancelled()).toBe(1);
    // A reply that lands after the switch is not shown for the next profile.
    slow = true;
    await profiles.unlock(PROFILES[0]!.profile_id);
    const late = companion.loadCheckins();
    await profiles.unlock(PROFILES[1]!.profile_id);
    release(ok({ items: [ITEM] }));
    await late;
    expect(companion.getCheckin().item).toBeNull();
  });
});

describe("SPEC §19.5.5 desktop notifications (JM-D24)", () => {
  test("only with checkin_notifications on and the permission granted; only the id and kind cross; once per check-in", async () => {
    const note = notifier();
    const fake = checkinCore({ due: () => ok({ items: [ITEM] }) });
    const { profiles, companion } = await opened(fake, note.value);
    await profiles.loadSettings();
    await companion.loadCheckins();
    expect(note.shown).toEqual([]); // the setting defaults to off
    fake.core.settings.get(PROFILES[0]!.profile_id)!.checkin_notifications = true;
    await profiles.loadSettings();
    await companion.loadCheckins();
    expect(note.shown).toEqual([{ commitment_id: CMT, kind: "event_checkin" }]);
    expect(JSON.stringify(note.shown)).not.toContain("mock paper");
    await companion.loadCheckins(); // the 30-minute refresh shows the same check-in: no second notification
    expect(note.shown).toHaveLength(1);
  });

  test("a refused permission turns the setting off and says so on the card", async () => {
    const note = notifier("denied");
    const fake = checkinCore({ due: () => ok({ items: [ITEM] }) });
    const { profiles, companion } = await opened(fake, note.value);
    fake.core.settings.get(PROFILES[0]!.profile_id)!.checkin_notifications = true;
    await profiles.loadSettings();
    await companion.loadCheckins();
    expect(note.shown).toEqual([]);
    expect(fake.core.settings.get(PROFILES[0]!.profile_id)!.checkin_notifications).toBe(false);
    expect(profiles.getView().settings?.checkin_notifications).toBe(false);
    expect(companion.getCheckin()).toMatchObject({ item: ITEM, notice: "notifications_denied" });
  });

  test("every kind has a template key; the commitment's text is never one", () => {
    expect(Object.keys(CHECKIN_NOTIFICATION_KEYS)).toEqual([...CHECKIN_KINDS]);
    for (const kind of CHECKIN_KINDS) expect(CHECKIN_NOTIFICATION_KEYS[kind]).toBe(`home.checkin.notify.${kind}`);
  });
});

describe("SPEC §19.3.5, §19.5.6 note lifecycle on the client", () => {
  const note: KnowsNote = {
    note_id: `mem_${"1".repeat(26)}`, text: "Prefers worked examples first.", status: "active", source: "reflector", flagged: false, subject: "physics",
    created_ts: 1, updated_ts: 2,
  };
  const base = { profile_id: `prf_${"1".repeat(26)}`, about: null, kcs: [], misconceptions: [], preferences: [], reviews: [], memory_saving: true, sharing: null };

  test("an older core's note reads as tentative, not fading, never recalled, not withheld", () => {
    expect(noteLifecycle(note)).toEqual({ confidence: "tentative", fading: false, recall_sessions: 0, withheld_online: false });
    expect(knowsReplyProblems({ ...base, notes: [note] })).toEqual([]);
  });

  test("the derived fields are read and checked at the boundary", () => {
    const derived = { ...note, confidence: "supported" as const, fading: true, recall_sessions: 3, withheld_online: true };
    expect(noteLifecycle(readKnows({ ...base, notes: [derived] }).notes[0]!)).toEqual({ confidence: "supported", fading: true, recall_sessions: 3, withheld_online: true });
    for (const bad of [{ confidence: "certain" }, { fading: "yes" }, { recall_sessions: -1 }, { recall_sessions: 1.5 }, { withheld_online: 1 }]) {
      expect(knowsReplyProblems({ ...base, notes: [{ ...note, ...bad }] })).toEqual(["notes"]);
    }
    expect(errors("api/commands#/$defs/KnowsNote", derived)).toEqual([]);
  });
});

describe("SPEC §19.6 Personal tutor memory online", () => {
  test("the feature follows crash reports, is a consent feature and carries the core's notice version", () => {
    expect(ONLINE_FEATURES.at(-1)).toBe("tutor_memory_online");
    expect(CONSENT_FEATURES.has("tutor_memory_online")).toBe(true);
    expect(CONSENT_NOTICE_VERSIONS.tutor_memory_online).toBe("2026-10.d1");
    expect(errors("api/events#/$defs/online_feature", "tutor_memory_online")).toEqual([]);
  });
});
