// The Last time card (SPEC §19.5.2, W8 phase 1), on Home beside the exam countdown and in Study's library: the
// sentence the core made from facts it chose by code (the last session's day, mode and subject, cards due, the nearest
// exam, a research pack ready). The card shows that sentence as text and adds no number of its own; a card the core
// cannot give (an older core, a failed read, nothing loaded yet) is simply not shown.
import type { CompanionView } from "@jana/client-core";
import { useT } from "../i18n.js";
import { Icon } from "../icons.js";
import { Button } from "../primitives/index.js";

export function LastTimeCard({ view, onOpenStudy }: { view: CompanionView; onOpenStudy?: () => void }) {
  const t = useT();
  const opener = view.status === "ready" ? view.opener : null;
  if (opener === null) return null;
  const facts = opener.facts;
  return (
    <section aria-labelledby="last-time-title" data-last-time={opener.opener_id} data-last-mode={facts.last_session_mode ?? ""}
      className="flex flex-col gap-2 rounded-card border border-line bg-canvas px-5 py-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="last-time-title" className="flex items-center gap-2 text-ui font-medium text-ink"><Icon name="timer" size={16} />{t("home.last_time.title")}</h2>
        {onOpenStudy !== undefined && <Button size="sm" tone="ghost" onClick={onOpenStudy}>{t("home.last_time.open_study")}</Button>}
      </div>
      <p data-last-time-text="" className="text-body text-ink">{opener.text}</p>
    </section>
  );
}
