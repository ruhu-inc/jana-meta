// **Your tutor** in Study (SPEC §19, W8 phase 2): one persistent conversation per profile, on this computer (JM-D27).
// The day's episode opens with the opener the core worded from facts it chose by code, shown once as the thread's first
// bubble; the learner's messages and the tutor's replies follow; under them, the buttons the engine sent from a tool
// result (`companion.action`), each labelled with its own copy key and kept in the store, so a reconnect or a restart
// shows them again. Everything the model wrote is shown as text, never as markup: no Markdown, no HTML, no links.
// The same thread is the library's panel and a tab beside Generate and Chat inside a material.
import { useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import { COMPANION_MESSAGE_MAX, companionActions, companionThread, type CompanionAction, type CompanionController, type CompanionEntry } from "@jana/client-core";
import { useT } from "../i18n.js";
import { Icon } from "../icons.js";
import { Button, ErrorState, IconButton, Loader } from "../primitives/index.js";
import { ComposerShell } from "../primitives/ComposerShell.js";

/** What the thread reads and does: the companion controller, or a stand-in with the same members (the tests). */
export type CompanionThreadSource = Pick<CompanionController, "holder" | "getThread" | "subscribe" | "send" | "retry">;

const ACTION_KEY = "study.companion.action.";
const NO_ENTRIES: CompanionEntry[] = [];
const NO_ACTIONS: CompanionAction[] = [];

/** A button's label: the engine's copy key when it is one of the thread's action keys and the catalogue has it, else
 * the action's own key; never text the model wrote. */
function useActionLabel(): (action: CompanionAction) => string {
  const t = useT();
  return (action) => {
    if (action.label_key.startsWith(ACTION_KEY)) {
      const label = t(action.label_key);
      if (label !== action.label_key) return label;
    }
    const own = `${ACTION_KEY}${action.action}`;
    const label = t(own);
    return label !== own ? label : t(`${ACTION_KEY}unknown`);
  };
}

function failureKey(error: string | null): string {
  if (error === "model_unavailable") return "study.companion.failed_model";
  if (error === "feature_disabled") return "study.companion.failed_off";
  return "study.companion.failed";
}

function TutorBubble({ entry }: { entry: Extract<CompanionEntry, { kind: "tutor" }> }) {
  const t = useT();
  const notices = entry.notices.map((key) => t(key)).filter((line, i) => line !== entry.notices[i]);
  const running = entry.status === "streaming";
  const phase = entry.phase === null || entry.phase === "streaming" ? null : entry.phase;
  const phaseLabel = phase === null ? t("tutor.status.thinking") : t(`tutor.status.${phase}`) === `tutor.status.${phase}` ? t("tutor.status.unknown") : t(`tutor.status.${phase}`);
  return (
    <li data-said="tutor" data-turn-id={entry.turn_id} data-turn-status={entry.status} className="flex max-w-[85%] flex-col gap-1 self-start">
      <span className="text-meta text-faint">{t("study.companion.tutor")}</span>
      {entry.text !== "" && <p data-companion-text="" className="whitespace-pre-wrap break-words rounded-card bg-panel px-3 py-2 text-body text-ink">{entry.text}</p>}
      {notices.map((line, i) => <p key={i} className="whitespace-pre-wrap rounded-card bg-panel px-3 py-2 text-ui text-ink">{line}</p>)}
      {running && entry.text === "" && <span role="status" className="text-meta text-muted">{phaseLabel}</span>}
      {!running && entry.status !== "complete" && entry.text === "" && notices.length === 0 && <span className="text-meta text-muted">{t("study.companion.no_reply")}</span>}
    </li>
  );
}

function StudentBubble({ entry, onRetry }: { entry: Extract<CompanionEntry, { kind: "student" }>; onRetry: () => void }) {
  const t = useT();
  return (
    <li data-said="student" data-message-state={entry.state} className="flex max-w-[85%] flex-col items-end gap-1 self-end">
      <span className="text-meta text-faint">{t("study.companion.you")}</span>
      <p className="whitespace-pre-wrap break-words rounded-card border border-line px-3 py-2 text-body text-ink">{entry.text}</p>
      {entry.state === "sending" && <span className="text-meta text-muted">{t("study.companion.sending")}</span>}
      {entry.state === "failed" && <span className="flex items-center gap-2 text-meta text-muted">{t("study.companion.not_sent")}<Button size="xs" tone="ghost" onClick={onRetry}>{t("action.try_again")}</Button></span>}
    </li>
  );
}

export function CompanionThread({ companion, onAction, place = "panel" }: {
  companion: CompanionThreadSource;
  /** A button was pressed: the app opens the place it names (the tutor, practice, a Study job, …). */
  onAction: (action: CompanionAction) => void;
  /** `panel` above the library's sources, `tab` beside Generate and Chat inside a material. */
  place?: "panel" | "tab";
}) {
  const t = useT();
  const label = useActionLabel();
  const thread = useSyncExternalStore(companion.subscribe, companion.getThread, companion.getThread);
  const store = useSyncExternalStore(companion.holder.subscribe, companion.holder.getState, companion.holder.getState);
  const sessionId = thread.session_id;
  const entries = useMemo(() => (sessionId === null ? NO_ENTRIES : companionThread(store, sessionId)), [store, sessionId]);
  const actions = useMemo(() => (sessionId === null ? NO_ACTIONS : companionActions(store, sessionId)), [store, sessionId]);
  const [draft, setDraft] = useState("");
  const list = useRef<HTMLOListElement>(null);
  const last = entries[entries.length - 1];
  const lastText = last === undefined ? "" : `${last.key}:${last.kind === "tutor" ? `${last.text.length}:${last.status}` : last.state}`;
  useEffect(() => {
    const el = list.current;
    if (el !== null) el.scrollTop = el.scrollHeight;
  }, [entries.length, lastText, actions.length]);
  const ready = thread.status === "ready" && sessionId !== null;
  const send = () => {
    if (companion.send(draft) !== null) setDraft("");
  };
  const heading = place === "tab" ? "companion-title-tab" : "companion-title";
  return (
    <section aria-labelledby={heading} data-companion-thread={sessionId ?? ""} data-companion-place={place}
      className={`flex flex-col gap-3 ${place === "panel" ? "rounded-card border border-line bg-canvas px-5 py-4" : ""}`}>
      <header className="flex flex-col gap-1">
        <h2 id={heading} className="flex items-center gap-2 text-ui font-semibold text-ink"><Icon name="study-area" size={16} />{t("study.companion.title")}</h2>
        <p data-companion-local="" className="text-meta text-muted">{t("study.companion.on_this_computer")}</p>
      </header>
      {(thread.status === "idle" || thread.status === "opening") && thread.opener === null && <Loader label={t("study.companion.opening")} />}
      {thread.status === "unavailable" && <p className="text-ui text-muted">{t("study.companion.unavailable")}</p>}
      {thread.status === "failed" && <ErrorState message={t(failureKey(thread.error))} />}
      {(thread.opener !== null || entries.length > 0) && (
        <ol ref={list} role="log" aria-live="polite" aria-label={t("study.companion.title")} className={`flex flex-col gap-3 overflow-y-auto ${place === "panel" ? "max-h-96" : "max-h-[60vh]"}`}>
          {thread.opener !== null && (
            <li data-said="tutor" data-opener={thread.opener.opener_id} className="flex max-w-[85%] flex-col gap-1 self-start">
              <span className="text-meta text-faint">{t("study.companion.tutor")}</span>
              <p data-companion-text="" className="whitespace-pre-wrap break-words rounded-card bg-panel px-3 py-2 text-body text-ink">{thread.opener.text}</p>
            </li>
          )}
          {entries.map((entry) => entry.kind === "tutor"
            ? <TutorBubble key={entry.key} entry={entry} />
            : <StudentBubble key={entry.key} entry={entry} onRetry={() => companion.retry(entry.key)} />)}
        </ol>
      )}
      {actions.length > 0 && (
        <div role="group" aria-label={t("study.companion.actions")} className="flex flex-wrap gap-2">
          {actions.map((action) => <Button key={action.action_id} size="sm" data-companion-action={action.action} onClick={() => onAction(action)}>{label(action)}</Button>)}
        </div>
      )}
      {thread.status === "ready" && entries.length === 0 && <p className="text-meta text-muted">{t("study.companion.intro")}</p>}
      <form onSubmit={(e) => { e.preventDefault(); send(); }}>
        <ComposerShell send={<IconButton type="submit" tone="action" icon="send" tip="above" label={t("study.companion.send")} disabled={!ready || draft.trim() === ""} />}>
          <label htmlFor={`${heading}-message`} className="sr-only">{t("study.companion.message_label")}</label>
          <textarea id={`${heading}-message`} rows={2} maxLength={COMPANION_MESSAGE_MAX} disabled={!ready} placeholder={t("study.companion.placeholder")} value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); send(); } }}
            className="w-full resize-none bg-transparent px-1 text-body text-ink outline-none placeholder:text-placeholder" />
        </ComposerShell>
      </form>
    </section>
  );
}
