// The concept map view of Learn (UXS-22 map view): one subject's curated skills as a layered map, foundations on
// the left, each skill right of what it builds on (the renderer's layout), with the learner's own layer on it: how
// often they asked about a skill, the mistakes diagnosed on it, and the questions that match no skill (open
// questions, taken to the tutor with one tap). Above it, "What next": the skills ranked by exam weight and unmet
// prerequisites, each with a one-line reason. Selecting a skill opens its sheet: state, what it builds on and leads
// to, the learner's questions and mistakes, and a mistake's root gap (an earlier skill it really comes from), whose
// gap path lights on the map; a root-gap link nobody reviewed says so, never shown as curated. The same map is a
// table for screen readers and keyboard users who prefer one, and the box states are words as well as fills.
import { createContext, useContext, useEffect, useId, useMemo, useRef, useState, type ComponentType, type KeyboardEvent, type RefObject } from "react";
import { nodeBadges, openQuestions, type ConceptMap as ConceptMapData, type ConceptMapView, type ConceptMistake, type ConceptNode, type ConceptQuestion } from "@jana/client-core";
import { Icon } from "../icons.js";
import { useT } from "../i18n.js";
import { Button, EmptyState, ErrorState, IconButton, SegmentedControl, Skeleton, SuggestionChip } from "../primitives/index.js";
import { useVisualSettings } from "../visuals/VisualViewer.js";

/** A box of the drawing: the skill, its state's look and word, and the learner's badges. */
export interface ConceptDrawNode {
  id: string;
  code: string;
  title: string;
  state: string;
  stateWord: string;
  linked: boolean;
  subject?: string;
  asked: number;
  mistakes: number;
  next: number;
  badge?: string;
}

export interface ConceptDrawEdge {
  from: string;
  to: string;
  kind: "prerequisite" | "root_gap";
  strength?: "required" | "helpful" | undefined;
  reviewed?: boolean | undefined;
  name?: string | undefined;
}

/** The vetted drawing of the map, given by the app (the UI never imports renderers, ARC-18). */
export type ConceptMapRenderer = ComponentType<{
  nodes: readonly ConceptDrawNode[];
  edges: readonly ConceptDrawEdge[];
  label: string;
  t: (key: string, args?: Record<string, string | number>) => string;
  active: string | null;
  gap?: readonly string[];
  pointed?: string | null;
  reducedMotion: boolean;
  zoom?: number;
  onActivate: (id: string) => void;
  onFocusNode: (id: string) => void;
}>;

/** The map's sizes: small for an overview, large for reading every box. */
const ZOOMS = { small: 0.6, medium: 0.8, large: 1 } as const;
type Zoom = keyof typeof ZOOMS;

const RendererContext = createContext<ConceptMapRenderer | null>(null);
export const ConceptMapRendererProvider = RendererContext.Provider;
/** The app's drawing of a concept map, or null (the map then shows as its table). */
export function useConceptRenderer(): ConceptMapRenderer | null {
  return useContext(RendererContext);
}

export interface ConceptActions {
  /** "Ask Jana about this" on a skill. */
  onAskKc?: (node: ConceptNode) => void;
  /** An open question taken to the tutor, in the learner's own words. */
  onAskQuestion?: (text: string) => void;
  /** Practise or learn a skill (the topic's journey on the subject map). */
  onPractiseKc?: (node: ConceptNode) => void;
}

const SUBJECT_KEY: Record<string, string> = { "cur.mth.o": "concept.subject.mathematics", "cur.phy.o": "concept.subject.physics", "cur.chm.o": "concept.subject.chemistry", "cur.bio.o": "concept.subject.biology", "cur.acc.o": "concept.subject.accounting" };

function stateWord(t: ReturnType<typeof useT>, state: ConceptNode["state"]): string {
  return state === "explaining" ? t("concept.state.explaining") : t(`mastery.${state}`);
}

function useDrawing(map: ConceptMapData, t: ReturnType<typeof useT>) {
  return useMemo(() => {
    const badges = nodeBadges(map);
    const next = new Map(map.next.map((n, i) => [n.kc_id, i + 1]));
    const nodes: ConceptDrawNode[] = map.nodes.map((n) => ({
      id: n.kc_id, code: n.code, title: n.statement, state: n.state, stateWord: stateWord(t, n.state), linked: n.linked,
      ...(n.linked ? { subject: t(SUBJECT_KEY[n.subject_id] ?? "concept.other_subject") } : {}),
      asked: badges.get(n.kc_id)?.asked ?? 0, mistakes: (badges.get(n.kc_id)?.mistakes ?? []).filter((m) => m.status !== "resolved").length, next: next.get(n.kc_id) ?? 0,
    }));
    const edges: ConceptDrawEdge[] = map.edges.map((e) => ({ from: e.from, to: e.to, kind: e.kind, strength: e.strength, reviewed: e.reviewed, name: e.misconception_name }));
    return { nodes, edges, badges };
  }, [map, t]);
}

function NextList({ map, onPick }: { map: ConceptMapData; onPick: (kc: string) => void }) {
  const t = useT();
  const nodes = new Map(map.nodes.map((n) => [n.kc_id, n]));
  if (map.next.length === 0) return <p className="text-ui text-muted" data-next-empty>{t("concept.next.none")}</p>;
  return (
    <ol className="flex flex-col gap-2" data-next-list>
      {map.next.map((n, i) => {
        const node = nodes.get(n.kc_id);
        if (node === undefined) return null;
        const needs = n.needs.map((k) => nodes.get(k)?.statement ?? k);
        const reason = n.reason === "needs_first"
          ? t("concept.next.needs_first", { weight: t(`concept.weight.${n.weight}`), count: needs.length, first: needs[0] ?? "" })
          : t(`concept.next.${n.reason}`, { weight: t(`concept.weight.${n.weight}`) });
        return (
          <li key={n.kc_id} data-next-kc={n.kc_id} data-reason={n.reason} className="flex flex-wrap items-start justify-between gap-2 rounded-control bg-panel p-3">
            <span className="flex min-w-0 flex-1 basis-60 flex-col gap-1">
              <span className="text-ui font-semibold text-ink">{t("concept.next.item", { place: i + 1, skill: node.statement })}</span>
              <span className="text-meta text-muted">{reason}</span>
            </span>
            <Button size="sm" tone="ghost" onClick={() => onPick(n.kc_id)}>{t("concept.show_on_map")}</Button>
          </li>
        );
      })}
    </ol>
  );
}

function QuestionLine({ q }: { q: ConceptQuestion }) {
  const t = useT();
  return (
    <li className="flex flex-col gap-1 py-2" data-question={q.question_id} data-input={q.input}>
      <span className="text-ui text-ink">{q.kept && q.text !== null ? q.text : t("concept.question.not_kept")}</span>
      <span className="text-meta text-faint">{t(`concept.question.input.${q.input}`)}</span>
    </li>
  );
}

function MistakeLine({ m, map, onGap }: { m: ConceptMistake; map: ConceptMapData; onGap: (m: ConceptMistake) => void }) {
  const t = useT();
  const root = m.root_kc_id === null ? undefined : map.nodes.find((n) => n.kc_id === m.root_kc_id);
  return (
    <li className="flex flex-col gap-2 py-2" data-mistake={m.misconception_id} data-status={m.status}>
      <span className="text-ui text-ink">{t("concept.mistake.line", { name: m.name, count: m.times })}</span>
      <span className="text-meta text-muted">{t(`concept.mistake.status.${m.status}`)}</span>
      {root !== undefined && m.idea !== null && (
        <span className="flex flex-col gap-2 rounded-control bg-panel p-3">
          <span className="text-ui text-ink">{t("concept.root_gap.about", { idea: m.idea, skill: root.statement })}</span>
          {/* An unreviewed link is a suggestion, never curated content. */}
          <span className="text-meta text-faint" data-reviewed={m.reviewed === true ? "true" : "false"}>{t(m.reviewed === true ? "concept.root_gap.reviewed" : "concept.root_gap.unreviewed")}</span>
          <span><Button size="sm" onClick={() => onGap(m)}>{t("concept.root_gap.show")}</Button></span>
        </span>
      )}
    </li>
  );
}

function NodeSheet({ node, map, actions, onClose, onGap, onPick }: { node: ConceptNode; map: ConceptMapData; actions: ConceptActions; onClose: () => void; onGap: (m: ConceptMistake) => void; onPick: (kc: string) => void }) {
  const t = useT();
  const id = useId();
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => heading.current?.focus(), [node.kc_id]);
  const byId = new Map(map.nodes.map((n) => [n.kc_id, n]));
  const before = map.edges.filter((e) => e.to === node.kc_id && e.kind === "prerequisite").flatMap((e) => { const n = byId.get(e.from); return n === undefined ? [] : [{ e, n }]; });
  const after = map.edges.filter((e) => e.from === node.kc_id && e.kind === "prerequisite").map((e) => byId.get(e.to)).filter((n): n is ConceptNode => n !== undefined);
  const asked = map.questions.filter((q) => q.kc_id === node.kc_id);
  const mistakes = map.mistakes.filter((m) => m.kc_id === node.kc_id);
  const onKey = (e: KeyboardEvent<HTMLElement>) => {
    if (e.key === "Escape") {
      e.preventDefault();
      onClose();
    }
  };
  return (
    <section role="dialog" aria-modal="false" aria-labelledby={id} onKeyDown={onKey} data-concept-sheet={node.kc_id}
      className="jana-reveal flex flex-col gap-4 rounded-card border border-line bg-canvas p-5 lg:sticky lg:top-4">
      <div className="flex items-start justify-between gap-2">
        <h2 id={id} ref={heading} tabIndex={-1} className="text-heading text-ink">{node.statement}</h2>
        <span className="-me-2 -mt-1"><IconButton icon="dismiss" size="sm" label={t("sheet.close")} onClick={onClose} /></span>
      </div>
      <p className="text-meta text-muted">{t("concept.sheet.meta", { code: node.code, topic: node.topic_title, state: stateWord(t, node.state) })}</p>
      {node.linked && <p className="text-meta text-faint">{t("concept.linked_from", { subject: t(SUBJECT_KEY[node.subject_id] ?? "concept.other_subject") })}</p>}
      <span className="flex flex-wrap gap-2">
        {actions.onAskKc !== undefined && <Button size="sm" tone="primary" onClick={() => actions.onAskKc?.(node)}><Icon name="tutor" size={16} />{t("concept.ask_jana")}</Button>}
        {actions.onPractiseKc !== undefined && !node.linked && <Button size="sm" onClick={() => actions.onPractiseKc?.(node)}>{t("concept.practise")}</Button>}
      </span>
      {before.length > 0 && (
        <div className="flex flex-col gap-1">
          <h3 className="text-label text-faint">{t("concept.sheet.builds_on")}</h3>
          <ul className="flex flex-col">
            {before.map(({ e, n }) => (
              <li key={n.kc_id}><button type="button" className="text-start text-ui text-ink underline-offset-2 hover:underline" onClick={() => onPick(n.kc_id)}>
                {t(e.strength === "helpful" ? "concept.sheet.helpful" : "concept.sheet.required", { skill: n.statement, state: stateWord(t, n.state) })}
              </button></li>
            ))}
          </ul>
        </div>
      )}
      {after.length > 0 && (
        <div className="flex flex-col gap-1">
          <h3 className="text-label text-faint">{t("concept.sheet.leads_to")}</h3>
          <ul className="flex flex-col">
            {after.map((n) => <li key={n.kc_id}><button type="button" className="text-start text-ui text-ink underline-offset-2 hover:underline" onClick={() => onPick(n.kc_id)}>{n.statement}</button></li>)}
          </ul>
        </div>
      )}
      <div className="flex flex-col gap-1">
        <h3 className="text-label text-faint">{t("concept.sheet.your_questions", { count: asked.length })}</h3>
        {asked.length === 0 ? <p className="text-meta text-muted">{t("concept.sheet.no_questions")}</p> : <ul className="flex flex-col divide-y divide-line">{asked.map((q) => <QuestionLine key={q.question_id} q={q} />)}</ul>}
      </div>
      {mistakes.length > 0 && (
        <div className="flex flex-col gap-1">
          <h3 className="text-label text-faint">{t("concept.sheet.your_mistakes")}</h3>
          <ul className="flex flex-col divide-y divide-line">{mistakes.map((m) => <MistakeLine key={m.misconception_id} m={m} map={map} onGap={onGap} />)}</ul>
        </div>
      )}
    </section>
  );
}

function Legend() {
  const t = useT();
  return (
    <ul className="flex flex-wrap gap-x-5 gap-y-1 text-meta text-muted" data-concept-legend aria-label={t("concept.legend")}>
      <li>{t("concept.legend.required")}</li>
      <li>{t("concept.legend.helpful")}</li>
      <li>{t("concept.legend.root_gap")}</li>
      <li>{t("concept.legend.linked")}</li>
    </ul>
  );
}

function MapTable({ map, onPick }: { map: ConceptMapData; onPick: (kc: string) => void }) {
  const t = useT();
  const byId = new Map(map.nodes.map((n) => [n.kc_id, n]));
  const badges = nodeBadges(map);
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-start text-ui" data-concept-table>
        <caption className="sr-only">{t("concept.table.caption")}</caption>
        <thead>
          <tr className="border-b border-line text-label text-faint">
            <th scope="col" className="p-2 text-start">{t("concept.table.skill")}</th>
            <th scope="col" className="p-2 text-start">{t("concept.table.state")}</th>
            <th scope="col" className="p-2 text-start">{t("concept.table.builds_on")}</th>
            <th scope="col" className="p-2 text-start">{t("concept.table.yours")}</th>
          </tr>
        </thead>
        <tbody>
          {[...map.nodes].sort((a, b) => Number(a.linked) - Number(b.linked) || (a.code < b.code ? -1 : 1)).map((n) => {
            const needs = map.edges.filter((e) => e.to === n.kc_id).map((e) => {
              const from = byId.get(e.from)?.statement ?? e.from;
              return e.kind === "root_gap" ? t(e.reviewed === true ? "concept.table.root_gap" : "concept.table.root_gap_unreviewed", { skill: from, name: e.misconception_name ?? "" })
                : e.strength === "helpful" ? t("concept.table.helpful", { skill: from }) : from;
            });
            const b = badges.get(n.kc_id);
            const yours = [b !== undefined && b.asked > 0 ? t("concept.badge.asked", { count: b.asked }) : "", ...(b?.mistakes ?? []).map((m) => t("concept.badge.mistake_named", { name: m.name }))].filter(Boolean);
            return (
              <tr key={n.kc_id} className="border-b border-line align-top" data-row-kc={n.kc_id}>
                <th scope="row" className="p-2 text-start font-normal">
                  <button type="button" className="text-start text-ink underline-offset-2 hover:underline" onClick={() => onPick(n.kc_id)}>{n.statement}</button>
                  <span className="block text-meta text-faint">{n.code}</span>
                </th>
                <td className="p-2">{stateWord(t, n.state)}</td>
                <td className="p-2 text-muted">{needs.length === 0 ? t("concept.table.nothing") : needs.join("; ")}</td>
                <td className="p-2 text-muted">{yours.join("; ")}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

/** The concept map from its view: the subject map's "Map" mode, the gallery and the tests render this. */
export function ConceptMapContent({ view, actions = {}, onRetry, onShowGap, onClearGap, pointed = null, initialKc }: {
  view: ConceptMapView;
  actions?: ConceptActions;
  onRetry?: () => void;
  onShowGap?: (gap: { misconceptionId: string; rootKcId: string; kcId: string }) => void;
  onClearGap?: () => void;
  /** The skill the tutor points at (a `kc:` cue). */
  pointed?: string | null;
  initialKc?: string;
}) {
  const t = useT();
  const { reducedMotion } = useVisualSettings();
  const [mode, setMode] = useState<"map" | "table">("map");
  const [active, setActive] = useState<string | null>(initialKc ?? null);
  const [open, setOpen] = useState<string | null>(initialKc ?? null);
  const scroller = useRef<HTMLDivElement>(null);
  const map = view.map;
  const pick = (kc: string) => {
    setActive(kc);
    setOpen(kc);
    if (mode === "map") {
      const box = scroller.current?.querySelector<SVGGElement>(`[data-kc-node="${CSS.escape(kc)}"]`);
      box?.scrollIntoView?.({ block: "nearest", inline: "center", behavior: reducedMotion ? "auto" : "smooth" });
    }
  };
  useEffect(() => {
    // The tutor pointing at a skill brings it into view.
    if (pointed === null || mode !== "map") return;
    scroller.current?.querySelector<SVGGElement>(`[data-kc-node="${CSS.escape(pointed)}"]`)?.scrollIntoView?.({ block: "nearest", inline: "center", behavior: reducedMotion ? "auto" : "smooth" });
  }, [pointed, mode, reducedMotion]);
  if (view.status === "failed") return <ErrorState message={t("concept.failed")} {...(onRetry !== undefined ? { action: { label: t("action.try_again"), onClick: onRetry } } : {})} />;
  if (map === null) {
    return <div role="status" aria-busy="true" data-concept-loading><span className="sr-only">{t("map.loading")}</span><Skeleton lines={4} /></div>;
  }
  if (map.status === "not_installed") return <EmptyState message={t("map.not_installed")} />;
  if (map.status === "unverified") return <ErrorState message={t("map.unverified")} />;
  if (map.nodes.length === 0) return <EmptyState message={t("map.no_topics")} />;
  return <Ready map={map} view={view} mode={mode} setMode={setMode} active={active} setActive={setActive} open={open} setOpen={setOpen} pick={pick}
    scroller={scroller} actions={actions} onShowGap={onShowGap} onClearGap={onClearGap} pointed={pointed} reducedMotion={reducedMotion} />;
}

function Ready({ map, view, mode, setMode, active, setActive, open, setOpen, pick, scroller, actions, onShowGap, onClearGap, pointed, reducedMotion }: {
  map: ConceptMapData; view: ConceptMapView; mode: "map" | "table"; setMode: (m: "map" | "table") => void; active: string | null; setActive: (kc: string) => void;
  open: string | null; setOpen: (kc: string | null) => void; pick: (kc: string) => void; scroller: RefObject<HTMLDivElement | null>; actions: ConceptActions;
  onShowGap: ((gap: { misconceptionId: string; rootKcId: string; kcId: string }) => void) | undefined; onClearGap: (() => void) | undefined; pointed: string | null; reducedMotion: boolean;
}) {
  const t = useT();
  const drawing = useDrawing(map, t);
  const Drawing = useContext(RendererContext);
  const [zoom, setZoom] = useState<Zoom>("medium");
  const node = open === null ? null : map.nodes.find((n) => n.kc_id === open) ?? null;
  const opened = openQuestions(map);
  const gap = view.gap;
  const byId = new Map(map.nodes.map((n) => [n.kc_id, n]));
  const showGap = (m: ConceptMistake) => {
    if (m.root_kc_id !== null) onShowGap?.({ misconceptionId: m.misconception_id, rootKcId: m.root_kc_id, kcId: m.kc_id });
    setMode("map");
  };
  const close = () => {
    setOpen(null);
    scroller.current?.querySelector<SVGGElement>(`[data-kc-node="${CSS.escape(active ?? "")}"]`)?.focus();
  };
  return (
    <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]" data-concept-ready>
      <div className="flex min-w-0 flex-col gap-4">
        {gap !== null && (
          <div role="status" className="flex flex-wrap items-center justify-between gap-2 rounded-card border border-line-strong bg-canvas p-3" data-gap-banner={gap.path.join(" ")}>
            <span className="text-ui text-ink">{t("concept.gap.banner", { from: byId.get(gap.path[0] ?? "")?.statement ?? "", to: byId.get(gap.path[gap.path.length - 1] ?? "")?.statement ?? "" })}</span>
            {onClearGap !== undefined && <Button size="sm" tone="ghost" onClick={onClearGap}>{t("concept.gap.clear")}</Button>}
          </div>
        )}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <Legend />
          {Drawing !== null && (
            <span className="flex flex-wrap items-center gap-3">
              {mode === "map" && <SegmentedControl label={t("concept.zoom")} value={zoom} onChange={setZoom} options={(["small", "medium", "large"] as const).map((z) => ({ value: z, label: t(`concept.zoom.${z}`) }))} />}
              <SegmentedControl label={t("concept.view")} value={mode} onChange={setMode} options={[{ value: "map", label: t("concept.view.map") }, { value: "table", label: t("concept.view.table") }]} />
            </span>
          )}
        </div>
        {mode === "map" && Drawing !== null ? (
          <div ref={scroller} className="max-h-[78vh] overflow-auto rounded-card border border-line bg-canvas" data-concept-scroller>
            <Drawing nodes={drawing.nodes} edges={drawing.edges} label={t("concept.map_label", { count: map.nodes.length })} t={t}
              active={active} gap={gap?.path ?? []} pointed={pointed} reducedMotion={reducedMotion} zoom={ZOOMS[zoom]} onActivate={(kc) => setOpen(kc)} onFocusNode={setActive} />
          </div>
        ) : (
          <MapTable map={map} onPick={pick} />
        )}
      </div>
      {node !== null ? <NodeSheet node={node} map={map} actions={actions} onClose={close} onGap={showGap} onPick={pick} /> : (
        <div className="flex flex-col gap-6" data-concept-side>
          <section aria-labelledby="concept-next" className="flex flex-col gap-3">
            <h2 id="concept-next" className="text-heading text-ink">{t("concept.next.title")}</h2>
            <NextList map={map} onPick={pick} />
          </section>
          <section aria-labelledby="concept-open" className="flex flex-col gap-3" data-open-questions={opened.length}>
            <h2 id="concept-open" className="text-heading text-ink">{t("concept.open.title")}</h2>
            {opened.length === 0 ? <p className="text-ui text-muted">{t("concept.open.none")}</p> : (
              <ul className="flex flex-col gap-2">
                {opened.map((q) => (
                  <li key={q.question_id} className="flex flex-wrap items-center justify-between gap-2 rounded-control border border-dashed border-line-strong p-3" data-open-question={q.question_id}>
                    <span className="flex min-w-0 flex-1 basis-60 flex-col gap-1">
                      <span className="text-ui text-ink">{q.text}</span>
                      <span className="text-meta text-faint">{t("concept.open.label", { how: t(`concept.question.input.${q.input}`) })}</span>
                    </span>
                    {actions.onAskQuestion !== undefined && q.text !== null && <SuggestionChip icon="tutor" onClick={() => actions.onAskQuestion?.(q.text ?? "")}>{t("concept.ask_jana")}</SuggestionChip>}
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
