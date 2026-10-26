// The concept map on the client (UXS-22 map view): one subject's curated skill backbone with the learner's states,
// their questions and diagnosed mistakes, the ranked "what next" and the gap path a root-gap card points along
// (`GET /v1/curriculum/{subject_id}/concept-map`). The reply is checked against the command contract's `ConceptMap`
// at the boundary. Everything here belongs to the unlocked profile and is dropped when it locks (SEC-19).
import { errors, type api_commands } from "@jana/contracts-ts/client";
import type { ProfileController } from "./profiles.js";

type Listener = () => void;

export type ConceptMap = api_commands.ConceptMap;
export type ConceptNode = api_commands.ConceptNode;
export type ConceptEdge = api_commands.ConceptEdge;
export type ConceptNext = api_commands.ConceptNext;
export type ConceptQuestion = api_commands.ConceptQuestion;
export type ConceptMistake = api_commands.ConceptMistake;

/** A gap path lit on the map: the skills from the root gap to the KC the mistake was on, and the misconception. */
export interface GapHighlight {
  path: string[];
  misconceptionId: string | null;
}

export interface ConceptMapView {
  status: "idle" | "loading" | "ready" | "failed";
  subjectId: string | null;
  map: ConceptMap | null;
  gap: GapHighlight | null;
}

export const EMPTY_CONCEPT_MAP: ConceptMapView = { status: "idle", subjectId: null, map: null, gap: null };

export function readConceptMap(value: unknown): ConceptMap {
  const problems = errors("api/commands#/$defs/ConceptMap", value);
  if (problems.length > 0) throw new Error(`concept map reply does not match the contract: ${problems.slice(0, 3).join("; ")}`);
  return value as ConceptMap;
}

/** What a node shows from the learner's own layer: how often they asked about it and the mistakes diagnosed on it
 * (any not yet resolved first). */
export interface NodeBadges {
  asked: number;
  mistakes: ConceptMistake[];
}

export function nodeBadges(map: ConceptMap): Map<string, NodeBadges> {
  const out = new Map<string, NodeBadges>();
  const of = (kc: string) => {
    let found = out.get(kc);
    if (found === undefined) out.set(kc, (found = { asked: 0, mistakes: [] }));
    return found;
  };
  for (const q of map.questions) if (q.kc_id !== null) of(q.kc_id).asked++;
  for (const m of map.mistakes) of(m.kc_id).mistakes.push(m);
  return out;
}

/** The questions that match no KC: the map shows them apart, as open questions to take to the tutor. */
export function openQuestions(map: ConceptMap): ConceptQuestion[] {
  return map.questions.filter((q) => q.kc_id === null && q.kept);
}

/** The shortest chain of map edges from `from` to `to` (both included), or [] when there is none; ties go to the
 * earlier edge in the map's order, as on the core. */
export function pathOn(map: ConceptMap, from: string, to: string): string[] {
  const after = new Map<string, string[]>();
  for (const e of map.edges) after.set(e.from, [...(after.get(e.from) ?? []), e.to]);
  const came = new Map<string, string | null>([[from, null]]);
  const queue = [from];
  while (queue.length > 0) {
    const at = queue.shift()!;
    if (at === to) {
      const path = [at];
      for (let back = came.get(at); back !== null && back !== undefined; back = came.get(back)) path.unshift(back);
      return path;
    }
    for (const next of after.get(at) ?? []) {
      if (!came.has(next)) {
        came.set(next, at);
        queue.push(next);
      }
    }
  }
  return [];
}

/** One subject's concept map for the unlocked profile. */
export class ConceptMapController {
  private view: ConceptMapView = EMPTY_CONCEPT_MAP;
  /** A gap asked for before its subject's map was read (a root-gap card's "See it on the map"). */
  private wanted: { subjectId: string; gap: { misconceptionId?: string | null; rootKcId: string; kcId: string } } | null = null;
  private readonly listeners = new Set<Listener>();

  constructor(private readonly profiles: ProfileController) {
    profiles.onClear(() => {
      this.wanted = null;
      this.set(EMPTY_CONCEPT_MAP);
    });
  }

  getView = (): ConceptMapView => this.view;

  subscribe = (listener: Listener): (() => void) => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };

  private set(next: ConceptMapView): void {
    if (next === this.view) return;
    this.view = next;
    for (const listener of [...this.listeners]) listener();
  }

  /** Read a subject's concept map; a reply after a lock or a switch is dropped. A re-read keeps the map shown. */
  async load(subjectId: string): Promise<void> {
    const generation = this.profiles.generation;
    const same = this.view.subjectId === subjectId && this.view.map !== null;
    this.set(same ? { ...this.view } : { status: "loading", subjectId, map: null, gap: null });
    try {
      const map = readConceptMap(await this.profiles.commands.get<unknown>(`/v1/curriculum/${encodeURIComponent(subjectId)}/concept-map`));
      if (generation !== this.profiles.generation || this.view.subjectId !== subjectId) return;
      this.set({ status: "ready", subjectId, map, gap: this.view.gap });
      if (this.wanted?.subjectId === subjectId) {
        const { gap } = this.wanted;
        this.wanted = null;
        this.showGap(gap);
      }
    } catch {
      if (generation === this.profiles.generation && this.view.subjectId === subjectId) this.set({ ...this.view, status: same ? "ready" : "failed" });
    }
  }

  /** Light the gap path of a mistake: from its root-gap skill to the KC it was on (a root-gap card fired, or the
   * learner opened the mistake). A misconception the map does not know lights the direct link when both ends are on
   * the map, else nothing. */
  showGap(gap: { misconceptionId?: string | null; rootKcId: string; kcId: string }): void {
    const map = this.view.map;
    const known = map?.mistakes.find((m) => m.misconception_id === gap.misconceptionId && m.gap_path.length > 0);
    const path = known?.gap_path ?? (map === null ? [] : pathOn(map, gap.rootKcId, gap.kcId));
    this.set({ ...this.view, gap: path.length > 0 ? { path, misconceptionId: gap.misconceptionId ?? null } : null });
  }

  /** Light a gap on a subject's map once it is read (now, when it is the map shown). */
  showGapOn(subjectId: string, gap: { misconceptionId?: string | null; rootKcId: string; kcId: string }): void {
    if (this.view.subjectId === subjectId && this.view.map !== null) this.showGap(gap);
    else this.wanted = { subjectId, gap };
  }

  clearGap(): void {
    if (this.view.gap !== null) this.set({ ...this.view, gap: null });
  }

  /** A KC's mastery moved: re-read when it is on the map shown. */
  onProgress(kcId: string): void {
    const { map, subjectId } = this.view;
    if (map !== null && subjectId !== null && map.nodes.some((n) => n.kc_id === kcId)) void this.load(subjectId);
  }
}
