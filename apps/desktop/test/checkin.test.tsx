// SPEC §19.5.5 (W8 phase 3) in the app as it is wired: the check-in card on Home, read when Home opens; "Answer in
// Study" opens Study with **Your tutor** showing the check-in's opener (through `POST /v1/checkins/{id}/open`, never a
// second plain open); a click on the check-in's desktop notification brings the app back to Home. Against the fake core.
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import type { CheckinNotifier, Commitment, CompanionOpened } from "@jana/client-core";
import { FakeProfileCore, PROFILES } from "../../../packages/client-core/test/profilecore.js";
import { App, createRuntime } from "../src/App.js";

const CMT = `cmt_${"0".repeat(25)}A`;
const ITEM: Commitment = {
  commitment_id: CMT, kind: "event_checkin", subject: "physics", kc_id: null, text: "How did Saturday's mock paper go?",
  due_from: "2026-10-18T07:00:00+01:00", due_until: "2026-10-21T07:00:00+01:00", dedupe_key: "event_checkin:physics:2026-10-17", confidence: 0.8,
  state: "pending", source: "extractor", source_session_id: null, created_at: "2026-10-15T18:00:00+01:00", shown_at: null, resolved_at: null,
};
const OPENED: CompanionOpened = {
  session_id: PROFILES[0]!.session_id, thread_id: `cth_${"6".repeat(26)}`, resumed: false,
  summary: { version: 1, cursor_seq: 0, updated_at: null, topics: [], misconceptions: [], next_step: null, episodes: 1 },
  opener: { opener_id: "2026-10-18", text: "You had a mock paper on Saturday. How did it go?", facts: {
    last_session_date: "2026-10-16", last_session_mode: "guided", last_subject: "physics", next_step: null, learner_cards_due: 0,
    study_cards_due: 0, exam_distance_days: null, pack_ready: false, checkin_id: CMT,
  } },
};

beforeEach(() => vi.stubGlobal("matchMedia", (query: string) => ({
  matches: true, media: query, onchange: null, addEventListener: () => undefined, removeEventListener: () => undefined,
  addListener: () => undefined, removeListener: () => undefined, dispatchEvent: () => false,
})));
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const pack = (subject: string) => ({ pack_id: `pack.${subject}.o`, subject, level: "O" as const, version: "0.1.0", signature_ok: true, size_bytes: 1 });

/** The fake core with Study on and the check-in routes; `posts` lists the companion and check-in posts. */
function core() {
  const fake = new FakeProfileCore();
  fake.packs.push(pack("phy"));
  const posts: string[] = [];
  const fetch = fake.fetch;
  fake.fetch = async (input, init = {}) => {
    const path = new URL(String(input)).pathname;
    if (path === "/v1/checkins/due") return Response.json({ items: [ITEM] });
    if (path === `/v1/checkins/${CMT}/open`) { posts.push(path); return Response.json(OPENED); }
    if (path === "/v1/companion") { posts.push(path); return Response.json({ ...OPENED, opener: { ...OPENED.opener, text: "Last time you worked on physics.", facts: { ...OPENED.opener.facts, checkin_id: null } } }); }
    const response = await fetch(input, init);
    if (path === "/v1/meta") return Response.json({ ...await response.json(), capabilities: ["study_workspace"] });
    return response;
  };
  return { fake, posts };
}

describe("W8 check-ins in the app", () => {
  test("the Home card opens Study with Your tutor showing the check-in", async () => {
    const { fake, posts } = core();
    render(<App runtime={createRuntime(fake.launch, fake.fetch)} />);
    await screen.findByRole("heading", { name: "Who's learning?" });
    fireEvent.click(screen.getByRole("button", { name: /^Ada/ }));
    const card = await waitFor(() => {
      const found = document.querySelector<HTMLElement>(`[data-checkin="${CMT}"]`);
      if (found === null) throw new Error("no card yet");
      return found;
    });
    expect(card.querySelector("[data-checkin-text]")?.textContent).toBe(ITEM.text);
    fireEvent.click(within(card).getByRole("button", { name: "Answer in Study" }));
    await screen.findByRole("heading", { name: "Study", level: 1 });
    await waitFor(() => expect(document.querySelector("[data-opener] [data-companion-text]")?.textContent).toBe(OPENED.opener.text));
    expect(posts).toEqual([`/v1/checkins/${CMT}/open`]);
  });

  test("a click on the check-in's notification brings the app back to Home", async () => {
    const { fake } = core();
    let clicked: string | null = null;
    const notifier: CheckinNotifier & { takeClick: () => Promise<string | null> } = {
      permission: async () => "granted", notify: async () => undefined, cancel: async () => undefined,
      takeClick: async () => { const id = clicked; clicked = null; return id; },
    };
    render(<App runtime={createRuntime(fake.launch, fake.fetch, notifier)} />);
    await screen.findByRole("heading", { name: "Who's learning?" });
    fireEvent.click(screen.getByRole("button", { name: /^Ada/ }));
    const nav = await screen.findByRole("navigation", { name: "Main" });
    fireEvent.click(await within(nav).findByRole("button", { name: "Progress" }));
    await waitFor(() => expect(document.querySelector("[data-app-screen]")?.getAttribute("data-app-screen")).toBe("progress"));
    // Focus without a click on a notification leaves the screen as it is.
    await act(async () => { window.dispatchEvent(new Event("focus")); await Promise.resolve(); });
    expect(document.querySelector("[data-app-screen]")?.getAttribute("data-app-screen")).toBe("progress");
    clicked = CMT;
    await act(async () => { window.dispatchEvent(new Event("focus")); await Promise.resolve(); });
    await waitFor(() => expect(document.querySelector(`[data-checkin="${CMT}"]`)).not.toBeNull());
  });
});
