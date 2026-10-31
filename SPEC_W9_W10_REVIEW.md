# Review of SPEC.md §20 (W9, video) and §21 (W10, the learner's map)

Reviewed 2026-10-31 against the working tree at `b99c661f` plus uncommitted W8 changes. Every claim below was checked
in the file named; line numbers are from this tree. Parent requirement codes were read in
`../jana/docs/specification/`.

## 1. Verdict

**§20 (video): rework before building.** The product idea holds and most of the plumbing it names exists, but four
load-bearing claims are false in the code: the online-feature registry cannot hold a feature with no gateway service
(`net/policy.py:86,112`), there is no Study path that reads an image with a model (photos are OCR text from the
worker, `study_worker/__main__.py:45-61`), the companion's `study_search` cannot read an aid's `for_you`
(`memory/queries.py:626-630` reads chunks and session notes only), and "the gateway already sends the syllabus"
is a learner-uploaded syllabus file, not the pack (`engine/study.py:1137,1155-1157`). Two privacy rules are also
missing (the moment fence on cloud calls; where the video file actually leaves), and the embedded player has an
unproven dependency on the shell's origin that must be spiked on the packaged app before the week is committed.

**§21 (map): build with fixes.** The data the layers need is in the learner model and the UI scaffolding
(`ConceptMap.tsx`, `ConceptMapSvg.tsx`, `SubjectMap.tsx` "Map" mode, `ConceptMapController`) exists as described,
and a replay to a date is feasible within budget (the existing rebuild budget is 100,000 events in 10 s,
`config/keys.py:720-721`). Three things must change before coding: `map_opened_at` cannot be a `Settings` key
(every write is a synced `setting_change` learning event, `store/settings.py:100-107`), "Ask your tutor about this"
reuses `open_tutor`, which is the hand-off to the *guided* tutor, not the thread (§19.3.3, `companion.py:61`),
and freshness cannot come from `kc_mastery.last_seen_at` alone because Study activity never touches that table
(`projections.py:217,305`).

## 2. Blocking findings

### §20

**B1. A feature with `service: "none"` crashes policy resolution.** SPEC.md:2106-2107 registers `video_playback`
with "service `none`". `net/policy.py:86` does `self.services[environment][self.features[feature].service]`
and `:112` builds `hosts=(service_hosts[row.service],)` for every shipped feature; `layer.py:119-120` does the
same. A feature whose service is not a key of `services.<env>` raises `KeyError` on every `resolve()`, i.e. at
core start. **Fix:** add an explicit `"service": null` branch to `Feature`/`resolve` (hosts `()`), and state in
§20.3 that the shell's net module (`src-tauri/src/net.rs`) is *not* the enforcement point for this feature (the
webview's own iframe traffic is), so the CSP is the only gate.

**B2. The online-feature registration list is incomplete and will fail `dat18_matches_arc07_features`.**
SPEC.md:2106-2108 names the `scope` CHECK (`schema.sql:50-53`) but not the `online_features` CHECK
(`schema.sql:739-742`), nor `device_consents` (`schema.sql:792`), nor the `online_feature` enum in
`events.schema.json:189-203` (named only as "enums"), nor a TABLE DAT-18a row (parent `data-model.md`, the row
`dat18_matches_arc07_features` checks; §19.6 added one jana-meta-only row for `tutor_memory_online` and §20.6 adds
none), nor `OnlineFeatures.tsx`'s feature list and `PROFILE_SCOPES`' stage map (`consents.py:23-39`). **Fix:**
list every site, as §19.3 does, and add the DAT-18a row ("Video playback | nothing from Jana; the learner's
computer connects to YouTube | `video_playback` | `video_playback` | the player is a link | S2").

**B3. `study_frames` is a new table with no data-inventory or profile-store entry; CI fails.** SPEC.md:2099-2100
says "(storage)" and "a retention rule" but omits `scripts/governance/data-inventory.toml` (PRV-03 test
`prv03_inventory_covers_schema`, header lines 1-5 of that file) and `store/profile_stores.py` (§19.3 requires both,
SPEC.md:1526-1527). The "profile's image store" does not exist by that name: Study blobs live at
`self.root / "blobs"` (`engine/study.py:345,574`). **Fix:** name both files in §20.3; say frames are blobs in the
source's workspace under `study_revisions`-style cascade.

**B4. Frames cannot be screened "before they leave".** SPEC.md:2076 (JM-D34) and :2165-2166 say each frame goes
"through the perception worker's privacy pass before it leaves (MDL-23)" and §20.4 (SPEC.md:2122) points at
`engine/study.py:2375`. That line is inside `for unit in units if not cloud else []` (`:2371`): the *local* OCR
path. A recording is cloud-only (`:2362-2365` sets `waiting_online` when not cloud), so a video file is uploaded
whole under `study_materials` and frames are extracted at the gateway (`study_recording.py:24-58` runs the worker
on `buffer.data`). The privacy pass can run in the gateway worker (it already imports
`perception_worker.image.preprocess`, `study_worker/__main__.py:47`), but the picture has already left. MDL-23 is
about the vision slot and the per-photo pre-send notice, not a screening pass. **Fix:** rewrite JM-D34 and §20.6:
"the video file leaves whole, as recordings do; frames are extracted and screened in the sandboxed worker; a
screened frame is never read by a model and never returned to the device". Drop the MDL-23 citation or cite it
only for the pre-send notice, which Study does not have today.

**B5. There is no "image unit" path in Study; frames would be OCR text, not pictures read by Spark.**
SPEC.md:2066, :2123 ("the image path for frames (line 2003)"), :2155-2157 and the $0.19 in :2175. Gateway
`study.py:2003` is `if b.request["kind"] in ("pdf", "slides", "photo")`, the per-page *billing* branch of
extraction; a `photo` unit is OCR'd in the worker (`study_worker/__main__.py:45-61`) and reaches Spark as text.
`grep image_url|vision` in `cloud_gateway/study.py` finds nothing. **Fix:** decide (owner) whether frames are OCR
text (board and slide writing only; diagrams unread; cost ≈ $0) or a new vision call per frame (new gateway path,
new budget, new DAT-18 wording). The demo's "its board and slides read" is true of OCR; "the picture" is not.

**B6. The companion cannot read the outline's `for_you` through `study_search`.** SPEC.md:2152-2154 and the
done-when at :2187. `memory/queries.py::study_excerpts` (`:626-630`) selects from `study_sources JOIN
study_chunks` and `session_notes`; aids live in `study_aids.body` and are never searched, and §19.3.3 (SPEC.md:1602-
1605) fixes the tool to those two tables. `for_you` is also "code, uncited" (:2093), so it has no chunk to match.
**Fix:** either (a) extend `study_excerpts` to aid claims and `for_you` rows with a `kind: "aid"` excerpt and say so
in §19.3.3's amendment list, or (b) answer "what haven't I got yet" by code: `progress_read` already returns bands
(`SPEC.md:1606`), and the outline's `concepts[].kc_ids` are on the device; add the join to the engine, not the
model.

**B7. The "syllabus outline the gateway already sends" is a learner's syllabus file, not the pack.**
SPEC.md:2075 (JM-D33), :2122, :2186. `engine/study.py:1137` pops `settings.syllabus` (selected *sources*) and
`:1155-1157` sends their text as `syllabus_outline`; nothing sends the curriculum pack's skills, and the gateway
prompt treats the field as "scope only: never cite it" (`cloud_gateway/study.py:1160`). Since mapping and `skips`
are by code (:2122), the model never needs the pack. **Fix:** the outline request carries transcript chunks only;
drop "syllabus outline" and "the learner block" from :2122 and :2186 (the learner block is not used by the model
either: `for_you` is code on the device; sending it is egress without purpose, PRV-03).

**B8. "Ask about this moment" has no cloud rule and no place to live.** SPEC.md:2104-2105, :2127, :2148-2151.
The ±30 s lines are Study chunks; §19.6 (SPEC.md:1836-1838) lets Study text reach a cloud companion call only when
`study_materials` is effective, and `companion.py:618 strip_for_cloud` enforces it for `study_search`. §20 is
silent, so a naive build sends transcript text to Spark under `cloud_tier` alone. Also, `CompanionOpen` is
idempotent per day (`companion_episodes.profile_day UNIQUE`, SPEC.md:1578-1580) and the records fence is built per
*turn* in the user message (§19.5.1 step 3), so an open with `context` on an already-open episode has nowhere to
put the lines until the learner's first message. **Fix:** (1) the moment fence is subject to `strip_for_cloud`
exactly as `study_search` excerpts; a cloud-only candidate without `study_materials` gets the moment as a labelled
number only ("about 04:12 in <title>"); (2) the context is held in `companion_turn_context` (or memory) for the
episode's *next* accepted turn only and discarded after it; (3) name `companion-turn.schema.json` (`action.kind`
enum, `contracts/agents/companion-turn.schema.json:31-39`) and `resolve_action` (`companion.py:638-653`) for
`open_moment`, both missing from :2102 and :2130.

**B9. The transcript parser's input format is mis-stated and the title rule is false.** SPEC.md:2096-2097 ("`mm:ss`
or `h:mm:ss` then text, one line each") and :2137 ("the title is the paste's first line when YouTube included
it"). YouTube's transcript panel copies as *alternating* lines (a timestamp line, then the text line), with
timestamps as `m:ss` without a leading zero (`0:00`, `1:02:03`), interleaved chapter headings when the video has
chapters, and no title line. A parser written to the spec's one-line form rejects the paste the hint tells the
learner to make. **Fix:** specify both forms (same-line and alternating), `m:ss`/`mm:ss`/`h:mm:ss`, a heading line
(no timestamp, between two timestamped blocks) kept as a chapter title not a chunk, and a title asked of the
learner (prefilled "YouTube video <id>"); put a verbatim fixture in `test_w9_links.py`. Also cap at the
`Locator.time.maximum` of 7,200,000 ms (`workspace.schema.json` `$defs/Locator`): lines past 2:00:00 must be refused
or the bound raised, which also touches `Source.duration_ms` and `study_recording_max_minutes` (`config.py:413`,
`le=120`).

**B10. The CSP exception cannot be "per setting" as written, and the player may not play from the shell's origin.**
SPEC.md:2108-2110, :2129, :2189. Facts: Tauri 2 computes the CSP at asset-request time from the app config
(`tauri-2.12.2/src/manager/mod.rs:429`, header at `protocol/tauri.rs:182-183`); the config is mutable only before
`Builder::run` through `Context::config_mut()` (`tauri-2.12.2/src/lib.rs:438`), and `main.rs:345` holds the
context immutably today. So "at start" is feasible, but: (a) the shell does not read `online_features` (the device
DB is opened by the core; `grep online_features src-tauri/src` is empty), so the spec must name the handshake (a
marker file the core writes under the data home, read at `main.rs:345`); (b) `video_playback` has consent
`profile` (:2106) but a CSP is app-wide and fixed for the run, so the exception must follow the *device* switch
(`online_features.enabled`) and the player per-profile consent, and :2189 must say "while the device switch is
on"; (c) the IFrame Player API loads a script from `https://www.youtube.com`, which `script-src 'self'`
(`tauri.conf.json:25`) forbids and the spec hides behind "the player script's origin" (:2109); loading a
third-party script into the shell is a new invariant break. **Fix:** control the iframe with `enablejsapi=1` and
`postMessage` JSON commands (`seekTo`, `listening` → `infoDelivery` with `currentTime`) and change *only*
`frame-src`; no script. (d) YouTube refuses embeds whose request carries no `Referer` (player error 153); the
packaged app serves from `tauri://localhost` on macOS, whose referrer WebKit does not send. Tauri offers
`app.windows[].useHttpsScheme` (`tauri-utils-2.10.1/src/config.rs:2213`) which gives an `https://tauri.localhost`
origin. **This must be spiked on the packaged build, not `devUrl` (`tauri.conf.json:8`), before W9 is committed.**

**B11. Budget arithmetic.** SPEC.md:2174-2175 "about $0.78 an hour (60 segments at the reservation of line 83)".
`study_recording.py:84` reserves `Usage(ceil(seconds)*128 + 1024, 2048)` per segment = 8,704 input + 2,048 output
tokens; at `defaults.toml` prices (1.25 / 4.25 per M) that is $0.0109 + $0.0087 = $0.0196 per segment, **$1.18 an
hour**, not $0.78 (the settle is lower; the reservation is what the ledger must hold). The $0.19 for frames assumes
a vision path that does not exist (B5). The $0.05 for the outline is right (30k × 1.25 + 3k × 4.25 per M = $0.050).

### §21

**B12. `map_opened_at` as a `Settings` key writes a synced learning event on every map open.** SPEC.md:2279-2280,
:2306-2307. `store/settings.py:100-107` appends a `setting_change` event (`learning-event.schema.json`) with
`source="student"` and `hlc` for every changed key, and `settings` is in the DAT-18 "Whole-profile snapshot"
egress class (`data-inventory.toml` `[learner.settings]`). That contradicts JM-D37 "no new stored history"
(:2257) and JM-D27 device-local (:1512), and pollutes the log the scrubber replays. **Fix:** store it in the
device-local `app_settings` table (`schema.sql:803-807`, keyed `map_opened_at:<profile_id>`), or a column on
`companion_summary`-style operational state; no `Settings` contract change, no `settings` CHECK, no migration for
§21.

**B13. "Ask your tutor about this" reuses `open_tutor`, which opens the guided tutor, not the thread.**
SPEC.md:2248, :2281-2282, :2294, :2297, :2334. §19.3.3 and `companion.py:61` define `open_tutor` as the PED-01
hand-off that "opens a new ask session with the question" (SPEC.md:1166, :1733); the thread is opened by `POST
/v1/companion`. `ev_companion_action` is an *engine-emitted stream event during a companion turn*, not a UI
navigation, so putting a map button there is the wrong layer; and `payload.kc_ids` already exists
(`events.schema.json` `ev_companion_action.payload`; `companion.py:652`), so the proposed `kc_id` is redundant.
**Fix:** a client-side deep link (`App.tsx` `Screen`, as `open_tutor` is routed at SPEC.md:1719) to the companion
thread with a draft `About <statement>:`; no contract change. Also add the named test `companion-thread.test.tsx`
to §21.9 (the §21.8 bullet at :2334 has none).

**B14. Freshness from `kc_mastery.last_seen_at` misses Study activity and KCs with no mastery row.**
SPEC.md:2256 (JM-D36 "Freshness buckets from `last_seen_at`") versus :2303-2304 ("the newest of a skill's
attempt, hint, check, review or Study activity"). `projections.py:217` lists `study_activity` in
`NON_EVIDENCE_TYPES` and `:305` skips it in `MasteryProjection.fold`, so it never updates `last_seen_at`;
`kc_views` (`model.py:51-56`) iterates `kc_mastery` rows only, so a KC touched only in Study has no `KcView`.
Hints update `last_seen_at` only through a closed opportunity (`:409`). **Fix:** define freshness as
`max(kc_mastery.last_seen_at, newest study_activity with this kc in kc_tags)` computed in `engine/learn.py`,
not in `KcView`; say it scans `events WHERE type='study_activity'` (JSON `kc_tags`, no index) and is bounded by
the same 26 weeks.

**B15. `snapshot_as_of` needs a schema, not just a fold.** SPEC.md:2289. `Projector.replay_all`
(`projections.py:1242-1265`) deletes and refolds the projection tables of `self.conn` and reads `events` from the
same connection; there is no API that folds into another connection. Feasible, but the spec must say: create the
learner schema in `:memory:` (the generated `store/generated/schema`), copy `events` with `occurred_at ≤ ts`, build
`Projector(mem, params, content)` and `rebuild()`; copy every non-projection table a fold reads (at least
`profile`); prove read-only with `table_checksum` (`:1147`) of the live tables before and after, and prove
correctness by `snapshot_as_of(now)` equalling the live tables. Budget evidence: 100,000 events in 10 s on the dev
machine (`config/keys.py:720-721`, `test_m6b_events.py:419-431`), so 10,000 in 2 s is credible; cite it.

## 3. Non-blocking findings (by design impact)

1. **`video` kind by stream info contradicts kind-by-suffix at create.** SPEC.md:2076, :2122. The client picks the
   kind from the suffix (`study-workspace.ts:344-345`, mp4/webm/mov/mkv/avi → `recording`) and the core validates
   suffix per kind (`engine/study.py:507-515`) before any byte is uploaded; stream info arrives only from
   `recording_info` at the gateway. Decide: kind `video` by suffix at create, downgraded to `recording` in the
   `extracted` revision when `has_video` is false (a body rewrite the spec must allow), or keep one kind with a
   `has_video` flag. The worker also refuses a container with no audio stream (`media.py:25-26`), so "no audio
   stream: frames only" (:2156) needs a worker change the row at :2131 does not mention.
2. **Worker limits make 180 video minutes a week unreachable.** `__main__.py:24-28` caps the stdin line at 140 MB
   and the source at 100 MB; `study_recording.py:46-47` caps output at 4 MB per call and the whole file is re-sent
   on stdin for *every* 60 s segment (`:76`). A one-hour 720p lecture is typically over 100 MB, and 60 frames as
   base64 PNG exceed 4 MB in one reply. State: one `video_frames` call per frame batch with a byte cap; frames
   downscaled in the worker; `upload_max_mb` 200 (`plans.toml`) versus the worker's 100 MB must be reconciled;
   "scene changes" must be keyframe-only (the CPU rlimit is 240 s, `__main__.py:17`).
3. **`JobCreate.settings.frames` is the wrong seam.** SPEC.md:2088. Frames are an extraction-time decision on the
   source; `GenerateSettings` (`workspace.schema.json`) is per aid job. Put it on `SourceCreate` (file variant) or a
   profile setting.
4. **New route versus a `SourceCreate` variant.** SPEC.md:2095, :2121. `StudyDesk.create` already handles inline
   `text` (`engine/study.py:449-450`); a `{kind: "video_link", url, transcript, title?}` variant of the `oneOf`
   reuses `POST /v1/study/sources`, the client's `addSource`, redaction (`:456`) and the `source_added` activity.
   A separate `/sources/link` duplicates all of it.
5. **`StudyCitation.tsx` is not in §20.4** though `Locator` gains `frame` (:2087): the label chain at `:24-33`
   handles page/slide/time/note/text only; `StudyCitations` grouping (`:49-57`) too.
6. **`teaching_outline` must also enter `JobKind`** (`workspace.schema.json` `$defs/JobKind`, separate from
   `AidKind`), the gateway's `GRANULAR_KINDS` (`cloud_gateway/study.py:654`) for per-claim support, and the
   `allOf` kind→field rule on `Aid`. §20.3 names `AidKind` only.
7. **`kc_tags` is word overlap with KC statements** (`study_topics.py:57-80`, ≤ 3 KCs). "Maps the range concept
   to its skill by code" (:2185) depends on the physics pack's statement wording containing "range"; seed and check
   the fixture before promising it in the demo (:2211). `skips` "skills absent from the whole transcript" needs a
   stated rule (which words of a statement must appear); as written an engineer cannot implement it.
8. **Fact binding on timestamps.** `_NUMBER` (`companion.py:15`) is `(\d+(?:\.\d+)?)` with a `[\w.]*\d` lookahead:
   "04:12" yields "04" then "12" as two numbers with no unit word, so every reply naming a moment fails the gate
   unless the tool result carries the same tokens beside the same words. Define the timestamp as a labelled fact
   (`companion_facts`) and exempt `hh:mm:ss` tokens from `labelled_numbers`; `test_w9_companion_moment.py` must cover
   it (the spec says "fact binding on the timestamp" without saying what passes).
9. **`study_search` locators live in the engine, not `events.schema.json`.** SPEC.md:2103 puts "`study_search`
   result items gain `locator`" under the events contract; the tool's shape is `toolsets.json` and
   `memory_tools.py:256`. Also `StudyExcerpt` has no locator today (`queries.py:649`).
10. **Mistakes layer omits `disputed`** (`schema.sql:323`, LRN-37's "This isn't right"); SPEC.md:2245 lists four
    statuses, the contract has five (`ConceptMistake.status` lacks `disputed` too, so the engine already drops them:
    say so).
11. **`changed_since: "down"` is nearly unreachable.** `BANDS` map `needs_review` to `secure` (LRN-34), so a band
    falls only by correction, re-mark or KC migration. Drop "down" (it is also the one LRN-35-sensitive word in the
    layer) or define it on state, not band.
12. **The "Your tutor" layer covers at most six skills.** `companion_summary.topics ≤ 6` (SPEC.md:1584); every
    other skill shows 0 "thread sessions", which reads as a fact about the learner. Either count from
    `companion_turn_context`/turn tool results or label the layer "topics your tutor is tracking".
13. **Study-layer `cards_due` per KC has no source for unreviewed cards.** Flashcards are tagged only through
    `card_review` activity (`SPEC.md:1553`); a due card never reviewed has no KC. Say "cards reviewed at least once"
    or compute `kc_tags` over the deck at read time.
14. **The existing map's `state` is stale by design** (`engine/learn.py:148-150` reads `kc_mastery.status`, not
    `kc_views` at now); `fading`/`due` from `KcView` will disagree with `state` on a decayed card. Either move the map
    to `kc_views` (one line) or document the difference. `fading` is then just `state == "needs_review"`.
15. **Overview tiles should follow TABLE UXS-22a** (first matching rule, icon and pattern), not "filled by band"
    (:2244, :2295), to match the parent's subject map and DSN-04.
16. **Ring word "on hover"** (:2293) is not available on touch; :2313 already requires the word in the box label and
    table, so delete "on hover".
17. **Shared `migration_v23`** (:2280) couples two separate weeks; whichever lands second takes v24. `migration_v22`
    is the latest (`store/sqlite.py:39`), so v23 is right for whichever is first.
18. **Scenario loader is W8-only.** `w8_scenarios.py:26` globs `tests/scenarios/w8/` and dispatches by hand-written
    `_case` functions (`:43-333`); `scenarios/w9/...` and `scenarios/w10/...` (:2208, :2346) need a generalised
    `CASES` and a handler each, and `evals/suites.toml:120-126` lists `companion` as W8. The YAML shape (`case`,
    `rubric`, `expect`) is consistent.
19. **Done-when without a test.** §20.8 "a quiz citing mm:ss · on screen" has no named assertion in
    `test_w9_video_file.py`; §21.8 "a note citing a skill's events appears as a pin and opens the knows page" and
    "a Study material … opens" have no UI test; "no probability appears anywhere" is tested over `ConceptMap` only
    (:2340) — add `CurriculumOverview` and `KcLinks`.
20. **Notice wording.** "YouTube sees that this computer played the video and when" (:2074) should add "and its
    internet address", as the `downloads` row of DAT-18a does for the same class of fact.
21. **A pasted transcript of someone else's video.** STU-22's design note (`study-area.md:393-394`) says "Fetching
    transcripts of other people's online videos waits for D64"; pasting is not fetching, but the spec should say so
    in one line (the learner's own copy for private study, never shared, never in packs), because §20.6 is silent.
22. **Privacy wording.** `PRV-10` (:2319) is the access/deletion right, not a data class; the knows view's classes
    are LRN-36/MEM-14/UXS-28 (`memory/view.py:1`). `DAT-18`'s `transcript` class is voice (`policy.json:75,86`);
    pasted text is `document`. `image` for frames is right.
23. **Style.** Sentences an engineer cannot act on: :2122 "`skips` from the matched topics' skills absent from the
    whole transcript"; :2146 "a change of topic by the chapters aid" (which aid runs when?); :2290 "`study`, `notes`,
    `thread_sessions` counts per KC from … frame and transcript tags" (no such tag table exists; §20 stores
    `study_frames.text`, not tags); :2293 "five fill steps with a pattern per step" (name the DSN pattern tokens);
    :2311 "mid hardware class" (name EVL-14's class). Otherwise both sections read like §18/§19: decisions in a
    table, each change with a file.

## 4. Wrong references

| Cited (SPEC.md) | Actual |
|---|---|
| `study-workspace.ts` `recordingBytes` (:2124) | `loadMedia()` at `packages/client-core/src/study-workspace.ts:282-290`; `media()` at `engine/study.py:1732-1743` |
| `tauri.conf.json` line 23–31, `frame-src 'none'` (:2108) | CSP block is lines 23–35; `frame-src` at line 31; `script-src 'self'` at line 25 is the one that blocks the player script |
| `study_recording.py` line 83 reservation (:2175) | line 84 (`bound = cost_usd(...)`); 83 is the comment |
| gateway `study.py` line 2003 "image path" (:2123) | the `pdf/slides/photo` page-count billing branch of `extract`; no image-reading path exists |
| `engine/study.py` line 2375 `self.perception` for frames (:2122) | local OCR path inside `if not cloud` (`:2371`); recordings are cloud-only (`:2362`) |
| "the gateway already sends [the syllabus outline]" (:2075) | a learner-uploaded syllabus *file*'s text (`engine/study.py:1137,1155-1157`), never the pack |
| `study_search` reads an aid's `for_you` (:2153) | `memory/queries.py:626-630` reads `study_chunks` and `session_notes` only |
| `events.schema.json`: `study_search` items gain `locator` (:2103) | tool shape is `contracts/registers/toolsets.json` + `memory_tools.py:256` |
| `open_tutor` payload gains `kc_id` (:2281-2282) | `payload.kc_ids` exists (`events.schema.json` `ev_companion_action`; `companion.py:652`); `open_tutor` is the guided-tutor hand-off, not the thread |
| `Home.tsx` "What moved today" (:2296) | `MovedToday` lives in `packages/ui/src/progress/Progress.tsx:66-90`; `Home.tsx` has no such block |
| `Settings` gains `map_opened_at` with the settings CHECK (:2279) | writing a setting appends a `setting_change` event (`store/settings.py:100-107`); use `app_settings` (`schema.sql:803`) |
| "the profile's image store" (:2100) | Study blobs at `<profile>/blobs` (`engine/study.py:345,574`) |
| JM-D36 "Freshness buckets from `last_seen_at`" (:2256) | `kc_mastery.last_seen_at` is written by opportunities only (`projections.py:305,409`); Study activity is `NON_EVIDENCE_TYPES` (`:217`) |
| Mistakes statuses "watching, active, resolving, resolved" (:2245) | `schema.sql:323` also has `disputed`; `ConceptMistake.status` enum is `suspected, active, resolving, resolved` |
| `MDL-23` as the frames' privacy pass (:2076, :2165) | MDL-23 is the vision slot and INP-20 pre-send notice (`model-router.md` MDL-23); the pass is `perception_worker.image.preprocess` refusal |
| `PRV-10` as the knows view's data classes (:2319) | PRV-10 is access/correction/deletion; the view is LRN-36/MEM-14/UXS-28 (`memory/view.py:1`) |
| `transcript` data class for pasted text (:2164) | `transcript` is voice/recording (`policy.json:75,86`); pasted text is `document` |
| Transcript panel "mm:ss then text, one line each"; title in first line (:2096, :2137) | panel copies as alternating lines, `m:ss` without leading zero, chapter headings interleaved, no title |
| `scenarios/w9/`, `scenarios/w10/` in suite `companion` (:2208, :2346) | loader globs `tests/scenarios/w8/` only (`w8_scenarios.py:26`) |
| `StudyGenerate.tsx` line 153–176, `<video>` at 162 (:2039, :2126) | correct (`RecordingPlayer` 143–190, `<audio>` at 162) |
| `StudyCitation.tsx` line 25; `api/learn.py` line 74; `App.tsx` line 215; `model.py` line 77; `study_recording.py` `transcribe` line 61; `sqlite.py` v22 latest → v23 next | all correct |

## 5. Owner-only questions, with a recommended answer

1. **Frames: OCR text or a model's eyes (B5)?** Recommend **OCR text in the worker for W9** (board and slide
   writing, cited "mm:ss · on screen", cost ≈ $0, no new DAT-18 wording) and defer vision reads of frames to a
   later decision with its own budget. Rewrite :2066, :2155-2157, :2175 and the demo accordingly.
2. **Player control without a YouTube script (B10c)?** Recommend **yes**: iframe + `postMessage`, `frame-src`
   only, `script-src 'self'` unchanged. Loading `www.youtube.com` script into the shell is a new trust decision
   that deserves its own JM-D if ever wanted.
3. **Shell origin spike (B10d).** Authorise a half-day spike on the packaged macOS build: does the
   `youtube-nocookie.com` embed play from `tauri://localhost`, and if not, does `useHttpsScheme: true` fix it
   without breaking the core's loopback (`connect-src` at `tauri.conf.json:26`)? If neither, JM-D31 falls back to
   "Watch on YouTube" opening the browser, and the week's value is the outline and the moment-seeking transcript.
4. **Where does the CSP flag live (B10a-b)?** Recommend: the core writes `<data_home>/video_playback` when the
   *device* switch is enabled and removes it when disabled; the shell reads it at `main.rs:345` and mutates
   `context.config_mut().app.security.csp`; the Settings line says "takes effect when Jana restarts"; the
   per-profile consent gates the player, not the CSP.
5. **Does the outline request carry the learner block and the pack skills (B7)?** Recommend **no**: transcript
   chunks only; bands and skills are joined on the device. Smaller prompt, less egress, nothing lost.
6. **"What haven't I got yet" by tool or by code (B6)?** Recommend **code**: a `study_outline_read` handler is
   unnecessary; the engine answers the question as a typed fact set (as `companion_facts` does for the opener),
   and the companion phrases it with `fact_refs`. Fits §19.5.1's "every number from a tool result".
7. **Should "Ask your tutor about this" open the thread or the guided tutor (B13)?** The spec's intent is the
   thread. Recommend the thread, by client deep link with a draft, no event; keep `open_tutor` as PED-01's hand-off.
8. **Is a pasted third-party transcript acceptable under STU-22's D64 note?** Recommend **yes, with one sentence
   in §20.6**: it is the learner's own copy for private study, held in their profile, never in packs or research
   export, and D64 is unchanged because Jana fetches nothing.
9. **`video_minutes_per_week` or per month?** `plans.toml` meters `recording_hours_per_month`; a per-week video
   limit beside a per-month recording limit is two clocks for one kind of thing. Recommend `video_minutes_per_month`
   drawn from the same 10-hour pool, and raise the worker's 100 MB source cap or state the real file limit.
10. **Map-first Progress (JM-D35).** No code objection; the only cost is LRN-34's "reflection block lists the bars
    that moved today" moving below the hero. Recommend keeping `MovedToday` as the first thing under the overview
    and letting it outline the moved skills on the map, as :2244 says.
