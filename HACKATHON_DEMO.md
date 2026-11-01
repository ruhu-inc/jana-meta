# Jana: three-minute learning-agent demo

Draft for rehearsal, updated 1 November 2026 for the build tagged `demo-2026-11-01` (commit `4ccd5c4c`). This is a
recording script, not a completed video, and the whole storyboard below has not yet been rehearsed end to end.
Use a synthetic adult learner and the stable build. Show only the app window. Keep credentials and real profiles
out of the recording. Retain the original recording so any cuts and elapsed-time captions can be checked.

One learner, Ada (an invented adult, O level Physics), works on **projectile motion**: a short practice run, the
Companion telling her what she has not got yet from her own record, a YouTube lecture turned into a teaching outline,
and the learner's map showing where it all sits. The subject is the Physics pack's subtopic "Projectile motion"
(PHY-O-01.09, pack 1.1.0, six skills in `content/curriculum/phy/o/kcs/projectiles.yaml`). What is new since the
31 October draft: the Companion's progress, plan and aid tools (SPEC §19), a YouTube lecture as a Study source (§20)
and the learner's map (§21). The memory-and-restart sequence of the earlier draft moves to the supporting walkthrough.

Which model does what, as the spec states it (the README table has the full list):

| Model | Where | Used in this storyboard |
| --- | --- | --- |
| Muse Spark | Meta Model API, through Jana's gateway | Guided tutor turns, the Companion's wording and tool use (§19.7 prices the companion turn at the `fast-model` alias), the teaching outline and its verifier (§20.7: `strong-model` plus verifier) |
| Muse Glimmer 30B | The laptop, llama.cpp, only with `--local-model` | The same tutoring and Companion turns when the cloud is off or unreachable |
| SAM 3.1 | Meta Model API, through the gateway | Not used: no photo or diagram appears in this storyboard |
| Kokoro-82M | Local speech pack | Not used: the storyboard is typed, with no spoken reply |
| No model | The device | Answer checking (the sandboxed maths worker), the lecture's mapping to skills and Ada's bands, the whole learner's map and its time scrubber (§21.7: $0, nothing leaves the device) |

## Storyboard

| Time | Beat | Screen |
| --- | --- | --- |
| 0:00–0:15 | Opening | Home, Demo Ada |
| 0:15–0:55 | A short practice run | Learn, Physics, Projectile motion |
| 0:55–1:25 | The Companion: what haven't I got yet | Study, Your tutor |
| 1:25–2:15 | A YouTube lecture, understood | Study, Add a YouTube video |
| 2:15–2:50 | The learner's map | Progress, My map |
| 2:50–3:00 | Close | Progress or Your tutor |

**0:00–0:15, opening.** *Screen:* Home with the synthetic Demo Ada profile (O level Physics). *Learner action:* none.
*Tutor shows:* the code-built Last time card (SPEC §19.1), if the profile has an ended session to name; a new profile
sees the first-time card. *Model:* none; the card is code, every number beside its label. *Narration:* “Adult learners
returning to exam preparation need a tutor that knows what they have and have not got. We extended Jana during this
hackathon with a Study companion, lectures from YouTube, and a map of the learner's own knowledge, built on Meta models.”

**0:15–0:55, a short practice run.** *Screen:* Learn, then Physics, then Projectile motion. *Learner action:* start
practice on the subtopic and answer one checked question, for example item 0007 (a stone thrown at 15 m/s at 40°; how
far does it land; the pack's answer is 22.6 m) by giving the maximum height, about 4.74 m, in place of the range; then
ask for a hint and correct it. *Tutor shows:* the answer marked by code, the hint ladder (authored hints; with cloud
tutoring on, the guided tutor asks where she is stuck), and the pack's “Range and maximum height mixed up”
misconception named as a watched mistake only if the engine recorded it. *Model:* the marking is the sandboxed maths
worker, not a model; with consent on, the guided tutor's Diagnoser and Coach run on Muse Spark through the gateway,
and on Muse Glimmer with `--local-model` when the cloud is off. *Narration:* “Every number is checked by code before
the tutor says it. A wrong answer here is the classic one: range mixed up with maximum height.”

**0:55–1:25, the Companion.** *Screen:* Study, then **Your tutor**. *Learner action:* type `What haven't I got yet?`.
*Tutor shows:* an answer built from Ada's own record (SPEC §19.5, §19.3.3): the Companion reads progress with its
`progress_read` tool, and each progress statement is bound to a code-built fact with its value and source; the app
renders the statement with its source and offers **What your tutor knows** for inspection. Reading a lesson or a Study
quiz alone is not a mastery claim (JM-D26). *Model:* Muse Spark through the gateway phrases the answer and chooses
tools; Muse Glimmer does it locally with `--local-model`; the facts are code. *Narration:* “The numbers come from
Ada's record, not from the model. She can open what the tutor knows, and see where each claim came from. Memory stays
on this computer unless she turns on the separate online-memory consent.”

**1:25–2:15, a YouTube lecture, understood.** *Screen:* Study, **Add a YouTube video** (fields: “Link to the video” and
“Its transcript”). *Learner action:* paste the lecture's link, paste its transcript copied from YouTube's panel (the
screen shows the three-step hint), keep the title “YouTube video” or rename it, press **Add video**; then press
**What this video teaches**, tap one **Open at m:ss** button; then in **Your tutor** type `What does this video teach
that I haven't got yet?`. *Tutor shows:* the transcript with its chapters and an **Open at m:ss** on every line
(nothing is downloaded and no player is embedded); after a short wait the teaching outline: objectives with their
moments, worked examples, concepts, “Assumes you know”, “Not covered here”, and “For you” with Ada's band on each
skill (not started, learning, secure); concepts tagged to the pack's projectile skills rather than “outside the packs”.
The Open-at tap opens `youtube.com/watch?v=<id>&t=<seconds>` in the browser. The last question is answered from the
outline's skills and Ada's bands, each with the moment it is taught at. *Model:* the outline is one Muse Spark
structured call over the transcript chunks only, then Study's verifier drops uncited statements (SPEC §20.5, §20.7,
estimated $0.05); the mapping to skills, the skipped skills and Ada's bands are code on the device, and the request
carries no learner data. The closing answer is phrased by Muse Spark (Glimmer offline) from code-built facts.
*Narration:* “Ada pastes a link and the transcript. Jana reads what the lecture teaches, cites a line for every
statement, and compares it with what Ada already knows. The moments open the video in her browser: there is no
embedded player in this release.” Read the counts and moments off the screen; the spec's example figures (four
objectives, six concepts, 06:40 and 08:15) are not a promise of what the live lecture produces.

**2:15–2:50, the learner's map.** *Screen:* Progress, which opens on **My map**. *Learner action:* tap the Physics
tile; switch the layer control (Mastery, Freshness, Mistakes); drag **See the map as it was** back and return to
**Today**; open one projectile skill's sheet. *Tutor shows:* every installed subject as topic tiles, then Physics'
skill map with the projectile skills; skills that moved since the map was last opened outlined “Up since last
time” or “New since last time”; the Freshness layer (practised today, this week, this month, longer ago, not
practised yet); the Mistakes layer ringing the watched misconception with its word; the scrubber replaying the learner
model read-only as of an earlier date (“Nothing here changes your progress”); the skill's sheet listing its Study
material and the lecture moment, cards due, what the tutor noted, and **Ask your tutor about this** (it opens the
thread with a draft and sends nothing). *Model:* none; this screen makes no model call and sends nothing off the device
(SPEC §21.6, §21.7, JM-D39). *Narration:* “The map is Ada's own record, drawn by code. Words and patterns, never a
probability, and a skill she has not met is ‘not yet’, not a warning. The scrubber replays her log to an earlier date
and changes nothing.”

**2:50–3:00, close.** *Learner action:* none. *Narration:* “The map, the memory and the lecture outline stay on this
computer; the cloud model gets only what Ada has consented to. We are demonstrating continuity and evidence-backed
adaptation, not claiming measured improvements in exam scores.”

Use the actual observed model name in captions. Do not label code output (marking, mapping, the map, a deterministic
memory acknowledgement or the code-built fallback line) as a model response. Only use a checked question, lecture and
model interaction already rehearsed successfully. If the sequence runs long, keep practice → Companion → lecture
outline → map, and cut the Open-at tap, the follow-up question and the skill sheet.

### Things the setup must provide

- **The pack.** Pack 1.1.0 (with Projectile motion) must be the one installed in the demo profile's data folder. A
  folder seeded earlier has an older Physics pack and the lecture's concepts will show “outside the packs”. Check that
  Learn lists Projectile motion before recording.
- **A baseline for “since last time”.** The map marks only skills whose band rose or appeared since the map was last
  opened, and the first open marks nothing (SPEC §21.5). Open Progress once before the practice beat, then again in the
  map beat.
- **Dates for the scrubber.** It offers weekly dates from the profile's first learning event, at most 26 weeks. A
  profile created for the recording has no date four weeks back, and the machine clock must not be changed to
  manufacture one. Either use a profile that genuinely has older history, or show the control and describe the
  four-weeks-ago view from the labelled simulated regression (`services/agent-core/tests/scenarios/w10/map_month_later.yaml`, suite `learner_map`). Decide before recording; do not caption a short replay as a month.
- **The lecture.** Choose one YouTube lecture on projectile motion with a transcript and rehearse it; its link is not
  stored in the repository. The transcript is the learner's own private copy and is never fetched by Jana (JM-D43). A
  paste without timestamps is saved as text and has no moments (so no **Open at**). Only YouTube links are accepted,
  and a transcript running past two hours is refused. `services/agent-core/tests/fixtures/w9/youtube_panel_projectile.txt`
  shows the paste format; it is a test fixture, not a recording of the real lecture.
- **Consent.** The outline and the Companion's cloud turns need the owner's consents on the Demo Ada profile (cloud
  tutor, and online Study materials for the transcript to leave the device). Personal tutor memory online is a
  separate switch, off by default; leave it off unless the narration says otherwise.

## Rehearsal and fallback

Evidence to date, from SPEC §19 to §21: the 29–30 October live runs of the Companion were fixed and re-tested against
the gateway; W9 and W10 were run live in the browser host on 31 October and the fixes of 1 November (transcript
layout, the outline's job label, sparse-transcript chapters, the code-built “what haven't I got yet” line, the
gateway-version check and the outline's skill mapping) each have a test. W10 had no in-browser check when it was
first built; its map was checked through the component and renderer tests. No complete rehearsal of the storyboard above
is recorded. See `LEARNING_AGENT_REVIEW.md` for the earlier Companion evidence and its limits.

1. Start this repository's gateway before the app, within its existing durable budget. In `.claude/launch.json` the
   gateway is `meta-gateway` on port 8082 and the host `demo-host` reads `JANA_META_GATEWAY_PORT=8082`; the debug pair
   is port 8083. The README flow uses port 8081 (the engine's default when the variable is unset). The port in the
   variable and the gateway's port must match. Enable online tutoring only with consent.
2. **Check the gateway version before the app.** The browser host's engine process (`jana_tools.hackathon_app`) calls
   `check_gateway` when it connects and refuses to start unless the gateway on that port answers `/v1/ping` with status
   204, a `jana-gateway-version` header equal to this repository's version (**1.2**) and `x-jana-inference-budget:
   enabled`. Reason: the parent project's gateway also served 1.1, so a gateway from another project on the shared port
   answered the ping and every new job kind then failed with `processing_failed`. To check by hand:
   `curl -i http://127.0.0.1:<port>/v1/ping`. If the check fails, the error names the port and the version found
   (“none” if the header is missing) or says no gateway answered; stop the other process, start this repository's
   gateway on that port, and relaunch the host. Do not work around it by editing the check.
3. Launch `uv run python -m jana_tools.hackathon_dev --stable --port 5197 --data-dir /tmp/jana-demo`.
   For local inference add `--local-model /path/to/Muse-Glimmer-30B-KQuant-17GB-Q4_K_M.gguf`.
4. Create only invented adult profiles. Preinstall packs and models; do not spend the video downloading them.
5. Run the storyboard without recording. Confirm every reply finishes, every button works, and every personalized
   statement has the right source. Confirm the Companion's answer in beat 3 is the model's phrasing of code facts, not
   the canned line. Restart the actual core as well as the browser during the supporting rehearsal.
6. Record a successful real-provider run with readable captions, then keep a local copy as the presentation fallback.
   Cut idle waits only with an honest elapsed-time caption. Never substitute scripted output for a failed model call.
7. Play the exported video from beginning to end, check the duration is at most three minutes, and check audio and
   caption legibility. Test the shared link without the owner's login before submitting it.

**Risks the spec names, and what to show.**

- **No embedded YouTube player.** The official player does not play in the packaged macOS app: YouTube refuses the
  `tauri://localhost` origin with error 153 (SPEC §20.2, JM-D42, from a spike recorded on another branch). **Watch on YouTube** and every
  **Open at m:ss** open the learner's own browser, as a research pack's sources do. Say so in the narration and do not
  imply playback inside Jana. Whether the packaged desktop app's webview opens that link in the system browser is
  unverified (SPEC §20, “The external-link opener”), so record from the browser host, and check the link opens
  before relying on it. Opening YouTube also needs the network; if it is unreachable, show the Open-at button and
  the URL it opens, and say the video itself did not load.
- **The wrong gateway on the port.** See step 2. In the recording, a failed check is a preflight, not a demo beat:
  fix it before recording and keep the rehearsal notes.
- **The cloud model is unreachable.** Offline, the router serves every call on the local model and the connectivity
  layer keeps probing, so the cloud tutor returns when Meta can be reached again. With `--local-model`, show the
  practice run and the Companion on Muse Glimmer (label it so; slower, and answers are not word-for-word the same), the
  map and its scrubber (no model at all), the pasted lecture's transcript, chapters and **Open at** links (parsed on
  the device; nothing downloaded), and an outline generated during rehearsal and kept in the profile. A new outline is a
  cloud call (SPEC §20.7) and the spec describes no local path for it, so say it needs the cloud model rather than
  pretend. Without a local model, saved history, the map and authored practice still work and ordinary AI conversation
  does not.
- **A Companion reply refused by the checks.** If its wording fails fact binding twice, the learner sees a code-built
  line from the facts (“Of this video's N skills, N are not yet secure: …” after an outline; a made aid is named from
  its result) rather than the canned “couldn't put that together” line. That is correct behaviour; caption it as code,
  not as Muse Spark.
- **Prerecorded fallback.** If the network fails live, use the verified local-model path or show the prerecorded run
  with a clear “recorded earlier” label. If no verified recording exists, show the map, saved memory and authored
  practice and state that online inference is unavailable. A storyboard is not a fallback video.

Budget, from the spec's estimates (not measured bounds): a typical Companion session about $0.11 (§19.7), the outline
about $0.05 (§20.7), the map $0. The Companion's caps are `companion.per_day_usd = 0.50` and
`companion_turns_per_day = 60`, enforced by the gateway's ledger. The gateway's allowances are shared across an
account's profiles (JM-D30).

The earlier Companion rehearsal (30–31 October) used the isolated Demo Ada profile at `http://127.0.0.1:5197/` with
`/tmp/jana-learning-agent-live-demo-20261030`, and real Muse Spark Study and guided tutor calls completed. Saved content
still works offline. An agreement made locally is not automatically available to the online tutor under the current
permissions; use an agreement made during the online conversation for an online continuity demonstration.

## Supporting acceptance walkthrough

Record separate evidence for each item. Use the regression tests for simulated days and label them as simulated.

Companion, memory and restoration (from the earlier script): saved preference (`Remember that I prefer short
explanations.`); study and checked attempt; core restart; continued agreement; corrected preference (`Actually, I
prefer hints first.`); forgotten memory absent from future recall; encrypted export and restoration; profile B
isolation; return to A; explanation sources (What your tutor knows). The default profile export does not promise raw
chat history; test the separately authorized archive path when claiming transcript restoration. Do not change the
machine clock to manufacture a multi-day live demo. The simulated three-day journey is
`test_learning_agent_journey.py`.

YouTube lecture (SPEC §20.8, tests in §20.9): each accepted link form yields the id and any other link is refused with
the message; the panel fixture parses to timed chunks and chapters, a same-line transcript too, a no-timestamp paste to
text, and a paste past two hours is refused; an **Open at** tap opens `youtube.com/watch?v=<id>&t=<s>` through the
app's external-link opener; a `teaching_outline` on the seeded projectile transcript lists cited objectives, examples
and concepts, maps the range concept to its skill and shows the learner's bands; the outline's cloud request carries
transcript chunks and nothing else; “what haven't I got yet” answers from the code fact set (`test_w9_*`,
`services/agent-core/tests/scenarios/w9/youtube_lecture.yaml`).

Learner's map (SPEC §21.8, tests in §21.9): Progress opens on the overview with each tile's rule, bands and freshness
equal to the subject map's; the layers show their words in the box labels and the table; a disputed misconception is
ringed with “You said this isn't right”; the first open marks nothing and no learning event is written by opening
the map; the scrubber's dated map equals the bands the model had then, `snapshot_as_of(now)` equals the live tables
and their checksums are unchanged; a date over 26 weeks back is refused; no probability appears in the map contracts
(`test_w10_*`, `services/agent-core/tests/scenarios/w10/map_month_later.yaml`).

The build tagged `demo-2026-11-01` is the reference for all of the above.
