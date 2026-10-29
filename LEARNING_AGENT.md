# A personal learning agent for Study: review and proposal

Status: **review, 2026-10-28**. Written after reading this repository and three reference repositories under
`.opensrc/repos/github.com/`: NousResearch/hermes-agent, openclaw/openclaw and synthetic-sciences/openscience.
Nothing here is decided; §5 lists the owner decisions it needs. Paths are relative to this repository unless
they start with the reference repository's name.

The goal, in the owner's words: a learning agent, personalised to each learner, that knows about their learning,
can talk to them, and has long (persistent) memory, for the Study feature.

## 1. What Jana already has

Jana is further along than any of the three repositories on the part that matters most: **a typed model of the
learner, written by code, per profile, on the device.** None of hermes-agent, OpenClaw or OpenScience has a user
model at all; each has a free-text notes file and a search index. Jana has:

| Layer | What it holds | Where | Written by | Read by |
|---|---|---|---|---|
| Learner model | Mastery per knowledge component (pfa_elo with a BKT baseline), FSRS-6 review cards, misconceptions (suspected → active → resolving → resolved), preferences, engagement (streak, frustration, confidence bias), subject ability, the profile (level, subjects, exam date, goals, support level) | `profiles/{ulid}/learner.db`, projections folded from an append-only event log (`agent_core/learner/projections.py`) | Code only: every attempt, verdict, hint, review and mastery check is an event (`learner/service.py`) | The Coach's learner block (tier 6), the planner (`learner/planner.py`), the adaptation policies (`learner/policies.py`), the Progress and "What your tutor knows" pages |
| Episodic notes | Dated, evidenced, declarative facts about the learner's learning, ≤140 characters, ≤50 active, ≤40 per subject, each citing event-log entries | `notes` table in the same database, with an FTS5 index | The Reflector only (`engine/reflection.py`), at four write points: end of problem, end of session or idle, end of onboarding, an explicit "remember that…" | The Coach's learner block (local variant only) and `memory_recall`; the "What your tutor knows" page (`packages/ui/src/memory/KnowsPage.tsx`) with forget and undo |
| Session transcript | Student text, tutor text, board state | `transcript` tables, 90-day retention | The engine | `session_recall` (current session only) |
| Session summary | Two sentences per session | `sessions.summary` | The Reflector, or code when it has nothing | Nothing reads it back into a prompt today |
| Study work | Sources, chunks, aids (notes, summary, chat, flashcards, quiz, podcast, lesson plan, chapters, concept map), decks with their own FSRS, quiz results, study journeys, research packs | Study tables in the same database (`engine/study.py`) | Study jobs | Study screens, Ask anything's own-material search |

Around this sits a memory discipline the reference repositories would envy: a do-not-capture filter (lexicon plus a
small classifier, `memory/capture.py`), a write policy that rejects instructions, relative dates, quotes of the
student, secrets and duplicates (`memory/policy.py`), integer refs so a model never sees a record id
(`memory/refs.py`), fixed read queries so a model never writes a query (`memory/queries.py`), bounded stores with
consolidation, a frozen snapshot per session, records-not-instructions wrappers, a memory-use indicator, undo, and a
transparency page. The product specification (`../jana/docs/specification/memory-and-context.md`) records that
these were borrowed, deliberately, from hermes-agent (consolidation on overflow, blocked entries left visible), mem0
(integer refs), crewAI (consolidation verbs), OpenScience (compaction threshold) and openworker (announce and undo).
So the question is not "how do we build memory": it is built. The question is why the learner does not feel it.

## 2. Why the learner does not feel it today

Four findings, each checked in code.

### 2.1 Study is cut off from the learner model

- Study, Ask anything and the research conversation never receive the learner block. The gateway's Study prompt
  (`cloud_gateway/study.py` ~1079–1260) sends source passages, settings, the syllabus outline and, for a follow-up,
  the previous answer's claim texts as "untrusted conversational context". No level, no mastery, no misconceptions,
  no notes. The research conversation (`engine/research_chat.py`) asks the learner what level they are at even though
  the profile stores it.
- Study emits no learning events (`engine/study.py`, line 1: "no syllabus learning events are emitted"). A quiz in
  Study moves nothing in the mastery model, and the Reflector never sees Study activity, so nothing a learner does in
  Study is ever remembered. Study flashcards use their own scheduler (`fsrs-6-source-v1`), separate from the learner
  model's review cards, so the planner does not know they are due.
- "Study chat" is not a conversation. Each question is one job producing one cited aid; a follow-up carries only the
  parent aid's claims (`StudyDesk.brief`, `previous_response`). There is no stored thread, no history, no opener.

### 2.2 Notes are dead on most jana-meta machines

- The Reflector runs only on a local model (`router/core.py` ~242: the reflector role has the cloud tier off;
  `reflection.py` `local_ready`). On a laptop without Muse Glimmer, which is every machine under 32 GB and every
  demo machine running online, a Reflector job is skipped (`no_local_candidate`) and an explicit "remember that…"
  is declined with the fixed notice. **No note is ever written.**
- The Coach prefers the cloud. A cloud call renders the learner block's cloud variant: the profile line, KC ids with
  three bands, misconception ids, preferences, and no notes (`memory/render.py`; MDL-25, MEM-20). `memory_recall`
  is withheld. **No note is ever read.**
- So in jana-meta the "persistent memory" the learner can feel is the mastery tables alone, and only in the guided
  tutor. This is a consequence of the parent product's privacy rule MDL-25, written for an under-18 product with a
  local model on every machine. jana-meta is an adult product whose online model is Spark in Standard mode with
  `store: false`. The rule deserves a fresh decision (§5, decision A).

### 2.3 There is no agent to talk to

- Each feature has its own prompt and its own short-lived state: the guided tutor (a session), Study (jobs), the
  research conversation (client-held turns, at most three questions), Ask anything (one shot). The soul
  (`content/agent/soul/SOUL.md`) gives them one voice, but nothing gives them one memory or one thread.
- Nothing reaches out. Exam reminders are computed when the app is open (`engine/exam_dates.py`); research jobs are
  polled. There is no scheduler, no check-in, no "you have 12 cards due and your exam is in 19 days" from the agent's
  side.

### 2.4 Identity is the device profile, and that is the right place

- The gateway knows a learner only as a random per-session pseudonym (`cloud_gateway/app.py`, `x-session-pseudonym`)
  and keeps a research job at most 24 hours. There is no account, and the learner database is one SQLite file per
  profile on the device. This is a strength: "each user has a special agent with long memory" is already true at
  the storage layer, with no multi-tenant isolation to build. All three reference repositories key memory per
  *agent* or *profile*, not per user, and their own docs warn that per-user memory needs one agent per person. Jana
  has that for free. The agent should stay on the device; only minimised prompts leave.

## 3. What each repository teaches

### 3.1 hermes-agent (NousResearch)

A single-owner personal agent. Memory is two plain-text files per profile, a SQLite transcript index, and an
optional external provider. What transfers:

| Pattern | Where in hermes-agent | Use in Jana |
|---|---|---|
| Two tiny always-in-prompt stores with character caps and the fill percentage in the header: `USER.md` (who the user is, 1,375 chars) and `MEMORY.md` (lessons, 2,200 chars) | `tools/memory_tool_store.py` (`_render_block`) | Jana's profile line and notes already split this way. Add the fill level to the Reflector's input so it consolidates before the bound, not at it |
| Overflow returns the current entries and asks for one atomic batch that removes or shortens and adds; at most three failed attempts per turn, then a terminal "stop retrying" so a save never blocks the reply | `memory_tool_store.py` (`apply_batch`, `_MAX_CONSOLIDATION_FAILURES_PER_TURN`) | Already adopted as MEM-12. Keep |
| The memory snapshot is frozen at session start; per-turn recall is appended to the **user message** inside a fence marked "NOT new user input", never to the system prompt, so the prompt cache survives | `agent/system_prompt.py`, `agent/memory_manager.py::build_memory_context_block`, `agent/turn_context.py` | The way to put recalled Study material and notes into a Spark call cheaply: Spark's cached input is $0.15 against $1.25 per million tokens |
| Learning happens in a **post-reply background fork** every N turns, with the same prompt (warm cache), tools restricted to memory and skills, deletions staged for approval, a do-not-capture block, and the rule "one fact goes to one store" | `agent/background_review.py`, triggers in `agent/turn_context.py` and `agent/turn_finalizer.py` | This is Jana's Reflector, which is already better bounded. The transferable part is the trigger: hermes also reviews **every 10 turns**, not only at session end. A long Study session should get a mid-session write point |
| Procedures live in skills, not memory: an always-present index of name and ≤60-char description, the body loaded on demand, patched by the agent after corrections ("stop doing X" is a first-class signal) | `agent/prompt_builder.py` (~1475), `tools/skill_manager_tool.py`, `tools/skill_manager_guards.py` (read before write) | Per-learner, per-topic "what works for this learner" files (§4, phase 4). Jana's teaching skills are authored and signed; learner-specific overlays would be a new, reviewed store |
| Full-text search over every past session as episodic recall, returning real messages, no summarisation | `tools/session_search_tool.py`, `hermes_state_common.py` | Extend `session_recall` from the current session to the profile's past sessions (already isolated by database). Hermes does not filter by user; Jana must, and already does |
| Scheduled jobs in a fresh session with a `[SILENT]` reply that suppresses delivery; suggested jobs need consent and remember dismissals | `cron/scheduler_prompt.py`, `cron/suggestions.py`, `/heartbeat` | Check-ins (§4, phase 3) |
| Injection and secret scan on write **and on load**; a poisoned entry is shown as `[BLOCKED]` in the prompt but kept on disk for the user to delete; secrets are scrubbed before anything leaves to a third-party memory backend | `tools/threat_patterns.py`, `memory_tool.py` | Jana does the write-side and render-side checks (MEM-27). Adopt the egress scrub if notes ever go to the cloud (decision A) |
| Honcho provider: a user model reasoned out by a model after each turn, refreshed on a cadence, with a warm-up call at session start so turn 1 already knows the user | `website/docs/user-guide/features/honcho.md` | The "opener" of a personal agent: before the first turn, one cheap call that turns the snapshot and last summary into "Last time you…" |

What not to copy: memory keyed per profile with no per-user filter; free-text facts with no evidence (hermes's own
docs note that models under about 30B claim saves they never made; Jana's spec cites this as the reason mastery is
written by code).

### 3.2 OpenClaw

A multi-channel personal assistant daemon. Memory is a curated `MEMORY.md` plus daily logs, a hybrid FTS5 and
sqlite-vec index in one SQLite file per agent, a nightly consolidation ("dreaming"), and a pre-reply recall sub-agent.
What transfers:

| Pattern | Where in OpenClaw | Use in Jana |
|---|---|---|
| Two tiers: a capped curated file always in the prompt, and dated daily logs that are only searched; on a new session, today's and yesterday's logs are prepended once as quoted untrusted data | `docs/concepts/memory.md`, `src/auto-reply/reply/startup-context.ts` | Jana's notes are the curated tier. The missing tier is a per-session Study log (what was read, made, missed) that is searchable but never in the prompt by default |
| Promotion by recall frequency: every retrieval is logged with its query hash and day; a snippet is promoted into the curated file only after passing score, count (≥3), distinct-query (≥3) and age gates, re-read from source before writing, with idempotent markers | `extensions/memory-core/src/short-term-promotion.ts` | A misconception or note that keeps being recalled across sessions earns a place in the profile line; one that is never recalled decays. Gives the notes layer a principled "what matters" signal it lacks |
| The curated file has a budget; when over it, the oldest **machine-written** sections go first and user-authored sections never do | `extensions/memory-core/src/memory-budget.ts` | Same rule for notes: a note the student asked for (`student_request`) is never evicted by consolidation; Reflector notes are |
| Silent pre-compaction memory flush: one hidden turn that may only append to today's log and must reply `NO_REPLY` if nothing is worth saving | `extensions/memory-core/src/flush-plan.ts` | A write point for long Study conversations before their context is compacted (§4, phase 2) |
| Active memory: a pre-reply recall sub-agent on a cheap model with only search tools, a 15 s timeout, `NONE` as the default, a summary of ≤220 characters written about the user, injected as untrusted context; a circuit breaker after 3 timeouts; always fails open | `extensions/active-memory/index.ts` (~1085) | The cheapest way to make a Study turn personal without sending the whole learner model: one `fast-model` call that writes two lines about this learner for this question |
| Hybrid retrieval in one SQLite file: FTS5 BM25 plus sqlite-vec at 0.3/0.7, 400-token chunks with 80 overlap, a hash-keyed embedding cache, and temporal decay (half-life 30 days) on dated logs only, never on the curated file | `packages/memory-host-sdk/src/host/memory-schema.ts`, `src/agents/memory-search.ts`, `extensions/memory-core/src/memory/temporal-decay.ts` | Jana's study chunks are already in SQLite with lexical search; the open question in Jana's own spec (MEM-21: whether a local embedding model fits) is answered by OpenClaw's fallback: lexical when no embedder is available |
| Commitments: after each reply, a debounced extractor proposes `{kind, due window, suggested text, dedupe key, confidence}` (event check-in, deadline check, care check-in, open loop); delivery is rate-limited (3 a day, quiet hours, at least one interval of delay, 72 h expiry) and runs without tools | `src/commitments/extraction.ts`, `src/infra/heartbeat-runner.ts` (~861) | "Mock paper on Saturday → ask on Sunday how it went". Exactly the check-in a personal tutor should make |
| Heartbeat with a `tasks:` list of `{name, interval, prompt}`: only due tasks enter the prompt, a tick with nothing due makes no model call, `HEARTBEAT_OK` suppresses the message, quiet hours apply | `docs/gateway/heartbeat.md`, `src/infra/heartbeat-runner.ts` | Due-review nudges and exam-distance nudges with no model call unless something is due |
| Conversational onboarding (`BOOTSTRAP.md`) that fills `USER.md` and `IDENTITY.md`, then deletes itself | `docs/reference/templates/BOOTSTRAP.md`, `src/agents/workspace.ts` | Jana's first-session interview is scripted and calls no model (D104). A Coach-worded version is MEM-06's unbuilt onboarding write point |
| memory-wiki: claims with `status`, `confidence`, `evidence[]` and freshness, with reports for contradicted, low-confidence and stale (30/90-day) claims | `extensions/memory-wiki/src/claim-health.ts` | Jana's misconception states already behave like this. The transferable part is the **stale report**: a note unsupported for 90 days should be shown as fading on the knows page |
| Prompt layout: persona and profile above a cache boundary; only the timezone above it, the clock fetched by a tool; volatile sections below | `src/agents/system-prompt.ts` (`SYSTEM_PROMPT_CACHE_BOUNDARY`) | Jana's nine tiers already separate stable from per-turn; audit the Study prompt for the same split before paying Spark's uncached price every turn |

What not to copy: memory per agent rather than per user; the "load MEMORY.md only in private sessions" rule that
lives in an instruction file rather than code; regex auto-capture of "I prefer…" (crude; the recall-frequency
promotion is the robust version).

### 3.3 OpenScience (Synthetic Sciences)

A local-first research agent, a science fork of the OpenCode coding agent. It has **no user model and no
cross-session memory store**; its evidence-gated lesson memory exists in code but is switched off (removed in #612).
It is only weakly relevant to per-user memory and strongly relevant to verification. What transfers:

| Pattern | Where in OpenScience | Use in Jana |
|---|---|---|
| Evidence-gated, falsifiable lessons: `situation + guidance + supports[] + contradictions[] + confidence (tentative/supported) + status`; "supported" only with verified evidence from **more than one session**; `unlearn` requires counterevidence and a rejected lesson cannot be re-learned with the same wording; at most 6 injected, labelled "untrusted priors; revalidate" | `backend/cli/src/session/research.ts` (~150–165, 779–921, 1537–1605) | The best model for Jana's notes to grow into: a note is `tentative` until a second session's evidence supports it; the Reflector's existing `contradiction` verb becomes counterevidence that demotes rather than deletes |
| A structured handoff that **updates the previous one** instead of regenerating from the transcript ("regenerating every time lets still-true facts drift"): Objective, Deliverables verbatim, Constraints and decisions, Findings with numbers and whether verified, Work state (done verified, in progress, blocked), Next move | `backend/cli/src/session/compaction.ts` (455–520) | The rolling per-profile Study summary (§4, phase 2): sections Topics covered, Misconceptions seen, What worked, Open questions, Next step; each session updates the last one |
| Strategy modes from attempt history: explore, refine, pivot, fuse, verify; pivot forced after 3 non-advancing attempts or a repeated failed approach | `session/research.ts` (`strategy`, 923–1030) | Already in spirit in Jana's adaptation policies (LRN-15 to LRN-27). The explicit "after three failures with the same representation, switch representation" rule is worth adding as a policy |
| Mechanical gates before a turn may end (`loop.before_finish`): deliverables present and free of placeholders and NaN, verifier commands run and fed back, a fresh-context reviewer at most twice | `backend/cli/src/harness/{deliverables,acceptance,review}.ts` | Jana's release gates (`engine/gates.py`) are this. The fresh-context reviewer (sees only the problem and the answer) is a cheap second opinion for Study aids beyond the support verifier |
| Change-keyed status reminders: per-step facts go in a tail message appended only when their key changes, so the prefix stays byte-identical | `session/prompt.ts` (1740–1790, `studyReminder`) | How to carry "cards due: 12, exam in 19 days" into every Study turn without breaking the cache |
| Evaluation discipline: a rubric written before any run, development and held-out splits, one harness rule changed per revision, acceptance bullets like "every number matches the fixture" | `evals/launch/rubric.json`, `evals/launch/suite.json` | `evals/memory` exists with personas and a grader. Add Study-memory cases and freeze the rubric before building |

What not to copy: anything about user modelling (there is none); summarising with a model where Jana's typed state
already gives a deterministic summary for free (Jana's spec made this call already, MEM-16).

## 4. Proposal: the personal learning agent, built from what exists

One agent per profile, on the device, with one voice (the soul), one memory (the learner database), one thread (a
persistent Study conversation), and a cloud model that sees only what the learner has allowed. The model phrases;
code decides, as everywhere in Jana. Four phases, each useful on its own.

### Phase 1: connect Study to the learner model (days; demo-visible)

1. **The learner block enters Study, the research conversation and Ask anything.** Render the existing cloud
   variant (profile line, KC bands, misconception ids, preferences; MDL-25-safe) and pass it with the request; the
   gateway's Study prompt and `research_chat.INSTRUCTION` gain a "who this learner is" section. The research
   conversation stops asking the level. Files: `engine/study.py` (`StudyDesk.brief`), `net/study.py`,
   `cloud_gateway/study.py` (~1079), `engine/research_chat.py`, `contracts/study/*` (a `learner` field).
2. **Study emits learning events.** Quiz attempts and verdicts, flashcard reviews and "explain back" results become
   `attempt`, `verdict` and `review` events tagged with KC ids through `engine/study_topics.py`'s topic matching
   (weighted tags where a question spans KCs, as LRN-08 allows). Mastery, misconceptions and the planner then see
   Study. Study's own FSRS deck stays, but its due cards are surfaced to the planner as a warm-up block.
3. **Study gets write points.** End of a Study session (or idle) queues a Reflector job with new evidence types
   (`study_quiz`, `study_review`, `study_aid`), so what the learner did in Study can become a note. Reflector input
   lines are rendered from events and pack labels, never from the learner's documents (`memory/reflect_input.py`).

Phase 1 changes no privacy rule: the cloud still sees bands and ids only. It also makes decision A worth taking,
because without it phase 3's notes are written only on Glimmer machines.

### Phase 2: the conversation (the agent the learner talks to)

4. **A persistent Study thread per profile.** One stored conversation (reuse the `sessions` and transcript tables
   with a `kind=study_companion`), with the Coach persona, that can: recall (`memory_recall`, `session_recall`
   extended to past sessions), search the learner's material (a `study_search` tool over `study_chunks` and aids,
   lexical, the same `own_evidence` Ask anything uses), read progress (`kc_views`, due cards, exam distance), plan
   (`learner/planner.py`), and act (create a Study job, start a research brief, open a practice set). Every action is
   an existing code path; the model only chooses and phrases, and every number still comes from a tool. Homework
   questions are routed to the guided tutor as Ask anything already does (`ask_route`).
5. **An opener from memory.** Before the first turn of a session, build "Last time you…" from the last session
   summary and the snapshot (code first; one `fast-model` call to word it, hermes's Honcho warm-up). Store the
   session summary as a **rolling handoff** that updates the previous one (OpenScience): Topics covered,
   Misconceptions seen, What worked, Open questions, Next step. Today `sessions.summary` is written and never read.
6. **Per-turn recall in a fence.** Recalled notes and material go into the user message as records (hermes), not
   the system prompt, so Spark's prompt cache holds; "cards due, exam in N days" rides as a change-keyed status line
   (OpenScience). Add a mid-session write point every N turns (hermes) and a silent flush before compaction
   (OpenClaw) so a long Study conversation loses nothing.

### Phase 3: memory that reaches the cloud, and an agent that reaches out

7. **Notes online, under consent (decision A).** A new consent, "Personal tutor memory online", lets the Reflector
   run on Spark (`strong-model`, background priority, `store: false`) and lets the learner block's cloud variant
   carry notes. Notes are already learning-only by construction: the do-not-capture filter, the write policy (no
   names, places, contacts, secrets, quotes), ≤140 characters, evidence-cited. Add hermes's egress scrub as a last
   line. Without this, the personal agent is personal only on 32 GB machines with Glimmer.
8. **Check-ins.** OpenClaw's commitments extractor after a Study turn ("mock paper Saturday → ask Sunday"), and a
   heartbeat with due tasks (cards due, exam distance thresholds, a pack that finished) that makes no model call when
   nothing is due. Delivery: a card on Home when the app opens, and a desktop notification through the Tauri shell;
   quiet hours, at most one a day, a dismissal remembered. No push infrastructure is needed.
9. **Evidence-gated notes.** A note starts `tentative`; it becomes `supported` only when a second session's evidence
   backs it (OpenScience); `contradiction` demotes instead of deleting; recall frequency (OpenClaw) promotes a note
   into the profile line and lets unrecalled notes fade; the knows page shows stale notes as fading (memory-wiki).

### Phase 4: procedural memory per learner

10. **"What works for you" overlays.** Per-learner, per-topic notes of the hermes skill kind ("for quadratics, a
    sketch first, then the formula"), written by the Reflector from policy decisions and outcomes, shown as an index
    in tier 5 and loaded on demand, pending on the knows page until the learner keeps them. Jana's authored
    teaching skills stay signed and unchanged; overlays are a separate, reviewed store.

### Evaluation

`evals/memory` already has personas, sessions and a grader. Before phase 1 lands, write the Study-memory rubric
(OpenScience: rubric before runs): the opener names last session's topic; a quiz miss in Study changes a KC band;
the research conversation never asks what the profile knows; a note from Study passes the capture filter; a cloud
request carries nothing outside DAT-18. Keep a held-out set.

### Budget (the $150 of credit)

| Call | Model | Per session | Note |
|---|---|---|---|
| Learner block in Study and research prompts | none | $0 | Rendered by code |
| Opener wording | `fast-model` | ~$0.002 | Cached prefix |
| Reflector on Spark (decision A) | `strong-model`, minimal prompt, ≤600 output tokens | ~$0.01 per write point | Background priority |
| Study thread turns | `fast-model` for routing and recall, `strong-model` only when an aid is made | ~$0.01–0.03 per turn | Cache the prefix; recall in the user message |
| Check-in extractor | `fast-model` | ~$0.002 | Skipped when a turn has no commitment-like content |

## 5. Decisions for the owner

| # | Decision | Recommendation |
|---|---|---|
| A | Relax MDL-25 for jana-meta: may episodic notes leave the device, and may the Reflector run on Spark, under a separate consent? | **Yes, under consent.** Adult product, Standard mode (no training), `store: false`, notes already filtered to learning facts with no identifiers. Without it the personal agent exists only on Glimmer machines, which the demo laptop may not be |
| B | Does Study write to the learner model (events, mastery, planner)? | **Yes.** Today Study is a separate product inside the app. Phase 1 is small and makes everything after it possible |
| C | One Study thread per profile, or one per source? | **One per profile.** The agent is the learner's, not the document's; sources are what it searches |
| D | Check-ins: in-app only, or desktop notifications too? | In-app card first (no new surface); Tauri notification behind a setting, off by default |
| E | Scope for the 4 November submission | Phase 1 and items 4–5 of phase 2 are demo-visible in days: the research conversation that already knows you, a quiz that moves your progress, and a Study thread that opens with "Last time you…" |

## 6. Read first

1. `services/agent-core/agent_core/engine/reflection.py`: the Reflector, its gates and write points.
2. `services/agent-core/agent_core/memory/render.py`, `snapshot.py`, `write.py`: the learner block (local and cloud), freezing, the write policy.
3. `services/agent-core/agent_core/engine/turn.py` (`_prepare`, `_learner_block`, `_cloud_system`): how the Coach gets memory today.
4. `services/agent-core/agent_core/engine/study.py` (`StudyDesk.brief`, `create_job`) and `services/cloud-gateway/cloud_gateway/study.py` (~1079–1320): the Study prompt that gets no learner.
5. `services/agent-core/agent_core/engine/research_chat.py`: the conversation that should already know the learner.
6. `services/agent-core/agent_core/router/router.yaml` and `router/core.py` (~242): where the Reflector is barred from the cloud.
7. `../jana/docs/specification/memory-and-context.md` and `model-router.md` (MDL-25): the rules this proposal asks to revisit.
8. In the reference repositories: `hermes-agent/main/agent/background_review.py`, `openclaw/main/extensions/memory-core/src/short-term-promotion.ts`, `openclaw/main/src/commitments/extraction.ts`, `openscience/backend/cli/src/session/research.ts`.
