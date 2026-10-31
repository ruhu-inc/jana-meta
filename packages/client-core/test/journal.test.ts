import { expect, test, vi } from "vitest";
import { SessionController, StoreHolder } from "../src/session.js";
import { FakeCore } from "./fakecore.js";
import { recordings } from "./recordings.js";
import { hydrate } from "../src/hydrate.js";
import { journalSnapshot } from "../src/journal.js";
import { optimistic } from "../src/reducer.js";
import { emptyStore } from "../src/store.js";
import { clientId } from "../src/ids.js";

const recording = recordings().find((r) => r.name === "s1_guided_solve")!;

test("a failed command offers retry even when the event stream stays connected", async () => {
  const core = new FakeCore(recording);
  let fail = true;
  const holder = new StoreHolder();
  const session = new SessionController({ endpoint: async () => ({ baseUrl: "http://core.test", token: core.token }) }, holder, recording.session_id, { fetch: async (url, init) => {
    if (String(url).endsWith("/turns") && fail) throw new TypeError("command connection failed");
    return core.fetch(url, init);
  } });
  try {
    await session.open();
    await vi.waitFor(() => expect(holder.getState().connection[`session:${recording.session_id}`]?.state).toBe("live"));
    const key = session.send([{ type: "text", text: "What did we agree to continue?" }], "ask");
    await vi.waitFor(() => expect(holder.getState().messages[key]?.state).toBe("failed"));
    fail = false; session.retry(key);
    await vi.waitFor(() => expect(core.turnKeys.has(key)).toBe(true));
    expect(core.turnStarts).toBe(1);
  } finally { session.close(); core.stop(); }
});

test.each([false, true])("a companion send interrupted by restart reconciles acceptance (%s) before offering retry", async (accepted) => {
  const core = new FakeCore(recording);
  const fresh = { ...core.snapshot(), session: { ...core.snapshot().session, mode: "study_companion" as const } };
  const key = clientId();
  const content = [{ type: "text" as const, text: "Remember that I prefer diagrams." }];
  const cached = { snapshot: journalSnapshot(optimistic(hydrate(emptyStore(), fresh), recording.session_id, key, content), recording.session_id), envelopes: [] };
  if (accepted) fresh.messages.push({ role: "student", message_id: clientId(), client_message_id: key, turn_id: null, content, ts: Date.now() });
  let release!: () => void;
  const gate = new Promise<void>((resolve) => { release = resolve; });
  const sent: { key: string | undefined; body: unknown }[] = [];
  const holder = new StoreHolder();
  const session = new SessionController({ endpoint: async () => ({ baseUrl: "http://core.test", token: core.token }) }, holder, recording.session_id, { fetch: async (url, init) => {
    const path = String(url);
    if (path.endsWith("/journal")) return Response.json(cached);
    if (path.endsWith("/snapshot")) { await gate; return Response.json(fresh); }
    if (path.endsWith("/turns")) {
      sent.push({ key: (init?.headers as Record<string, string>)["idempotency-key"], body: JSON.parse(String(init?.body)) });
      return Response.json({}, { status: 202 });
    }
    return core.fetch(url, init);
  } });
  try {
    const opening = session.open();
    await vi.waitFor(() => expect(holder.getState().messages[key]?.content).toEqual(content));
    release(); await opening;
    expect(holder.getState().messages[key]?.state).toBe(accepted ? "accepted" : "failed");
    expect(sent).toEqual([]);
    session.retry(key);
    if (accepted) { expect(sent).toEqual([]); return; }
    await vi.waitFor(() => expect(sent).toHaveLength(1));
    expect(sent[0]).toEqual({ key, body: { client_message_id: key, intent: "ask", content } });
  } finally { release(); session.close(); core.stop(); }
});

test("live session commits persist a throttled profile journal without browser storage", async () => {
  const core = new FakeCore(recording, 2); const bodies: { snapshot: unknown; envelopes: unknown[] }[] = [];
  const times: number[] = [];
  const session = new SessionController({ endpoint: async () => ({ baseUrl: "http://core.test", token: core.token }) }, new StoreHolder(), recording.session_id, { fetch: async (url, init) => {
    if (String(url).endsWith("/journal")) {
      if (init?.method === "PUT") { bodies.push(JSON.parse(String(init.body))); times.push(performance.now()); }
      return Response.json(bodies.at(-1) ?? { snapshot: null, envelopes: [] });
    }
    return core.fetch(url, init);
  } });
  try {
    await session.open(); core.start();
    await vi.waitFor(() => expect(core.done).toBe(true), { timeout: 2000 });
    await vi.waitFor(() => expect(bodies.length).toBeGreaterThan(0), { timeout: 1500 });
    expect(JSON.stringify(bodies.at(-1))).toContain("session_id");
    expect(JSON.stringify(bodies)).not.toContain('"connection"');
    for (let i = 1; i < times.length; i++) expect(times[i]! - times[i - 1]!).toBeGreaterThanOrEqual(490);
  } finally { session.close(); core.stop(); }
});

test.each(["snapshot", "closed"])("a late journal cannot overwrite %s state", async (state) => {
  const core = new FakeCore(recording); core.position = Math.floor(recording.frames.length / 2);
  const cache = { snapshot: core.snapshot(), envelopes: [] }; core.position = 0;
  let release!: () => void; const held = new Promise<void>((resolve) => { release = resolve; });
  const holder = new StoreHolder();
  const session = new SessionController({ endpoint: async () => ({ baseUrl: "http://core.test", token: core.token }) }, holder, recording.session_id, { fetch: async (url, init) => {
    if (String(url).endsWith("/journal")) { await held; return Response.json(cache); }
    return core.fetch(url, init);
  } });
  try {
    await session.open(); if (state === "closed") session.close();
    const data = () => { const { connection: _connection, ...rest } = holder.getState(); return JSON.stringify(rest); };
    const before = data(); release();
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(data()).toBe(before);
  } finally { release(); session.close(); core.stop(); }
});
