# Learning agent specification review

## Implementation follow-up — 30 October 2026

The original review below is historical. The seven-stage implementation now includes profile/egress guards, local
remember/correct/forget commands, persistent paginated history and offline access, typed source-rendered progress
facts, encrypted companion restoration, durable cloud admission, and inspectable teaching evidence.

The three-day simulated acceptance journey passes through the app API and real storage: a learner states
preferences, studies and answers a practice question, restarts, continues an agreement, corrects and forgets memories,
exports and restores an encrypted profile, receives a sourced progress statement, and switches profiles and back.
The latest integration run passed **80 tests** covering companion follow-ups, fact binding, profile/cloud boundaries,
the journey, opener, gateway and online memory. Earlier implementation checks also passed for history/offline access,
archive rejection and restoration, erasure/retention, teaching observations, durable budgets, UI and client behavior.
These runs overlap; their counts must not be added into a unique-test total.
The requirement audit also recorded a fresh named run of seven archive and four teaching-observation cases:
all 11 pass, covering authorized history, deletion-aware import, invalid provenance, explanation sources and
assisted versus delayed independent outcomes without promoting observations to mastery.

The seven-stage implementation and regression follow-ups are complete. The final original rebuild benchmark passed
within its unchanged 10-second limit after the other agent's bulk test processes finished; the complete test,
including fixture setup, took 38.29 seconds. All six memory API cases also pass on the final source snapshot.
The broad backend files have all run. Completed coverage includes 40 power-loss recovery cycles, the
306-combination development safety suite, the 10,000-turn engine stress test, the 1,000-turn API lifecycle stress test,
and content-only offline learning. The current file inventory accounts for all 317 agent-core/cloud-gateway test
files through original partitions and supplemental runs. The final 80-file agent-core partition recorded 955 passes,
one skip and eight failures; all eight failures now have passing original follow-ups.

The gateway partition finished with 484 passes, one skip and three failures sharing a structured-output contract
regression. The contract now explicitly declares supported response-format fields while retaining the schema-name
restriction and arbitrary nested output schema. Regenerated bindings pass all three original failures and three
companion-gateway cases, including lossless request-model parsing; 31 gateway guard/adapter/admission checks also
pass. Code generation, Python typing (690 files), UI typing and affected lint/formatting checks pass after this fix.

Other failures found during the gate have been addressed or independently rechecked:

- Standalone voice announcements retain compatibility with profile ownership checks. Answer-only voice tests now
  disable incidental filler timers; dedicated filler tests use a controlled clock and assembly barrier. The affected
  voice/boundary run passed 99 cases, and all eight parity cases pass after fixing its last timing assumption.
- The private-history route inventory includes authenticated companion history; all four history tests pass.
- Study search's small-model description is 278 characters, within its existing 280-character limit; three relevant
  description/schema checks pass and the tool snapshot is unchanged.
- Erasure registry, durability boundary, role/tool, demo, engine-flow and S1 topic-journey failures have passing
  original regressions.
  A diagnostic-thread stall required restarting unfinished coverage with its dump timer disabled.

The worker timing failure is resolved. `sec08_pathological_inputs_bounded` reproduced at 5.72 seconds despite
available CPU capacity: a rejected input waited for replacement startup before its error returned. The supervisor
now kills and removes that worker immediately and tracks replacement separately. Three deterministic regressions
failed before the fix and pass afterwards, covering delayed/failed startup, waiting callers and shutdown. The real
worker/sandbox run passed 17 cases including the original 2.5-second bound; its two assertions that assumed completed
replacement were updated to check immediate removal and subsequent recovery, and both original cases now pass.
Five integration cases also pass for rejection, queued callers, shutdown, error envelopes and crash recording.
**Goal status: complete.** `dat05_rebuild_time_budget` passes in the final quiet validation window.
Replay now reuses the current event's opportunity
across projections and caches parsed stamps on immutable events. All 34 replay/correction/migration cases pass.
A paired 100,012-event diagnostic retains the exact checksum and reduces CPU time from 9.44 to 9.02 seconds, but
elapsed time remains about 11.6 seconds. That early diagnostic used raw SQLite and initially empty projections, so
it is not acceptance evidence. A further check with the app's database pragmas and populated projections measured
9.75 CPU seconds and 12.33 elapsed seconds with the same checksum. The prior original benchmark failed at
11.83 seconds against its unchanged 10-second limit. After the other bulk test processes finished, the original
benchmark passed unchanged (`/tmp/jana-learning-agent-event-rebuild-quiet.xml`). This verifies the acceptance bound
in that window, not a guarantee under arbitrary host contention. All 22 memory/archive/teaching/journey checks
pass after the replay changes.
Two voice-off tests now pass after waiting for their startup handshake before teardown: the diagnostic showed cold
engine construction taking 1.87–2.15 seconds after an immediate disconnect, crossing the test's two-second close
deadline. That deadline is unchanged. No production limits were relaxed. The earlier learner-rebuild timing check
passed unchanged once host load fell. Implementation, functional acceptance and the final performance gate are
verified. The final benchmark can be reproduced with:

```sh
.venv/bin/pytest -q services/agent-core/tests/test_m6b_events.py::dat05_rebuild_time_budget --tb=short -o faulthandler_timeout=0
```

| Stage | Implementation and verification evidence | Current result |
| --- | --- | --- |
| 1. Isolation and cloud boundaries | `test_w8_companion_boundaries.py`: profile switches during queued opens, model/tool/compaction work and callbacks; retry-time consent withdrawal; local-only recall, history and compaction. | Targeted tests pass. |
| 2. Explicit memory commands | `test_companion_memory_commands.py`: restart persistence, committed acknowledgements, self-report evidence, version-pinned corrections, ambiguous deletion and forgotten-context exclusion. | Targeted tests pass. |
| 3. Continuity and offline access | `test_companion_continuity.py`, client companion tests and `companion-thread.test.tsx`: paginated history, offline access, restored runtime, local-only provenance and forward migration 22. | Targeted tests pass. |
| 4. Fact binding | `test_companion_fact_binding.py`: code-rendered references preserve metric, value, period and source; invalid references and representative unsupported claims are rejected. | Targeted tests pass. |
| 5. Restoration and durable budgets | `test_companion_archive.py`, existing deletion/export tests and `test_companion_durable_budget.py`: authorized history, deletion-aware import, rebuilt summary cursors, invalid provenance rejection and persistent account admission. | Targeted and compatibility tests pass. |
| 6. Teaching evidence and explanations | `test_teaching_observations.py` and knows UI tests: self-report versus practice, recorded assistance, delayed checked performance, conflicting outcomes, source references and no mastery mutation. | Targeted tests pass. |
| 7. Complete learner journey | `test_learning_agent_journey.py`: simulated three-day API/storage journey, including public practice commands, restored source-backed progress and switching profiles in both directions; broad backend files covered with failure follow-ups. | Journey and final rebuild benchmark pass. |

Concrete decisions and limits:

- Daily cloud limits bind to the authenticated account and are shared across its profiles/devices. The gateway has
  no authenticated learner identity; client-chosen pseudonyms cannot be trusted to create separate allowances.
- Forgetting removes saved memory and excludes older dialogue from model recall. Authorized history remains readable.
  The durable forget cutoff cannot weaken after clock rollback and audit retention.
  Restoration on this device respects known erasures. An older archive on an unrelated offline device cannot learn
  about a subsequent deletion without receiving its deletion state.
- Recent dialogue context is bounded to 100 scanned messages and 12,000 characters, with local recall for deeper
  retained history. Retention still applies; this is durable personal context, not unlimited memory.
- Raw companion conversation search stays local in both current and past scopes. Restored learner and tutor
  messages retain their local-only provenance; cloud replay uses only the filtered history builder.
  Companion compaction also stays local because it consumes history before that filter, with a deterministic
  fallback when no local model is available and a profile check before each model attempt.
- Teaching observations distinguish explicit preferences, assistance and later checked performance. They remain
  tentative associations, with no claim that a method caused learning or that Study activity proves mastery.
- The acceptance journey uses a simulated clock and scripted language model. A live demo and measured learner
  outcomes are separate evidence; passing these tests does not establish hackathon results or educational efficacy.

Implementation decisions and regression pointers are recorded in SPEC §19's Stage 1–7 follow-up. The findings below
are retained as the rationale and review history, rather than silently rewritten as a new source review.

---

## 1. Verdict

Rework §19 before building it. The proposed Study evidence can corrupt mastery, several contract extensions cannot validate or persist, and the cloud-memory flow contradicts its consent notice. Keep the November 4 scope to a bounded subset after the blockers below are resolved; the persistent thread, cloud reflection and note lifecycle are not small extensions to the existing implementation.

Review basis: the local specification and implementation, including the files named in `SPEC.md:1238`, the parent requirements, and the existing memory evaluation harness. This is a specification review, not a runtime certification: validation consisted of source inspection, read-only schema-pointer checks and recomputation of the stated costs; no application code, contracts, tests or existing documents were changed.

## 2. Blocking findings

### B1. Topic suggestions are being promoted to mastery evidence without a valid observation model

**Spec:** `SPEC.md:1159`, `SPEC.md:1238`, `SPEC.md:1242`.

**Contradiction:** `services/agent-core/agent_core/engine/study_topics.py:18` matches topic-title phrases and collects the topic's KCs; it does not establish which skills an item tests. `services/agent-core/agent_core/learner/mastery.py:230` applies confidence only to `diagnoser`, so `study_topics` confidence has no effect. At `services/agent-core/agent_core/learner/mastery.py:343`, an observation changes subject ability, and at line 346 a success gives the full observation weight to **every** tagged KC, regardless of its normalized share; evidence also propagates to neighbouring KCs at line 355. Furthermore, `services/agent-core/agent_core/engine/study.py:1591` explicitly distinguishes comparison with a model-written answer key from independently checked correctness. Recording nothing for an unmatched item does not protect matched-but-irrelevant skills or incorrect answer keys.

**Fix:** Specify admissible item-to-KC evidence and grading assurance, the aggregation of per-tag confidence into the event's single `kc_confidence`, and the exact mastery modifiers before enabling Study mastery updates. Until these are defined and tested, title matches may support activity/context records but must not feed `pfa_elo`.

### B2. The proposed Study writes do not specify a valid atomic, idempotent event conversion

**Spec:** `SPEC.md:1162`, `SPEC.md:1238`, `SPEC.md:1244`.

**Contradiction:** Study already opens transactions in `services/agent-core/agent_core/engine/study.py:1533` and `services/agent-core/agent_core/engine/study.py:1612`; `Learner.record_batch` rejects an enclosing transaction at `services/agent-core/agent_core/learner/service.py:109`. `submit_quiz` belongs to `StudyQueue` and delegates to `StudyDesk.submit` at `services/agent-core/agent_core/engine/study.py:1853`, so adding event writes at both named seams can double-record one submission. The event requires a session, per-item attempt identity/index, response kind and timing at `contracts/learning/learning-event.schema.json:670`, whereas Study has a prefixed submission ID and can submit several items or perform a preliminary check; omitted answers become `skipped` at `services/agent-core/agent_core/engine/study.py:1576`. No Study session creation/closure or mapping of these cases is specified. Finally, `create_job` enqueues work; the successful aid write is at `services/agent-core/agent_core/engine/study.py:1327`, with completion at line 1404.

**Fix:** Name one commit seam using `record_batch(..., extra=...)` for the Study rows and events together, with grading completed before the transaction and stable per-item identities across retries. Define Study session boundaries, check-versus-submit semantics, skipped/unverifiable handling and ready-activity emission at the successful completion commit, including the other `study_activity` producers.

### B3. Reusing `review` cannot represent the retained Study scheduler, and verdicts still schedule learner cards

**Spec:** `SPEC.md:1164`, `SPEC.md:1243`.

**Contradiction:** `contracts/learning/learning-event.schema.json:1001` requires an `attempt_id` and one `kc_id`, with no deck, card, revision or scheduler identity. A Study review is a self-rating of a particular card, with no corresponding attempt, at `services/agent-core/agent_core/engine/study.py:1491`; different cards on the same KC can legitimately have different dates. Meanwhile, closing an ordinary learning opportunity calls `_review` at `services/agent-core/agent_core/learner/projections.py:436`, and `_review` writes a learner-model card at line 490. Merely stating that Study keeps its scheduler neither prevents this second scheduling path nor makes a Study card's schedule reconstructible on another device.

**Fix:** Define separate identity and replay semantics for Study card reviews, including how a self-rating relates to an attempt, and explicitly control whether Study verdicts may update KC review cards. Either specify deterministic synchronization of Study schedules and the D19 agreement check or explicitly keep those schedules device-local and amend the claimed cross-device guarantee for this feature.

### B4. Several explicit contract/storage instructions fail against the current schemas

**Spec:** `SPEC.md:1156`, `SPEC.md:1160`, `SPEC.md:1168`, `SPEC.md:1178`, `SPEC.md:1185`, `SPEC.md:1255`.

**Contradiction:** The `attempts.mode` CHECK still excludes Study at `contracts/data/schema.sql:337`; only the sessions CHECK is explicitly listed in §19.3.2. The proposed card problem reference is **65 characters**: `stc:` + a 30-character deck ID + `:` + a 30-character card ID (`contracts/study/workspace.schema.json:21`), exceeding `problem_ref.maxLength = 64` at `contracts/learning/learning-event.schema.json:709`. `Session.origin` is its own enum at `contracts/api/commands.schema.json:488`, so adding only `CreateSession.origin.kind` leaves returned sessions invalid. There is no `envelope.type` property/enum at `contracts/learning/learning-event.schema.json:525`; learning event types are selected by the root union, and erased-event types have a separate branch at line 449. Likewise, new tutor event definitions must enter the union at `contracts/api/events.schema.json:2680`. Regenerating SQL alone does not upgrade installed databases; the forward migration mechanism is in `services/agent-core/agent_core/store/sqlite.py:18`.

**Fix:** Replace the prose list with checked pointers covering both event unions, erased types, request and response enums, every affected SQL CHECK and a bounded problem-reference encoding. Require a forward migration and generated-binding validation against both a fresh database and an existing profile.

### B5. A Study warm-up cannot survive the plan event or identify what to open

**Spec:** `SPEC.md:1243`, `SPEC.md:1410`.

**Contradiction:** Updating the API `PlanBlock` does not update the persisted `plan_generated.blocks` schema, which rejects extra properties at `contracts/learning/learning-event.schema.json:1254`. The planner's `Block` holds only kind, KCs, minutes and reason at `services/agent-core/agent_core/learner/planner.py:83`; adding `source: study` alone still loses the deck/card tuple. The actual state collector reads only learner-model due cards at `services/agent-core/agent_core/engine/plans.py:138` and passes them into `PlannerState` at line 152; that file is missing from the change list.

**Fix:** Carry a bounded, typed Study selection through the state collector, planner block, learning event, stored plan, API view and UI open action. Define selection/order and the shared review-cap calculation across both schedulers, including unavailable or stale Study cards.

### B6. The proposed egress path sends precisely the data the consent says never leaves

**Spec:** `SPEC.md:1277`, `SPEC.md:1352`, `SPEC.md:1356`, `SPEC.md:1361`, `SPEC.md:1369`.

**Contradiction:** Automatic `study_search` would forward verbatim source chunks, titles and session-note statements from `services/agent-core/agent_core/engine/ask_anything.py:123`; the existing caller gates their transmission separately through `share_own` at line 178. §19's automatic recall step does not carry that gate. Explicit “remember” input is only escaped, not scrubbed, in `services/agent-core/agent_core/memory/reflect_input.py:146`; filtering the eventual note is too late to prevent its request text leaving. §19.6 expressly permits past transcript hits to leave while its notice says conversations never leave, and the extractor sends student text before filtering its output (`SPEC.md:1321`). The Redactor checks known terms and contact patterns, not every third-party name or exam date (`services/agent-core/agent_core/config/personal_data.py:78`, line 95). Reusing the independent evaluation grader as the production scrub also destroys the independence declared in `evals/memory/grader.en.yaml:1`. Finally, the adapter's `store: false` controls stored completions (`services/cloud-gateway/cloud_gateway/providers/meta.py:64`); it is not evidence for “deleted when each reply is made.”

**Fix:** Specify and enforce a per-purpose egress allowlist for automatic recall, tool results, reflection, explicit requests, extractors and opener facts before serialization, with source-sharing consent independently checked and unapproved text withheld. Rewrite the notice and DAT-18 amendment to match that exact payload and verified retention guarantee, keeping the evaluation grader independent of the runtime filter.

### B7. The consent and cloud Reflector cannot be enabled by the listed changes alone

**Spec:** `SPEC.md:1229`, `SPEC.md:1244`, `SPEC.md:1247`, `SPEC.md:1253`, `SPEC.md:1420`.

**Contradiction:** Scope availability derives from `PROFILE_SCOPES` and feature stages, not a standalone `shipped_scopes` list (`services/agent-core/agent_core/store/consents.py:23`, line 63). The SQL scope CHECK omits the new value (`contracts/data/schema.sql:48`), and consent grants require a server-shipped notice at `services/agent-core/agent_core/api/profiles.py:311`; a client notice-version constant is insufficient. Network policy rejects unregistered features/classes at `services/agent-core/agent_core/net/policy.py:161`. On routing, removing the special Reflector ban still leaves `reflector` absent from `roles_allowed` (`services/agent-core/agent_core/router/router.yaml:194`), and `reflection.py` returns early for `content_only` hardware before reaching the proposed local-candidate gate (`services/agent-core/agent_core/engine/reflection.py:579`). Thus the phase-3 promise for machines without Glimmer is not met by the named edits.

**Fix:** Add the complete scope/feature/policy/notice/client/storage registration and specify the effective-consent dependency and revocation check at each send. Include the Reflector in the permitted roles under that gate and revise both hardware and candidate checks, with a real content-only-machine acceptance test.

### B8. An indefinitely open session bypasses the promised transcript retention

**Spec:** `SPEC.md:1119`, `SPEC.md:1181`, `SPEC.md:1249`, `SPEC.md:1310`.

**Contradiction:** Transcript retention selects only sessions with `ended_at IS NOT NULL`, then deletes all their turns at once (`services/agent-core/agent_core/store/retention.py:95`). A single companion session kept open for weeks and resumed indefinitely will never enter that purge, despite the stated 90-day bound on recall. Ending and reusing the same row instead risks deleting recent messages together with old ones. The same session identity also means many days of companion use count as one session for support and promotion (`SPEC.md:1339`, `SPEC.md:1344`).

**Fix:** Specify rolling per-turn retention for the persistent thread, covering parts, retrieval, checkpoints and summary provenance, with no exemption for an open session. Explicitly distinguish the thread's identity from any bounded study episode used for engagement, support or promotion, or state that companion-only use cannot satisfy distinct-session thresholds.

### B9. Summary persistence is underspecified, and forgetting a note can replace JSON with plain text

**Spec:** `SPEC.md:1182`, `SPEC.md:1251`, `SPEC.md:1300`.

**Contradiction:** `CompanionSummary` has no durable fold cursor or counted-session identity, and its misconceptions, `what_worked` and `open_questions` lack the timestamps needed for the 30-day removal rule. Its two arrays cannot be unambiguously populated from the existing single `summary_for_student` string (`contracts/agents/reflection.schema.json:95`). More directly, forgetting a note scans **all** session summaries and replaces matching content with the two-sentence `code_summary` (`services/agent-core/agent_core/memory/write.py:130`), corrupting a companion summary's JSON representation and discarding unrelated sections. The transparency client is a separately checked `KnowsView`, not the proposed `MemoryList` extension (`packages/client-core/src/memory.ts:4`, line 35).

**Fix:** Specify durable cursor/deduplication metadata, per-entry freshness/provenance, and a typed mapping for the Reflector's permitted summary edits. Make forgetting, expiry, loading, repair and the Knows endpoint mode-aware so they preserve valid companion JSON and remove every derived copy of forgotten content.

### B10. Ten conversational turns can produce no Reflector evidence, and compaction does not preserve this dialogue

**Spec:** `SPEC.md:1217`, `SPEC.md:1244`, `SPEC.md:1310`, `SPEC.md:1418`.

**Contradiction:** The queue cursor counts learning events, not transcript turns (`services/agent-core/agent_core/engine/reflection.py:808`), and skips without new evidence at line 817. `build_input` reads only selected event types up to the cursor, not a lower-bounded dialogue window (`services/agent-core/agent_core/memory/reflect_input.py:122`); an accepted check-in answer does not automatically become such evidence. Existing compaction retains problem/board state and summarizes free dialogue only when a callback is supplied (`services/agent-core/agent_core/engine/compaction.py:55`, line 81); queuing an event-only Reflector cannot preserve the missing conversations. Cancellation is requeued in-process, but startup recovery finds only ended sessions whose summary is null (`services/agent-core/agent_core/engine/reflection.py:829`), excluding this long-lived thread after its first summary.

**Fix:** Define the bounded evidence produced by conversational turns and check-in answers, its privacy rules, and separate durable cursors for summary folding and successful reflection. Specify the actual companion compaction input and restart recovery so a cancelled or deferred Reflector job cannot lose its window, and distinguish preserving structured facts from preserving free-dialogue meaning.

### B11. The tool reuse violates the promised reference boundary unless adapters are specified

**Spec:** `SPEC.md:1189`, `SPEC.md:1195`, `SPEC.md:1246`, `SPEC.md:1249`.

**Contradiction:** `own_evidence` returns raw source/chunk/note IDs and string refs such as `own1`, not integer model refs (`services/agent-core/agent_core/engine/ask_anything.py:147`, line 171). The existing cloud block deliberately creates an empty ref table (`services/agent-core/agent_core/memory/render.py:199`), so “as cloud for refs (integer refs still)” describes incompatible behaviours. `progress_of` requires a committed attempt, selected KCs and a prior probability map (`services/agent-core/agent_core/engine/memory_tools.py:153`); it is not the zero-argument profile overview proposed here. Adding tools only to generated register output will be overwritten: its source is `contracts/registers/toolsets.json`, explicitly named at `services/agent-core/agent_core/tools/generated/register.py:1`. Past transcript search and model-written `study_search` text also exceed the current MEM-05 exception, which allows only current-session transcript search (`../jana/docs/specification/memory-and-context.md:96`).

**Fix:** Specify adapters that produce minimal model-facing records with per-call integer refs, resolve them against the captured profile and source revision, and invalidate stale refs safely when snapshots refresh. Add the authoritative tool-register changes, a separate fixed progress query and an explicit bounded MEM-05 amendment; do not permit SQL or arbitrary memory-query generation.

### B12. Note lifecycle changes bypass existing ownership/replay rules and conflict with hard bounds

**Spec:** `SPEC.md:1222`, `SPEC.md:1254`, `SPEC.md:1339`.

**Contradiction:** `keep` is currently a no-op (`services/agent-core/agent_core/memory/write.py:519`), while contradiction creates a separate pending note and preserves the original at line 562, as MEM-09 requires (`../jana/docs/specification/memory-and-context.md:154`). §19 changes this to automatic demotion without defining how student-owned or corrected notes are protected. The notes projection reconstructs rows from events (`services/agent-core/agent_core/learner/projections.py:534`), but the proposed SQL fields omit stored support-session identities/promoted state or rules for deriving them, and render-time recall writes have no specified rebuild/sync semantics. “Never cut” promoted notes conflicts with the enforced block allowance at `services/agent-core/agent_core/memory/render.py:228`; sufficiently many promoted notes cannot all fit. “Never fade” student requests also does not prevent the existing 180-day expiry, which uses creation time regardless of support or recall (`services/agent-core/agent_core/store/retention.py:225`).

**Fix:** Define lifecycle changes as validated, replayable writes through the existing authorized writer, explicitly preserving or amending MEM-09 ownership and contradiction handling. Make promotion a bounded priority, define whether recall metadata is local or synchronized, and state that retention wins over pinning unless the retention policy is explicitly changed.

### B13. The proposed configuration additions fail strict parsing and do not enforce caps

**Spec:** `SPEC.md:1256`, `SPEC.md:1401`.

**Contradiction:** Gateway configuration forbids unknown fields (`services/cloud-gateway/cloud_gateway/config.py:31`); `Limits` has no companion or memory-job fields at line 266, and `GatewayConfig` has no `[companion]` model at line 346. Adding the prescribed TOML keys without those changes fails configuration loading. Neither TOML addition defines admission, reservations, charging, retries, per-learner identity, reset time or the queue behaviour at the cap. The existing router budgets are substantially broader than this feature's proposed cap (`services/agent-core/agent_core/router/router.yaml:206`).

**Fix:** Add typed configuration and entitlement fields plus gateway admission/accounting seams that enforce the dollar, turn and job caps across concurrent requests and devices. Define whether aid generation and correction/tool calls count, and reserve/reconcile their usage before treating the numbers as operational limits.

### B14. Companion actions and openers are not defined as durable session state

**Spec:** `SPEC.md:1184`, `SPEC.md:1185`, `SPEC.md:1257`, `SPEC.md:1274`.

**Contradiction:** The current stream has a bounded replay ring (`services/agent-core/agent_core/api/stream.py:52`), with recovery through the server projection and client snapshot (`services/agent-core/agent_core/api/projection.py:15`, `packages/client-core/src/hydrate.ts:18`). Neither the snapshot shape nor the reducer knows about companion actions/openers; unrecognized client events fall through at `packages/client-core/src/reducer.ts:319`. Merely rendering the new events in a controller loses their state on reconnect/restart. The proposed `open_tutor` action also lacks the question payload it must carry, and `open_study_job` conflates an existing job with an add-source flow; opener delivery through both HTTP response and stream has no deduplication identity (`SPEC.md:1180`, `SPEC.md:1186`).

**Fix:** Define durable action/opener representations, typed payloads and stable identities, then include them in server folding, persistence, snapshot hydration and client replay. Specify idempotent open/resume under concurrent calls and exactly-once presentation without relying on the in-memory event ring.

## 3. Non-blocking findings, ranked by design impact

### N1. The November 4 cut is not supported by the dependency list

**Spec:** `SPEC.md:1121`, `SPEC.md:1238`, `SPEC.md:1290`, `SPEC.md:1478`.

**Evidence:** Phase 1 requires a structured learner serializer that does not exist in `SessionMemory.block` (`services/agent-core/agent_core/engine/memory_session.py:121`), Study session/event plumbing, mastery semantics, migrations, two-scheduler plan integration and new reflection inputs. The opener requires last-session selection, due-count union, current exam facts, pack-ready watermarks, checkpoint caching and numeric validation; including summary next-step and check-ins brings in later-phase dependencies. The persistent thread additionally requires B8–B10 and B14. The demo's Biology mastery claim also conflicts with the shipped-subject decision (`SPEC.md:68`) and the existing topic matcher, which only knows installed pack KCs (`services/agent-core/agent_core/engine/study_topics.py:13`).

**Fix:** For November 4, prioritize read-only learner context, deterministic known-level research behaviour and a code-backed opener using already available facts; cut title-derived mastery, Study plan integration, cloud notes, lifecycle changes and check-ins. Ship the persistent thread only if retention, replay, isolation and compaction pass end-to-end tests, and use an installed mathematics/physics/chemistry topic in the demo.

### N2. “One miss lowers the band” is not the current mastery rule, and the next Coach snapshot may stay stale

**Spec:** `SPEC.md:1408`, `SPEC.md:1468`, `SPEC.md:1479`.

**Contradiction:** A failed opportunity after a passed mastery check sets `review_failed` (`services/agent-core/agent_core/learner/projections.py:427`), but `needs_review` still renders as `secure` (`services/agent-core/agent_core/memory/render.py:43`). A single observation also need not cross any probability threshold. A Coach snapshot is frozen once and returned unchanged on later freezes (`services/agent-core/agent_core/engine/memory_session.py:83`); §19 explicitly refreshes only the companion.

**Fix:** Make acceptance assert the correct evidence/state transition for a seeded learner, rather than an unconditional band downgrade. Specify whether “next tutor turn” means a newly opened session or an explicitly invalidated snapshot, preserving reference and prompt-cache correctness.

### N3. Check-in extraction and delivery need a complete operational state machine

**Spec:** `SPEC.md:1207`, `SPEC.md:1213`, `SPEC.md:1318`, `SPEC.md:1323`, `SPEC.md:1331`.

**Contradiction:** The dedupe key needs a subject/KC, but neither the stored commitment nor extractor output provides one. Opening a check-in returns `CompanionOpened`; it does not create the “thread turn that opened it” used to mark it answered. The daily opener cache (`SPEC.md:1295`) can also return a different or already dismissed check-in. The date rule does not define timezone/travel behaviour, past dates, ordering direction for confidence or whether a deadline check should occur after the deadline. Persistent ownership matters because existing jobs are cancelled on profile switch/deletion (`services/agent-core/agent_core/engine/reflection.py:881`), but the new heartbeat/notification jobs have no corresponding lifecycle or missing-source-session rule.

**Fix:** Specify grounded subject/KC identity, timezone and deterministic date conversion, atomic daily delivery/deduplication, explicit transitions including which accepted answer resolves which commitment, and invalidation of cached openers. State that deleted-source commitments expire or detach safely, profile deletion cancels jobs/notifications, and lock/profile changes prevent delivery from the previous profile.

### N4. Offline and consent-off behaviour is undefined at the API boundary

**Spec:** `SPEC.md:1248`, `SPEC.md:1292`, `SPEC.md:1364`, `SPEC.md:1420`.

**Contradiction:** The turn API can reject with `model_unavailable` before reaching the proposed `turn.py` branch (`services/agent-core/agent_core/api/core.py:1025`). The opener only specifies fallback after invalid wording, not unavailable candidates, revoked consent or exhausted budget. “Without [memory consent] the request is declined as today” also incorrectly excludes a valid local Reflector: current explicit requests are admitted when `local_ready()` succeeds (`services/agent-core/agent_core/engine/reflection.py:608`).

**Fix:** State that thread history and a code opener remain readable offline, define local-candidate versus unavailable conversational behaviour, and never queue cloud prompts without permission. Keep local explicit-memory requests working without the cloud-memory consent, and define consent withdrawal during an in-flight call and before applying its result.

### N5. Known research level cannot be filled at the proposed seam

**Spec:** `SPEC.md:1150`, `SPEC.md:1241`.

**Contradiction:** `Brief.level` is required and permits `o_level` or `first_year` (`contracts/study/research.schema.json:26`, line 52), while profile levels are `O` or `A` (`contracts/api/commands.schema.json:371`). `next_turn` validates the structured response before `tidy` runs (`services/agent-core/agent_core/engine/research_chat.py:151`), so a missing level fails before the fallback. Adding a sentence to the prompt does not enforce “never asks a known level”; existing `tidy` returns question turns without such a filter at line 117.

**Fix:** Specify the supported level mapping and override precedence, then make known level part of decoding/validation or normalize it before final validation. Suppress redundant level questions in code and define the follow-up when a learner explicitly changes the intended level.

### N6. The budget arithmetic is broadly plausible, but two totals and the bound are wrong

**Spec:** `SPEC.md:1387`, `SPEC.md:1391`, `SPEC.md:1400`.

**Evidence:** Recomputed using the checked-in prices at `services/cloud-gateway/cloud_gateway/defaults.toml:38`:

| Item | Recomputed USD | Consequence |
| --- | ---: | --- |
| Opener, 200 / 400 / 80 tokens | 0.000650 | Rounding in the spec is reasonable. |
| Plain turn, 800 / 2,500 / 250 | 0.0024375 | Rounding is reasonable. |
| One-tool-round turn, 1,800 / 2,500 / 300 | 0.003900 | Twelve cost **0.046800**, not 0.04. |
| Reflector, 1,800 / 0 / 600 | 0.004800 | Two cost **0.009600**, not 0.015; label any extra allowance explicitly. |
| Extractor, 500 / 0 / 80 | 0.000965 | Rounding is reasonable. |
| Opener + 12 tool turns + one $0.05 aid + two reflections | **0.107050** | Without the aid: **0.057050**. |
| Twenty such sessions, each also using one extractor | **2.160300** | Estimate only, not a demonstrated upper bound. |

The learner block costs no separate call but adds billed input tokens, so its row is not generally $0. A two-round tool exchange can require several model requests; the table does not say whether it sums all requests, repeats the prompt, includes cache misses, or includes reasoning in output. `strong-model` currently maps every reasoning setting to `minimal` (`services/cloud-gateway/cloud_gateway/defaults.toml:34`), so “≤ $0.01 at low” is neither a configured distinct case nor a measured bound. The extractor runs after every lexically qualifying turn, not necessarily once per session (`SPEC.md:1321`).

**Fix:** Label the table as an estimate and state whether each token row totals the entire exchange, including reasoning, corrections and tools. Add measured cold-cache and maximum-round cases and enforce B13 before promising twenty sessions under $3.

### N7. The eval files do not fit the existing runner, and named tests do not cover every done-when claim

**Spec:** `SPEC.md:1407`, `SPEC.md:1414`, `SPEC.md:1420`, `SPEC.md:1463`.

**Contradiction:** `scripts/jana_tools/harness/memory.py:95` loads every session YAML, and `session_state` expects `problem`, `plan`, `board`, `step` and `rung` at line 143; `transcript` expects rounds of student/tutor pairs at line 161. The proposed endpoint/state-transition scenarios have no defined adapter to this format. Persona `p_o_chemistry` does exist (`evals/memory/personas.yaml:7`), but a valid persona and filename do not execute a rubric.

| Done-when claim | Coverage gap in the named tests |
| --- | --- |
| Phase 1: Progress changes and the next Coach block reflects it (`SPEC.md:1408`) | Atomic event-write tests do not verify the actual mastery/band result or a live frozen Coach snapshot (`SPEC.md:1434`). |
| Phase 2: opener names the last subject/date (`SPEC.md:1414`) | Number checking does not establish selection of the correct session or subject (`SPEC.md:1439`). |
| Phase 2: three-session topic counts and no lost summary entry (`SPEC.md:1417`) | In-place updates/schema validity do not verify distinct-session deduplication, retry replay or preservation through real compaction (`SPEC.md:1446`). |
| Phase 3: cloud reflection writes a note used by the next cloud Coach (`SPEC.md:1421`) | The named test asserts a cloud call with `store:false`, not the complete write/read/egress chain (`SPEC.md:1453`). |
| Phase 3: Saturday becomes Sunday morning (`SPEC.md:1422`) | Present only as an unimplemented eval scenario; the unit list has no date-resolution test (`SPEC.md:1449`). |
| Phase 3: notifications appear only when enabled (`SPEC.md:1425`) | Template-body coverage does not verify opt-in or OS permission (`SPEC.md:1452`). |

The existing list also omits restart recovery, profile isolation after switching, deletion/retention, consent revocation, event replay convergence, repeated submissions and cap enforcement. Its “transcripts never leave” test contradicts the allowed recall-hit egress rather than resolving it (`SPEC.md:1456`, `SPEC.md:1370`).

**Fix:** Specify a dedicated scenario adapter/runner and fixtures, assertions, suite registration and held-out evaluation procedure before adding these YAML files. Add named integration tests for each gap above, plus the blockers' rollback, privacy and lifecycle cases, with the egress expectation first made internally consistent.

### N8. The proposed UI placement hides the profile-wide companion behind a selected source

**Spec:** `SPEC.md:1258`, `SPEC.md:1259`, `SPEC.md:1262`, `SPEC.md:1305`.

**Contradiction:** `StudyWorkspace` returns its library view before reaching source tabs when no source is selected (`packages/ui/src/learn/StudyWorkspace.tsx:247`); adding a third tab to `TABS` alone cannot provide a general Study companion entry. The Knows client has no companion summary in its current note/view contract (`packages/client-core/src/memory.ts:4`), and the UI table only adds note badges despite promising a rolling summary on that page. Adding a Cargo dependency beside `tauri-plugin-dialog` (`apps/desktop/src-tauri/Cargo.toml:35`) also leaves notification initialization, permission handling, click routing and cancellation unspecified.

**Fix:** Place and route the companion at the profile-wide Study level, define its relation to a selected source, and add the summary endpoint/view rendering explicitly. List the notification runtime, permission and client integration files, including denied permission and profile-switch behaviour.

### N9. Several supposedly reused operations are new work, and the prose hides their decisions

**Spec:** `SPEC.md:1238`, `SPEC.md:1248`, `SPEC.md:1282`, `SPEC.md:1293`.

**Contradiction:** `SessionMemory.block` requires an allowance and returns a rendered block, not the claimed data form (`services/agent-core/agent_core/engine/memory_session.py:121`); selecting at most 24 KCs for the new structured request is therefore an unspecified serializer/query. `engine/gates.py` implements schema, verified values, answer-leak, one-ask and budget gates, not the named set of Study personal-advice/brand gates (`services/agent-core/agent_core/engine/gates.py:23`). `{action: null | {…}}` leaves the executable output contract undefined, and “every number appears” permits misbinding a real number to the wrong fact: 12 due cards can become “your exam is in 12 days.” Requiring every input number in a 240-character opener can also be impossible once a numeric next-step is included.

**Fix:** Name the serializer, bounded selection rule and actual gate implementations, and replace the ellipsis with the complete action schema. Define semantic provenance for fact/value pairs and select a bounded subset of opener facts by code before wording, with current facts refreshed even when wording is cached.

### N10. Cross-device identity and retained operational data remain an owner-visible product decision

**Spec:** `SPEC.md:1100`, `SPEC.md:1111`, `SPEC.md:1119`, `SPEC.md:1216`, `SPEC.md:1226`.

**Evidence:** §19 locates state on the device but says one companion per profile and promises note writing “on every machine”; this does not say whether two devices share a thread or simply each run one. Parent synchronization carries event-log segments (`../jana/docs/specification/data-model.md:427`), whereas commitments and recall counters are new operational tables outside that stated event path. Retention rules are an explicit table registry (`services/agent-core/agent_core/store/retention.py:70`), but no retention period is given for dismissed/answered commitments or note-recall rows; 72-hour delivery expiry is not storage deletion. A whole-profile delete can remove the learner database, but that alone does not specify already scheduled OS notifications or queued in-memory work.

**Fix:** State explicitly whether the W8 thread, commitments and recall statistics are per device, and define conflict/identity rules before claiming synchronization. Give each new stored field a purpose, retention and egress classification as PRV-03 requires (`../jana/docs/specification/privacy-and-safety.md:54`), including cleanup after source/session/note deletion.

## 4. Incorrect or misleading references checked

Most existing function line numbers in §19.4 are accurate; the problems below are wrong locations, incorrect owners or claims that the cited seam does more than it does, rather than routine line drift.

| Cited | Actual |
| --- | --- |
| `SPEC.md:1168`: `envelope.type` enum | No such enum in `contracts/learning/learning-event.schema.json:525`; extend root variants and the erased-event type list at line 449. |
| `SPEC.md:1188`: `ev_status.phase` enum | Phase is a `$ref`; its enum is `$defs/status_phase` at `contracts/api/events.schema.json:120`. |
| `SPEC.md:1238`: `StudyDesk.submit_quiz`, line 1743 | `StudyQueue` starts at `services/agent-core/agent_core/engine/study.py:1712`; its `submit_quiz` is at line 1743 and delegates to `StudyDesk.submit` at line 1853. |
| `SPEC.md:1238`: `create_job`, line 804, as the ready-aid write seam | It creates a job; the aid transaction is at `services/agent-core/agent_core/engine/study.py:1327`, and the job is completed at line 1404. |
| `SPEC.md:1238`: `SessionMemory.block("cloud")` data form | `services/agent-core/agent_core/engine/memory_session.py:121` requires `allowance_chars` and renders a block; a structured data serializer is new work. |
| `SPEC.md:1246`: cloud refs preserve integer note refs | `services/agent-core/agent_core/memory/render.py:199` makes the cloud ref table empty. |
| `SPEC.md:1249`: `progress_of`, line 153, as a profile overview | `services/agent-core/agent_core/engine/memory_tools.py:153` is an attempt-specific before/after view and rejects an attempt without a committed verdict. |
| `SPEC.md:1254`: `memory/policy.py` as the location of `apply_reflection` | Implementation is `services/agent-core/agent_core/memory/write.py:438`; policy supplies validation helpers. |
| `SPEC.md:1189`: generated register among tool-definition edit targets | `services/agent-core/agent_core/tools/generated/register.py:1` says to edit `contracts/registers/toolsets.json` and regenerate. |
| `SPEC.md:1228`: `MemoryList` as the Knows UI data seam | The client validates the separately proposed `KnowsView` contract in `packages/client-core/src/memory.ts:4`; `KnowsNote` starts at line 35. |
| `SPEC.md:1313`: existing compaction “summarises only free dialogue” | `services/agent-core/agent_core/engine/compaction.py:69` only does so with an explicit callback; otherwise it retains earlier Agreements or leaves that section empty. |
| `SPEC.md:1314`: cursor skip proves a window “since the last job” | Skip is at `services/agent-core/agent_core/engine/reflection.py:597`; input construction at `services/agent-core/agent_core/memory/reflect_input.py:122` reads up to the cursor, not from a prior lower bound. |
| `SPEC.md:1359`: memory grader as runtime privacy machinery | `evals/memory/grader.en.yaml:1` explicitly defines an independent evaluation filter. |
| Review brief: TABLE DAT-18a in `architecture.md` | Table is `../jana/docs/specification/data-model.md:418`; architecture references it at `../jana/docs/specification/architecture.md:149`. This location error is in the review brief, not §19's parent-directory citation. |

## 5. Owner-only questions and recommended answers

1. **What must be demonstrated on November 4: a persistent companion or the full three-phase learning loop?** The deadline decision at `SPEC.md:1121` and demo at `SPEC.md:1478` imply different dependency sets. **Recommendation:** approve the bounded read-only context/opener cut in N1; require the persistence blockers to pass before calling the thread persistent, and defer cloud memory/check-ins.

2. **May a generated Study quiz change official mastery, and what grading/tagging assurance is acceptable?** This changes the meaning of Progress, not just implementation (`SPEC.md:1408`; `services/agent-core/agent_core/learner/mastery.py:343`). **Recommendation:** do not count title-derived tags or unverified model keys as mastery evidence; retain their activity value until an explicit evidence policy is approved.

3. **Which private text, if any, may be sent for memory features?** The current notice forbids text that other paragraphs permit (`SPEC.md:1352`, `SPEC.md:1363`, `SPEC.md:1370`). **Recommendation:** initially allow only screened short notes and code-built evidence under the new consent; keep raw explicit requests and historical transcript excerpts local, and require the existing source-sharing permission for document excerpts. Do not promise provider deletion on reply completion without evidence for that guarantee.

4. **Does “your agent” mean one device's companion or one identity and history across devices?** The wording at `SPEC.md:1100` and `SPEC.md:1119` does not settle it, and Study schedules are outside the specified event representation. **Recommendation:** declare W8 state device-local, make that clear in the product, and reserve shared-thread/schedule synchronization for a separately specified phase.

5. **Does pinning imply indefinite retention, and may the Reflector demote student-owned notes automatically?** The new lifecycle at `SPEC.md:1339` conflicts with existing ownership and expiry semantics. **Recommendation:** keep the 180-day retention ceiling and student approval protections; make pinning a bounded retrieval preference, not an exemption or proof that a note is true.

6. **What does profile level `A` mean for a research brief that supports only `o_level` and `first_year`?** The enums differ at `contracts/api/commands.schema.json:371` and `contracts/study/research.schema.json:52`. **Recommendation:** never silently map A level to first-year university; limit the November demonstration to O level and explicitly specify the broader mapping later.
