// SPEC §19.9 `companion-thread.test.tsx` (W8 phase 2): **Your tutor** in Study. The opener is the first bubble; a
// message sends; a button renders from a `companion.action` event and is still there after a restart hydrates a
// snapshot that carries `actions`; pressing it hands the app the action that names the place to open; and nothing the
// model wrote is ever rendered as markup. The thread is the library's panel and a third tab inside a material, and a
// companion button's request reaches Study (the add panel, research with its topic, a job's material).
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, test, vi } from "vitest";
import {
  EMPTY_PLAN, EMPTY_STUDY, EMPTY_THREAD, StoreHolder, hydrate, emptyStore, optimistic, reduce, type CompanionAction, type CompanionThreadView, type CoreSnapshot,
  type Envelope, type PlanState, type StudyWorkspaceController, type StudyWorkspaceView,
} from "@jana/client-core";
import { CompanionThread, type CompanionThreadSource } from "../src/learn/CompanionThread.js";
import { StudyWorkspace } from "../src/learn/StudyWorkspace.js";
import { PlanCard } from "../src/home/PlanCard.js";
import { LocaleProvider } from "../src/i18n.js";

afterEach(() => cleanup());

const SESSION = `ses_${"C".repeat(26)}`;
const EPOCH = "ep_companion_ui";
const ADD = `act_${"0".repeat(25)}1`;
const HOMEWORK = `act_${"0".repeat(25)}2`;
const OPENED: CompanionThreadView = {
  status: "ready", session_id: SESSION, thread_id: `cth_${"D".repeat(26)}`, resumed: false,
  opener: { opener_id: "2026-10-29", text: "Last time you worked on physics; 12 cards are due.", facts: {
    last_session_date: "2026-10-28", last_session_mode: "guided", last_subject: "physics", next_step: null, learner_cards_due: 12,
    study_cards_due: 0, exam_distance_days: null, pack_ready: false, checkin_id: null,
  } },
  summary: null, error: null, notice: null,
};

function snapshot(actions?: CoreSnapshot["actions"], seq = 0): CoreSnapshot {
  return {
    session: { session_id: SESSION, title: "", mode: "study_companion", subject: "physics", topic_id: null, created_ts: 0, updated_ts: 0, archived: false },
    cursor: { epoch: EPOCH, seq }, messages: [], parts: {}, boards: {}, visuals: {}, open_requests: [], active_turn: null,
    ...(actions === undefined ? {} : { actions }),
  };
}

const addSource = { type: "companion.action", action_id: ADD, action: "open_add_source", payload: {}, label_key: "study.companion.action.open_add_source" } as const;
const homework = { type: "companion.action", action_id: HOMEWORK, action: "open_tutor", payload: { question: "Solve 2x + 3 = 7" }, label_key: "study.companion.action.open_tutor" } as const;

/** The thread's source as the companion controller is: a store the session folds into, the episode, send and retry. */
class FakeCompanion implements CompanionThreadSource {
  readonly holder = new StoreHolder();
  private thread: CompanionThreadView;
  private readonly listeners = new Set<() => void>();
  readonly sent: string[] = [];
  readonly retry = vi.fn();
  readonly loadEarlier = vi.fn(async () => undefined);
  readonly answers: string[] = [];
  /** The open sent again with the answer: here, what the core answers it with. */
  onAnswer: (answer: "accepted" | "declined") => CompanionThreadView = () => OPENED;
  private seq = 0;
  private keys = 0;

  constructor(view: CompanionThreadView = OPENED, start: CoreSnapshot = snapshot()) {
    this.thread = view;
    this.holder.update(() => hydrate(emptyStore(), start));
    this.seq = start.cursor.seq;
  }

  getThread = (): CompanionThreadView => this.thread;
  subscribe = (listener: () => void): (() => void) => { this.listeners.add(listener); return () => this.listeners.delete(listener); };
  setThread(view: CompanionThreadView): void { act(() => { this.thread = view; for (const l of [...this.listeners]) l(); }); }
  answerNotice = async (answer: "accepted" | "declined"): Promise<void> => {
    this.answers.push(answer);
    await Promise.resolve();
    this.setThread(this.onAnswer(answer));
  };

  send = (text: string): string | null => {
    const words = text.trim();
    if (words === "") return null;
    this.keys += 1;
    const key = `cli_${String(this.keys).padStart(26, "0")}`;
    this.sent.push(words);
    this.holder.update((s) => optimistic(s, SESSION, key, [{ type: "text", text: words }]));
    return key;
  };

  emit(event: Record<string, unknown> & { type: string }, turnId: string | null = null): void {
    this.seq += 1;
    const envelope = { v: 1, channel: "session", seq: this.seq, epoch: EPOCH, session_id: SESSION, turn_id: turnId, ts: 1000 + this.seq, event } as Envelope;
    act(() => this.holder.update((s) => reduce(s, envelope)));
  }

  /** A whole tutor turn answering the message sent as `key`, with this text. */
  reply(key: string, text: string): void {
    const turn = `trn_${String(this.seq + 1).padStart(26, "0")}`, part = `prt_${String(this.seq + 1).padStart(26, "0")}`;
    const message = `msg_${String(this.seq + 1).padStart(26, "0")}`;
    this.emit({ type: "turn.start", turn_id: turn, user_message_id: message, client_message_id: key, intent: "ask", mode: "study_companion", fork: false }, turn);
    this.emit({ type: "message.accepted", client_message_id: key, message_id: message, turn_id: turn, disposition: "turn" }, turn);
    this.emit({ type: "part.start", part_id: part, kind: "text", index: 0 }, turn);
    this.emit({ type: "text.delta", part_id: part, delta: text }, turn);
    this.emit({ type: "part.end", part_id: part, status: "complete", duration_ms: 1 }, turn);
  }
}

const shown = (companion: CompanionThreadSource, onAction: (a: CompanionAction) => void = () => undefined) =>
  render(<LocaleProvider locale="en"><CompanionThread companion={companion} onAction={onAction} /></LocaleProvider>);

const bubbles = (container: HTMLElement) => [...container.querySelectorAll("[data-said]")] as HTMLElement[];

describe("W8 Your tutor", () => {
  test("the opener is the thread's first bubble, under the title and the on-this-computer line", () => {
    const { container } = shown(new FakeCompanion());
    expect(screen.getByRole("heading", { name: "Your tutor" })).toBeDefined();
    expect(container.querySelector("[data-companion-local]")?.textContent).toBe("This conversation stays on this computer.");
    const [first] = bubbles(container);
    expect(first?.getAttribute("data-opener")).toBe("2026-10-29");
    expect(first?.getAttribute("data-said")).toBe("tutor");
    expect(first?.querySelector("[data-companion-text]")?.textContent).toBe(OPENED.opener?.text);
  });

  test("a message sends, shows at once after the opener, and the reply follows it as text", () => {
    const companion = new FakeCompanion();
    const { container } = shown(companion);
    const box = screen.getByRole("textbox", { name: "Message to your tutor" }) as HTMLTextAreaElement;
    fireEvent.change(box, { target: { value: "  What is due today?  " } });
    fireEvent.click(screen.getByRole("button", { name: "Send to your tutor" }));
    expect(companion.sent).toEqual(["What is due today?"]);
    expect(box.value).toBe("");
    expect(bubbles(container).map((b) => [b.getAttribute("data-said"), b.querySelector("p")?.textContent])).toEqual([
      ["tutor", OPENED.opener?.text], ["student", "What is due today?"],
    ]);
    companion.reply("cli_00000000000000000000000001", "12 cards are due; start with those.");
    expect(bubbles(container).map((b) => b.getAttribute("data-said"))).toEqual(["tutor", "student", "tutor"]);
    expect(bubbles(container)[2]?.textContent).toContain("12 cards are due; start with those.");
    // Enter sends too; an empty message is never sent.
    fireEvent.change(box, { target: { value: "Thanks" } });
    fireEvent.keyDown(box, { key: "Enter" });
    expect(companion.sent).toEqual(["What is due today?", "Thanks"]);
    expect((screen.getByRole("button", { name: "Send to your tutor" }) as HTMLButtonElement).disabled).toBe(true);
  });

  test("a button renders from companion.action with its label key, and survives a restart that hydrates `actions`", () => {
    const companion = new FakeCompanion();
    const onAction = vi.fn();
    shown(companion, onAction);
    expect(screen.queryByRole("group", { name: "Suggested next steps" })).toBeNull();
    companion.emit(addSource);
    companion.emit(homework);
    const group = screen.getByRole("group", { name: "Suggested next steps" });
    expect(within(group).getAllByRole("button").map((b) => b.textContent)).toEqual(["Add it to Study", "Work on it with the tutor"]);
    cleanup();

    // A restart: a fresh store from the core's snapshot, which carries the same buttons.
    const restarted = new FakeCompanion(OPENED, snapshot({ [ADD]: addSource, [HOMEWORK]: homework }, 2));
    shown(restarted, onAction);
    const again = screen.getByRole("group", { name: "Suggested next steps" });
    expect(within(again).getAllByRole("button").map((b) => b.textContent)).toEqual(["Add it to Study", "Work on it with the tutor"]);
    // It opens the right place: the app is handed the action, with the question for the tutor.
    fireEvent.click(within(again).getByRole("button", { name: "Work on it with the tutor" }));
    expect(onAction).toHaveBeenCalledWith(expect.objectContaining({ action: "open_tutor", payload: { question: "Solve 2x + 3 = 7" } }));
    fireEvent.click(within(again).getByRole("button", { name: "Add it to Study" }));
    expect(onAction).toHaveBeenLastCalledWith(expect.objectContaining({ action: "open_add_source" }));
  });

  test("text is never rendered as markup: the opener, the reply and a label key from outside the thread's keys", () => {
    const markup = "<b>bold</b> <img src=x onerror=alert(1)> **stars** [link](https://example.com)";
    const companion = new FakeCompanion({ ...OPENED, opener: { ...OPENED.opener!, text: markup } });
    const { container } = shown(companion);
    companion.reply(companion.send("hi")!, markup);
    companion.emit({ ...addSource, action_id: `act_${"0".repeat(25)}3`, label_key: "<i>pwned</i>" });
    expect(container.querySelector("b, i, img, a, strong, em")).toBeNull();
    const texts = [...container.querySelectorAll("[data-companion-text]")].map((p) => p.textContent);
    expect(texts).toEqual([markup, markup]);
    // A label key the thread does not own falls back to the action's own label.
    expect(screen.getByRole("button", { name: "Add it to Study" })).toBeDefined();
  });

  test("while it opens, a core without it, and a refusal each say so; the composer waits for the thread", () => {
    const companion = new FakeCompanion({ ...EMPTY_THREAD, status: "opening" });
    shown(companion);
    expect(screen.getByText("Opening your tutor…")).toBeDefined();
    expect((screen.getByRole("textbox", { name: "Message to your tutor" }) as HTMLTextAreaElement).disabled).toBe(true);
    companion.setThread({ ...EMPTY_THREAD, status: "failed", error: "model_unavailable" });
    expect(screen.getByRole("alert").textContent).toContain("needs a tutor model or the online tutor");
    companion.setThread({ ...EMPTY_THREAD, status: "unavailable", error: "not_found" });
    expect(screen.getByText("Your tutor is not available on this computer yet.")).toBeDefined();
  });

  test("the online tutor's first-use notice is asked in the thread, and the learner's answer is sent with the open", async () => {
    const companion = new FakeCompanion({ ...EMPTY_THREAD, status: "notice", notice: "notice_required" });
    const { container } = shown(companion);
    const notice = screen.getByRole("group", { name: "Talk with the online tutor?" });
    expect(notice.textContent).toContain("Your messages in this conversation will be sent to the online tutor so it can answer. Your name is not sent.");
    expect(container.querySelector("[role=alert]")).toBeNull(); // a question, not a failure
    expect((screen.getByRole("textbox", { name: "Message to your tutor" }) as HTMLTextAreaElement).disabled).toBe(true);
    await act(async () => { fireEvent.click(within(notice).getByRole("button", { name: "OK" })); });
    expect(companion.answers).toEqual(["accepted"]);
    expect(screen.queryByRole("group", { name: "Talk with the online tutor?" })).toBeNull();
    expect((screen.getByRole("textbox", { name: "Message to your tutor" }) as HTMLTextAreaElement).disabled).toBe(false);
  });

  test("keeping it on this computer is sent too; where no tutor can run here, the notice says why and offers OK only", async () => {
    const companion = new FakeCompanion({ ...EMPTY_THREAD, status: "notice", notice: "notice_required" });
    companion.onAnswer = () => ({ ...EMPTY_THREAD, status: "notice", notice: "notice_declined" });
    shown(companion);
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Keep it on this computer" })); });
    expect(companion.answers).toEqual(["declined"]);
    const notice = screen.getByRole("group", { name: "Talk with the online tutor?" });
    expect(notice.textContent).toContain("There is no tutor model on this computer, so your tutor can only answer with the online tutor.");
    expect(within(notice).queryByRole("button", { name: "Keep it on this computer" })).toBeNull();
    expect(within(notice).getByRole("button", { name: "OK" })).toBeDefined();
  });

  test("a reply that is still being worked on shows its phase, `recalling` included", () => {
    const companion = new FakeCompanion();
    shown(companion);
    const key = companion.send("What did we do last time?")!;
    const turn = `trn_${"9".repeat(26)}`;
    companion.emit({ type: "turn.start", turn_id: turn, user_message_id: `msg_${"9".repeat(26)}`, client_message_id: key, intent: "ask", mode: "study_companion", fork: false }, turn);
    companion.emit({ type: "status", phase: "recalling", label_key: "status.recalling", label_params: {}, phase_started_ts: 1, model_tier: null, progress: null }, turn);
    expect(screen.getByText("Remembering what we did")).toBeDefined();
  });
});

describe("W8 Your tutor in Study", () => {
  const sid = `src_${"0".repeat(26)}`, now = "2026-10-29T00:00:00Z";
  const source = { source_id: sid, revision: 1, kind: "text", title: "Biology", state: "ready", private: false, created_at: now, updated_at: now, readable_units: 1, unreadable_units: [], sha256: "0".repeat(64) } as const;
  function study(view: Partial<StudyWorkspaceView>, request: Parameters<typeof StudyWorkspace>[0]["request"] = null) {
    let current = { ...EMPTY_STUDY, status: "ready", ...view } as StudyWorkspaceView;
    const listeners = new Set<() => void>();
    const controller = {
      subscribe: (l: () => void) => { listeners.add(l); return () => listeners.delete(l); }, getView: () => current, load: vi.fn(async () => {}), loadTopicMaps: vi.fn(async () => {}),
      close: vi.fn(() => { current = { ...current, source: null }; for (const l of [...listeners]) l(); }), open: vi.fn(), refreshOpened: vi.fn(), openTarget: vi.fn(async () => true),
      researchPacks: vi.fn(async () => []),
    };
    const done = vi.fn();
    const companion = new FakeCompanion();
    const result = render(<LocaleProvider locale="en"><StudyWorkspace controller={controller as unknown as StudyWorkspaceController}
      lastTime={<section data-last-time="" />} companion={(place) => <CompanionThread companion={companion} onAction={() => undefined} place={place} />} request={request} onRequestDone={done} /></LocaleProvider>);
    return { ...result, controller, done };
  }

  test("the library keeps materials and the tutor in separate tabs", () => {
    const { container } = study({ sources: [source] });
    expect(container.querySelector('[data-companion-place="panel"]')).toBeNull();
    expect(screen.getAllByRole("button", { name: /Biology/ }).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("tab", { name: "Your tutor" }));
    expect(container.querySelector('[data-companion-place="panel"]')).not.toBeNull();
    expect(screen.queryByRole("button", { name: /Biology/ })).toBeNull();
  });

  test("inside a material the thread is a third tab beside Generate and Chat, and the study ask box steps aside", () => {
    const { container } = study({ source, followCurrent: true });
    const tabs = screen.getAllByRole("tab").map((t) => t.textContent);
    expect(tabs).toEqual(["Generate", "Chat", "Your tutor"]);
    fireEvent.click(screen.getByRole("tab", { name: "Your tutor" }));
    expect(container.querySelector('[data-companion-place="tab"]')).not.toBeNull();
    expect(screen.getByRole("textbox", { name: "Message to your tutor" })).toBeDefined();
    expect(screen.queryByRole("textbox", { name: "Ask about this material" })).toBeNull();
  });

  test("a companion button's request reaches Study: a job's material, the add panel, research with its topic filled in", async () => {
    const job = `stj_${"1".repeat(26)}`;
    const target = study({ sources: [source] }, { kind: "target", job_id: job });
    await waitFor(() => expect(target.controller.openTarget).toHaveBeenCalledWith({ kind: "target", job_id: job }));
    await waitFor(() => expect(target.done).toHaveBeenCalledOnce());
    cleanup();

    const research = study({ source, followCurrent: true }, { kind: "research", topic: "Photosynthesis" });
    await waitFor(() => expect(research.controller.close).toHaveBeenCalled());
    await waitFor(() => expect((screen.getByRole("textbox", { name: "What do you want to learn about?" }) as HTMLInputElement).value).toBe("Photosynthesis"));
    expect(research.done).toHaveBeenCalledOnce();
    cleanup();

    const add = study({ sources: [source] }, { kind: "add" });
    await waitFor(() => expect(add.done).toHaveBeenCalledOnce());
    expect(screen.getByRole("button", { name: "Add material" }).getAttribute("aria-expanded")).toBe("true");
  });
});

describe("W8 the plan's due Study cards", () => {
  test("a warm-up of due Study cards says how many and opens their deck", () => {
    const deck = `dek_${"4".repeat(26)}`;
    const cards = [1, 2, 3].map((n) => ({ deck_id: deck, card_id: `fcd_${String(n).padStart(26, "0")}` }));
    const plan = (next: number): PlanState => ({
      ...EMPTY_PLAN, status: "ready",
      plan: {
        plan_id: `evt_${"5".repeat(26)}`, request_id: `req_${"5".repeat(26)}`, date: "2026-10-29", phase: "normal", status: "started", minutes: 25, next_block: next,
        alternatives: [], keep_learning: false, decided_ts: null,
        blocks: [
          { index: 0, kind: "warmup", kc_ids: [], minutes: 5, status: next > 0 ? "done" : "pending", done: 0, target: 3, reason_code: "due_reviews_study", study_cards: cards },
          { index: 1, kind: "main", kc_ids: ["kc.phy.o.motion.solve_with_equation"], minutes: 20, status: "pending", done: 0, target: 1 },
        ],
      } as unknown as PlanState["plan"],
    });
    const onStudyCards = vi.fn(), onContinue = vi.fn();
    const card = (state: PlanState) => <LocaleProvider locale="en"><PlanCard state={state} names={{ topic: () => "Motion", started: () => true }} streak={null}
      actions={{ onStart: vi.fn(), onChange: vi.fn(), onNotToday: vi.fn(), onContinue, onKeepLearning: vi.fn(), onAnother: vi.fn(), onRetry: vi.fn(), onStudyCards }} /></LocaleProvider>;
    const { rerender } = render(card(plan(0)));
    expect(screen.getByText("Review 3 Study cards")).toBeDefined();
    expect(screen.getByText("Cards from your own materials are due, so they stick.")).toBeDefined();
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    expect(onContinue).toHaveBeenCalledWith(expect.objectContaining({ study_cards: cards })); // the app opens the deck
    // As a row of its own, the warm-up opens its deck (`open_study_deck`).
    rerender(card(plan(1)));
    fireEvent.click(screen.getByRole("button", { name: "Open the cards" }));
    expect(onStudyCards).toHaveBeenCalledWith(deck);
  });
});

test("restored same-day history remains visible when its runtime snapshot is empty", () => {
  const companion = new FakeCompanion({ ...OPENED, can_reply: false, history: [
    { id: "msg_restored", session_id: SESSION, role: "user", text: "Continue our momentum agreement", created_at: 1 },
  ] });
  shown(companion);
  expect(screen.getByText("Continue our momentum agreement")).toBeDefined();
});

// SPEC §21.9 (W10): "Ask your tutor about this" on the learner's map is a client deep link to the thread with a
// draft (§21.3): the words wait in the composer for the learner, nothing is sent and no action is taken.
describe("W10 the learner's map hands the thread a draft", () => {
  test("the deep link's draft is in the composer, offered once, and nothing is sent", () => {
    const companion = new FakeCompanion();
    const onAction = vi.fn(), onDraftShown = vi.fn();
    const draft = "About Find acceleration from the gradient of a velocity-time graph: ";
    const { container } = render(<LocaleProvider locale="en"><CompanionThread companion={companion} onAction={onAction} draft={draft} onDraftShown={onDraftShown} /></LocaleProvider>);
    const box = screen.getByRole("textbox", { name: "Message to your tutor" }) as HTMLTextAreaElement;
    expect(box.value).toBe(draft);
    expect(box.hasAttribute("data-companion-draft")).toBe(true);
    expect(document.activeElement).toBe(box);
    expect(onDraftShown).toHaveBeenCalledTimes(1);
    expect(companion.sent).toEqual([]);
    expect(onAction).not.toHaveBeenCalled();
    expect(bubbles(container).map((b) => b.getAttribute("data-said"))).toEqual(["tutor"]); // the opener only
    // The learner finishes the question and sends it themselves.
    fireEvent.change(box, { target: { value: `${draft}why the gradient?` } });
    fireEvent.click(screen.getByRole("button", { name: "Send to your tutor" }));
    expect(companion.sent).toEqual([`${draft}why the gradient?`]);
  });
});

describe("W9 moments in Your tutor (SPEC §20.4)", () => {
  const MOMENT = `act_${"0".repeat(25)}3`;
  const openMoment = { type: "companion.action", action_id: MOMENT, action: "open_moment", payload: { source_id: `src_${"5".repeat(26)}`, at_ms: 252000 }, label_key: "study.companion.action.open_moment" } as const;

  test("the open_moment button names the moment the engine resolved and hands the app its source and time", () => {
    const companion = new FakeCompanion();
    const onAction = vi.fn();
    shown(companion, onAction);
    companion.emit(openMoment);
    const button = screen.getByRole("button", { name: "Open the moment, 4:12" });
    expect(button.getAttribute("data-companion-action")).toBe("open_moment");
    fireEvent.click(button);
    expect(onAction).toHaveBeenCalledWith(expect.objectContaining({ action: "open_moment", payload: { source_id: `src_${"5".repeat(26)}`, at_ms: 252000 } }));
  });

  test("a pending moment shows as 'About m:ss in <title>' above the composer until the next message consumes it", () => {
    const companion = new FakeCompanion({ ...OPENED, context: { source_id: `src_${"5".repeat(26)}`, at_ms: 252000, title: "Projectile motion" } });
    const { container } = shown(companion);
    const line = container.querySelector("[data-companion-context]") as HTMLElement;
    expect(line.textContent).toBe("About 4:12 in Projectile motion");
    expect(companion.sent).toEqual([]); // opening with a moment sends nothing
    companion.setThread({ ...companion.getThread(), context: null }); // the controller clears it when the message goes
    expect(container.querySelector("[data-companion-context]")).toBeNull();
  });
});
