// SPEC §19.3.3, §19.8 phase 2 on the client: the thread opens through `POST /v1/companion` (validated, one request for
// concurrent opens, the opener in the view only), its turns go through the session's pieces with intent `ask`, and a
// `companion.action` is folded into the store and read back from a snapshot's `actions`, so a button survives a
// reconnect and a restart. The knows view carries the rolling summary; the recent lists never pick the thread.
import { describe, expect, test } from "vitest";
import { errors, type SessionList } from "@jana/contracts-ts";
import {
  CompanionController, EMPTY_THREAD, companionActions, companionThread, readCompanionOpened, type CompanionOpened, type CompanionSummary,
} from "../src/companion.js";
import { hydrate, type CoreSnapshot } from "../src/hydrate.js";
import { journalSnapshot } from "../src/journal.js";
import { knowsReplyProblems, knowsViewOf, readKnows } from "../src/memory.js";
import { ProfileController } from "../src/profiles.js";
import type { Envelope } from "../src/queue.js";
import { lastWorked, recentSessions } from "../src/recent.js";
import { optimistic, reduce } from "../src/reducer.js";
import { KNOWN_EVENTS, StoreHolder } from "../src/session.js";
import { emptyStore, type Store } from "../src/store.js";
import { readEnvelope } from "../src/tolerant.js";
import { FakeProfileCore, PROFILES } from "./profilecore.js";

const SESSION = `ses_${"7".repeat(26)}`;
const EPOCH = "ep_companion";
const ACTION = `act_${"0".repeat(25)}1`;
const LATER = `act_${"0".repeat(25)}2`;
const SUMMARY: CompanionSummary = { version: 3, cursor_seq: 40, updated_at: "2026-10-29T10:00:00Z", topics: [], misconceptions: [], next_step: null, episodes: 2 };

function snapshot(actions?: CoreSnapshot["actions"]): CoreSnapshot {
  return {
    session: { session_id: SESSION, title: "", mode: "study_companion", subject: "physics", topic_id: null, created_ts: 0, updated_ts: 0, archived: false },
    cursor: { epoch: EPOCH, seq: 0 }, messages: [], parts: {}, boards: {}, visuals: {}, open_requests: [], active_turn: null,
    ...(actions === undefined ? {} : { actions }),
  };
}

let seq = 0;
function envelope(event: Record<string, unknown> & { type: string }, turnId: string | null = null): Envelope {
  seq += 1;
  return { v: 1, channel: "session", seq, epoch: EPOCH, session_id: SESSION, turn_id: turnId, ts: 1000 + seq, event } as Envelope;
}

const makeAid = { type: "companion.action", action_id: ACTION, action: "open_study_job", payload: { job_id: `stj_${"1".repeat(26)}` }, label_key: "study.companion.action.open_study_job" } as const;
const homework = { type: "companion.action", action_id: LATER, action: "open_tutor", payload: { question: "Solve 2x + 3 = 7" }, label_key: "study.companion.action.open_tutor" } as const;

const data = (store: Store) => { const { connection: _c, ...rest } = store; return rest; };

describe("SPEC §19.3.3 companion.action in the store", () => {
  test("the event is in the contract, read by the tolerant reader and known to the session", () => {
    expect(KNOWN_EVENTS.has("companion.action")).toBe(true);
    const read = readEnvelope(envelope(makeAid));
    expect(read.kind).toBe("accept");
    expect(errors("api/events", envelope(homework))).toEqual([]);
  });

  test("the reducer folds a button by its action id, and the same id again replaces it", () => {
    seq = 0;
    let store = hydrate(emptyStore(), snapshot());
    store = reduce(store, envelope(makeAid));
    store = reduce(store, envelope(homework));
    expect(companionActions(store, SESSION).map((a) => [a.action, a.label_key])).toEqual([
      ["open_study_job", "study.companion.action.open_study_job"], ["open_tutor", "study.companion.action.open_tutor"],
    ]);
    expect(store.actions[LATER]?.payload.question).toBe("Solve 2x + 3 = 7");
    const again = reduce(store, envelope({ ...makeAid, payload: { job_id: `stj_${"2".repeat(26)}` } }));
    expect(Object.keys(again.actions)).toHaveLength(2);
    expect(again.actions[ACTION]?.payload.job_id).toBe(`stj_${"2".repeat(26)}`);
    // Replaying what was already folded changes nothing (UIA-02).
    const replayed = { v: 1, channel: "session", seq: 1, epoch: EPOCH, session_id: SESSION, turn_id: null, ts: 1, event: makeAid } as Envelope;
    expect(reduce(again, replayed)).toBe(again);
  });

  test("a snapshot's actions hydrate to the same store a stream folds: the button survives a restart", () => {
    seq = 0;
    const streamed = [makeAid, homework].reduce((s, e) => reduce(s, envelope(e)), hydrate(emptyStore(), snapshot()));
    const restarted = hydrate(emptyStore(), { ...snapshot({ [ACTION]: makeAid, [LATER]: homework }), cursor: { epoch: EPOCH, seq: 2 } });
    expect(data(restarted)).toEqual(data(streamed));
    expect(errors("api/commands#/$defs/Snapshot", { ...snapshot({ [ACTION]: makeAid }), messages: [] })).toEqual([]);
    // A snapshot replaces the session's buttons, and leaves another session's alone.
    const other = { ...makeAid, action_id: `act_${"0".repeat(25)}9` };
    const mixed = { ...restarted, actions: { ...restarted.actions, [other.action_id]: { ...other, session_id: `ses_${"8".repeat(26)}` } } };
    const fresh = hydrate(mixed, snapshot({ [ACTION]: makeAid }));
    expect(Object.keys(fresh.actions).sort()).toEqual([ACTION, other.action_id].sort());
    // The local journal keeps them too (UIA-06), as the snapshot shape.
    expect(journalSnapshot(streamed, SESSION)?.actions).toEqual({ [ACTION]: makeAid, [LATER]: homework });
  });

  test("the thread reads as plain-text bubbles in order, with each reply's text and phase", () => {
    seq = 0;
    const turn = `trn_${"3".repeat(26)}`, part = `prt_${"4".repeat(26)}`;
    let store = hydrate(emptyStore(), snapshot());
    store = optimistic(store, SESSION, "cli_1", [{ type: "text", text: "What is due?" }]);
    store = reduce(store, envelope({ type: "turn.start", turn_id: turn, user_message_id: `msg_${"5".repeat(26)}`, client_message_id: "cli_1", intent: "ask", mode: "study_companion", fork: false }, turn));
    store = reduce(store, envelope({ type: "status", phase: "recalling", label_key: "status.recalling", label_params: {}, phase_started_ts: 1, model_tier: null, progress: null }, turn));
    expect(companionThread(store, SESSION).map((e) => [e.kind, e.kind === "tutor" ? e.phase : e.text])).toEqual([["student", "What is due?"], ["tutor", "recalling"]]);
    store = reduce(store, envelope({ type: "part.start", part_id: part, kind: "text", index: 0 }, turn));
    store = reduce(store, envelope({ type: "text.delta", part_id: part, delta: "<b>12 cards</b> are due." }, turn));
    const [, reply] = companionThread(store, SESSION);
    expect(reply).toMatchObject({ kind: "tutor", text: "<b>12 cards</b> are due.", status: "streaming" });
  });
});

function companionCore(reply: () => Response) {
  const core = new FakeProfileCore();
  const opened: { key: string | undefined }[] = [];
  const fetcher = (async (input, init = {}) => {
    const url = new URL(String(input));
    if (url.pathname === "/v1/companion" && (init.method ?? "GET") === "POST") {
      opened.push({ key: (init.headers as Record<string, string> | undefined)?.["idempotency-key"] });
      await new Promise((r) => setTimeout(r, 5));
      return reply();
    }
    return core.fetch(input, init);
  }) as typeof fetch;
  return { core, fetch: fetcher, opened };
}

const OPENED: CompanionOpened = {
  session_id: PROFILES[0]!.session_id, thread_id: `cth_${"6".repeat(26)}`, resumed: false, summary: SUMMARY,
  opener: { opener_id: "2026-10-29", text: "Last time you worked on physics; 12 cards are due.", facts: {
    last_session_date: "2026-10-28", last_session_mode: "guided", last_subject: "physics", next_step: null, learner_cards_due: 12,
    study_cards_due: 0, exam_distance_days: null, pack_ready: false, checkin_id: null,
  } },
};
const ok = (body: unknown) => new Response(JSON.stringify(body), { status: 200, headers: { "content-type": "application/json" } });

describe("SPEC §19.3.3 the thread's open and its turns", () => {
  test("two opens at once send one request with an idempotency key; the opener and summary are in the view", async () => {
    const fake = companionCore(() => ok(OPENED));
    const profiles = new ProfileController(fake.core.launch, new StoreHolder(), { fetch: fake.fetch });
    await profiles.load(); await profiles.unlock(PROFILES[0]!.profile_id);
    const companion = new CompanionController(profiles, { fetch: fake.fetch });
    expect(companion.send("hello")).toBeNull(); // nothing to send to before the thread opens
    await Promise.all([companion.open(), companion.open()]);
    expect(fake.opened).toHaveLength(1);
    expect(fake.opened[0]!.key).toMatch(/^cli_/);
    expect(companion.getThread()).toMatchObject({ status: "ready", session_id: OPENED.session_id, thread_id: OPENED.thread_id, opener: OPENED.opener, summary: SUMMARY });
    // A message goes to the episode's session as an ordinary turn, intent `ask`.
    const key = companion.send("  What should I do next?  ");
    expect(key).toMatch(/^cli_/);
    await new Promise((r) => setTimeout(r, 20));
    const turn = fake.core.log.find((l) => l.method === "POST" && l.path === `/v1/sessions/${OPENED.session_id}/turns`);
    expect(turn?.body).toMatchObject({ client_message_id: key, intent: "ask", content: [{ type: "text", text: "What should I do next?" }] });
    // Opening again on the same day keeps the stream that runs (the core returns the same session).
    await companion.open();
    expect(fake.opened).toHaveLength(2);
    expect(companion.getThread().session_id).toBe(OPENED.session_id);
    // A profile switch drops the thread (SEC-19).
    await profiles.unlock(PROFILES[1]!.profile_id);
    expect(companion.getThread()).toEqual(EMPTY_THREAD);
    companion.close();
  });

  test("a reply off the contract fails the open; a core without the thread is unavailable; a refusal says why", async () => {
    expect(() => readCompanionOpened({ ...OPENED, opener: { ...OPENED.opener, text: "x".repeat(241) } })).toThrow();
    for (const [reply, status, error] of [
      [() => ok({ ...OPENED, resumed: "yes" }), "failed", "invalid_reply"],
      [() => new Response(JSON.stringify({ error: { code: "not_found", message: "", retryable: false, action_taken: false, request_id: "req_x" } }), { status: 404 }), "unavailable", "not_found"],
      [() => new Response(JSON.stringify({ error: { code: "model_unavailable", message: "", retryable: false, action_taken: false, request_id: "req_x" } }), { status: 409 }), "failed", "model_unavailable"],
    ] as const) {
      const fake = companionCore(reply);
      const profiles = new ProfileController(fake.core.launch, new StoreHolder(), { fetch: fake.fetch });
      await profiles.load(); await profiles.unlock(PROFILES[0]!.profile_id);
      const companion = new CompanionController(profiles, { fetch: fake.fetch });
      await companion.open();
      expect(companion.getThread()).toMatchObject({ status, error, session_id: null });
      expect(companion.send("hi")).toBeNull();
    }
  });
});

describe("SPEC §19.3.3 elsewhere on the client", () => {
  const base = {
    profile_id: `prf_${"1".repeat(26)}`, about: null, kcs: [], misconceptions: [], preferences: [], notes: [], reviews: [], memory_saving: true, sharing: null,
  };
  test("the knows reply accepts the rolling summary and the view carries it", () => {
    expect(knowsReplyProblems({ ...base, companion_summary: SUMMARY })).toEqual([]);
    expect(knowsReplyProblems({ ...base, companion_summary: null })).toEqual([]);
    expect(knowsReplyProblems({ ...base, companion_summary: { ...SUMMARY, what_worked: "free text" } })).toEqual(["companion_summary"]);
    expect(knowsViewOf(readKnows({ ...base, companion_summary: SUMMARY })).companion_summary).toEqual(SUMMARY);
    expect("companion_summary" in knowsViewOf(readKnows(base))).toBe(false);
  });

  test("the recent lists and the tutor's subject never pick the thread's session", () => {
    const listed = [
      { session_id: "ses_a", title: "Projectiles", subject: "physics", topic_id: null, mode: "guided", updated_ts: 10, created_ts: 1, archived: false },
      { session_id: "ses_b", title: "", subject: "physics", topic_id: null, mode: "study_companion", updated_ts: 20, created_ts: 1, archived: false },
    ] as unknown as SessionList["sessions"];
    expect(recentSessions({ sessions: listed, next_before: null } as unknown as SessionList).map((s) => s.session_id)).toEqual(["ses_a"]);
    expect(lastWorked(listed)?.session_id).toBe("ses_a");
  });
});
