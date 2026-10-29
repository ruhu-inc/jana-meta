// SPEC §19.9 `checkin-card.test.tsx` (W8 phase 3, §19.5.5): the check-in card on Home. It shows when the due query
// names a check-in, with the commitment's words as plain text; "Answer in Study" opens **Your tutor** through the
// check-in's own route, with the check-in as the opener; "Not now" dismisses it; an older core (404) shows nothing; a
// profile switch drops it. A desktop notification is sent only with Check-in notifications on and the computer's
// permission granted, carries only the check-in's id and kind (its body is the kind's fixed template), and a refused
// permission keeps the setting off with a notice.
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { useSyncExternalStore } from "react";
import { afterEach, describe, expect, test } from "vitest";
import {
  CHECKIN_KINDS, CHECKIN_NOTIFICATION_KEYS, CompanionController, ProfileController, StoreHolder, type CheckinNotifier, type CheckinView, type Commitment,
  type CompanionOpened,
} from "@jana/client-core";
import { BASE } from "@jana/i18n";
import { FakeProfileCore, PROFILES } from "../../client-core/test/profilecore.js";
import { CheckinCard } from "../src/home/CheckinCard.js";
import { Home } from "../src/home/Home.js";
import { LocaleProvider } from "../src/i18n.js";
import { CompanionThread } from "../src/learn/CompanionThread.js";
import { Settings } from "../src/settings/Settings.js";

afterEach(() => cleanup());

const CMT = `cmt_${"0".repeat(25)}A`;
const TEXT = "How did Saturday's <b>mock paper</b> go?";
const ITEM: Commitment = {
  commitment_id: CMT, kind: "event_checkin", subject: "physics", kc_id: null, text: TEXT,
  due_from: "2026-10-18T07:00:00+01:00", due_until: "2026-10-21T07:00:00+01:00", dedupe_key: "event_checkin:physics:2026-10-17", confidence: 0.8,
  state: "pending", source: "extractor", source_session_id: null, created_at: "2026-10-15T18:00:00+01:00", shown_at: null, resolved_at: null,
};
const OPENED: CompanionOpened = {
  session_id: PROFILES[0]!.session_id, thread_id: `cth_${"6".repeat(26)}`, resumed: false,
  summary: { version: 1, cursor_seq: 0, updated_at: null, topics: [], misconceptions: [], next_step: null, episodes: 1 },
  opener: { opener_id: "2026-10-18", text: "How did Saturday's mock paper go?", facts: {
    last_session_date: "2026-10-16", last_session_mode: "guided", last_subject: "physics", next_step: null, learner_cards_due: 0,
    study_cards_due: 0, exam_distance_days: null, pack_ready: false, checkin_id: CMT,
  } },
};
const ok = (body: unknown) => new Response(JSON.stringify(body), { status: 200, headers: { "content-type": "application/json" } });
const notFound = () => new Response(JSON.stringify({ error: { code: "not_found", message: "", retryable: false, action_taken: false, request_id: "req_x" } }), { status: 404 });

/** The fake core with the check-in routes in front: `due` answers the due query (a 404 is an older core). */
function core(due: () => Response = () => ok({ items: [ITEM] })) {
  const fake = new FakeProfileCore();
  const posts: string[] = [];
  const fetcher = (async (input, init = {}) => {
    const path = new URL(String(input)).pathname;
    if (path === "/v1/checkins/due") return due();
    if (path.startsWith("/v1/checkins/") || path === "/v1/companion") {
      posts.push(path);
      if (path === `/v1/checkins/${CMT}/open`) return ok(OPENED);
      if (path === `/v1/checkins/${CMT}/dismiss`) return ok({ ...ITEM, state: "dismissed" });
      return notFound();
    }
    return fake.fetch(input, init);
  }) as typeof fetch;
  return { fake, fetch: fetcher, posts };
}

function notifier(permission: "granted" | "denied" = "granted") {
  const shown: { commitment_id: string; kind: string }[] = [];
  const asked: string[] = [];
  let cancelled = 0;
  const value: CheckinNotifier = {
    permission: async () => { asked.push("permission"); return permission; },
    notify: async (checkin) => { shown.push(checkin); },
    cancel: async () => { cancelled += 1; },
  };
  return { value, shown, asked, cancelled: () => cancelled };
}

async function unlocked(c: ReturnType<typeof core>, notify?: CheckinNotifier) {
  const profiles = new ProfileController(c.fake.launch, new StoreHolder(), { fetch: c.fetch });
  await profiles.load();
  await profiles.unlock(PROFILES[0]!.profile_id);
  const companion = new CompanionController(profiles, { fetch: c.fetch, ...(notify === undefined ? {} : { notifier: notify }) });
  return { profiles, companion };
}

/** Home with the card as the app wires it, and the thread it opens into (Study's **Your tutor**). */
function HomeWithCheckin({ companion }: { companion: CompanionController }) {
  const view = useSyncExternalStore(companion.subscribe, companion.getCheckin, companion.getCheckin);
  const thread = useSyncExternalStore(companion.subscribe, companion.getThread, companion.getThread);
  return <>
    <Home name="Ada" ask={null} subjects={[]} onSubject={() => undefined} pickup={[]} onPickup={() => undefined}
      practice={{ ideas: [], refreshes: 0, subjectLabel: (s) => s }} onPractice={() => undefined}
      countdown={<section data-exam-countdown="" />} lastTime={<section data-last-time="" />}
      checkin={<CheckinCard view={view} onOpen={(id) => void companion.openCheckin(id)} onDismiss={(id) => void companion.dismissCheckin(id)} />} />
    {thread.session_id !== null && <CompanionThread companion={companion} onAction={() => undefined} />}
  </>;
}

const shown = (node: React.ReactElement) => render(<LocaleProvider locale="en">{node}</LocaleProvider>);

describe("W8 check-in card", () => {
  test("shown when a check-in is due, between the countdown and the Last time card, with its words as plain text", async () => {
    const c = core();
    const { companion } = await unlocked(c);
    const { container } = shown(<HomeWithCheckin companion={companion} />);
    expect(container.querySelector("[data-checkin]")).toBeNull();
    await act(() => companion.loadCheckins());
    const card = container.querySelector("[data-checkin]") as HTMLElement;
    expect(card.getAttribute("data-checkin")).toBe(CMT);
    expect(within(card).getByRole("heading", { name: "A check-in from your tutor" })).toBeDefined();
    expect(card.querySelector("[data-checkin-text]")?.textContent).toBe(TEXT);
    expect(card.querySelector("b")).toBeNull();
    expect(container.querySelector("[data-exam-countdown]")?.nextElementSibling).toBe(card);
    expect(card.nextElementSibling?.hasAttribute("data-last-time")).toBe(true);
  });

  test("Answer in Study opens the thread through the check-in's route, with the check-in as the opener", async () => {
    const c = core();
    const { companion } = await unlocked(c);
    const { container } = shown(<HomeWithCheckin companion={companion} />);
    await act(() => companion.loadCheckins());
    fireEvent.click(screen.getByRole("button", { name: "Answer in Study" }));
    await waitFor(() => expect(container.querySelector("[data-companion-thread]")?.getAttribute("data-companion-thread")).toBe(OPENED.session_id));
    expect(c.posts).toEqual([`/v1/checkins/${CMT}/open`]);
    expect(companion.getThread().opener?.facts.checkin_id).toBe(CMT);
    const opener = container.querySelector("[data-opener]") as HTMLElement;
    expect(opener.querySelector("[data-companion-text]")?.textContent).toBe(OPENED.opener.text);
    expect(container.querySelector("[data-checkin]")).toBeNull(); // opened: off the card
    companion.close();
  });

  test("Not now dismisses it and it leaves the card", async () => {
    const c = core();
    const { companion } = await unlocked(c);
    const { container } = shown(<HomeWithCheckin companion={companion} />);
    await act(() => companion.loadCheckins());
    fireEvent.click(screen.getByRole("button", { name: "Not now" }));
    await waitFor(() => expect(c.posts).toEqual([`/v1/checkins/${CMT}/dismiss`]));
    expect(container.querySelector("[data-checkin]")).toBeNull();
  });

  test("nothing on an older core (404), nothing when none is due", async () => {
    for (const due of [notFound, () => ok({ items: [] })]) {
      const { companion } = await unlocked(core(due));
      const { container } = shown(<HomeWithCheckin companion={companion} />);
      await act(() => companion.loadCheckins());
      expect(container.querySelector("[data-checkin]")).toBeNull();
      cleanup();
    }
    for (const view of [{ status: "idle", item: null, notice: null }, { status: "unavailable", item: null, notice: null }] as CheckinView[]) {
      const { container } = shown(<CheckinCard view={view} onOpen={() => undefined} onDismiss={() => undefined} />);
      expect(container.innerHTML).toBe("");
      cleanup();
    }
  });

  test("a profile switch drops it and cancels the notifications shown", async () => {
    const c = core();
    const note = notifier();
    const { profiles, companion } = await unlocked(c, note.value);
    c.fake.settings.get(PROFILES[0]!.profile_id)!.checkin_notifications = true;
    await profiles.loadSettings();
    const { container } = shown(<HomeWithCheckin companion={companion} />);
    await act(() => companion.loadCheckins());
    expect(container.querySelector("[data-checkin]")).not.toBeNull();
    await act(() => profiles.unlock(PROFILES[1]!.profile_id));
    expect(container.querySelector("[data-checkin]")).toBeNull();
    expect(note.cancelled()).toBe(1);
  });
});

describe("W8 check-in notifications (JM-D24)", () => {
  test("only with the setting on and the permission granted, with the kind's template body, never the check-in's words", async () => {
    const c = core();
    const off = notifier();
    const { profiles, companion } = await unlocked(c, off.value);
    await profiles.loadSettings();
    await companion.loadCheckins();
    expect(off.shown).toEqual([]); // off by default
    c.fake.settings.get(PROFILES[0]!.profile_id)!.checkin_notifications = true;
    await profiles.loadSettings();
    await companion.loadCheckins();
    expect(off.shown).toEqual([{ commitment_id: CMT, kind: "event_checkin" }]);
    // The body the shell shows is the kind's fixed template (the shell's own test holds it to these words).
    for (const kind of CHECKIN_KINDS) {
      const body = BASE[CHECKIN_NOTIFICATION_KEYS[kind]]!;
      expect(body.length).toBeGreaterThan(0);
      expect(body).not.toContain("{");
      expect(body).not.toContain("mock paper");
    }

    const denied = notifier("denied");
    const second = core();
    const { profiles: other, companion: refused } = await unlocked(second, denied.value);
    second.fake.settings.get(PROFILES[0]!.profile_id)!.checkin_notifications = true;
    await other.loadSettings();
    const { container } = shown(<HomeWithCheckin companion={refused} />);
    await act(() => refused.loadCheckins());
    expect(denied.shown).toEqual([]);
    expect(second.fake.settings.get(PROFILES[0]!.profile_id)!.checkin_notifications).toBe(false);
    expect(container.querySelector("[data-checkin]")?.textContent).toContain("Notifications are blocked on this computer");
  });

  test("Settings: the switch sits under Personal tutor memory online; turning it on asks for permission, and a refusal leaves it off", async () => {
    for (const permission of ["granted", "denied"] as const) {
      const c = core();
      c.fake.features.tutor_memory_online = false;
      c.fake.settings.get(PROFILES[0]!.profile_id)!.checkin_notifications = false;
      const note = notifier(permission);
      const { profiles } = await unlocked(c);
      shown(<Settings profiles={profiles} notifier={note.value} />);
      const row = await waitFor(() => {
        const found = document.querySelector<HTMLElement>('[data-online-feature="tutor_memory_online"]');
        if (found === null || found.querySelector("[data-checkin-notifications]") === null) throw new Error("not yet");
        return found;
      });
      // The online tutor is off, so Personal tutor memory online cannot be turned on yet, and says why.
      expect((within(row).getByRole("checkbox", { name: "Personal tutor memory online" }) as HTMLInputElement).disabled).toBe(true);
      expect(row.querySelector("[data-needs-cloud]")?.textContent).toBe("This works with the online tutor. Turn on the online tutor first.");
      expect(row.textContent).toContain("What leaves this computer: your tutor's short notes about how you learn, and one-line records of what you practised, so the online tutor can remember you. Never your documents, your conversations, your name or your exam dates. Meta does not store these requests or train on them.");
      const toggle = within(row).getByRole("checkbox", { name: "Check-in notifications" }) as HTMLInputElement;
      expect(toggle.checked).toBe(false);
      fireEvent.click(toggle);
      await waitFor(() => expect(note.asked).toEqual(["permission"]));
      if (permission === "granted") {
        await waitFor(() => expect(c.fake.settings.get(PROFILES[0]!.profile_id)!.checkin_notifications).toBe(true));
      } else {
        await waitFor(() => expect(within(row).getByText(/Notifications are blocked on this computer/)).toBeDefined());
        expect(c.fake.settings.get(PROFILES[0]!.profile_id)!.checkin_notifications).toBe(false);
      }
      cleanup();
    }
  });
});
