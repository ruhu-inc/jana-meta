# Jana: three-minute learning-agent demo

Draft for rehearsal. The recording script is now the section "Storyboard, 2 November build" below, walked live on the night of 1 November on the build after commit `7844132a` (the one that adds the provenance line). The 1 November storyboard that follows it was written for the build tagged `demo-2026-11-01` (commit `4ccd5c4c`). This is a
recording script, not a completed video. It was walked once live on 1 November, through every beat except the time
scrubber, which has no earlier date on a new profile; see “Live walk-through, 1 November” below, which also corrects
the screen names and steps.
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

The event requires the demo to distinguish what was built during the hackathon (from 26 October) from the existing
product; `HACKATHON_SUBMISSION.md` lists the event work in full. Caption each beat. New in the event: Muse Spark and
Muse Glimmer as the tutor, the Projectile motion subtopic, the Companion, the YouTube lecture outline and the learner's
map. Existing foundation: the checking worker, the hint ladder and the Study desk the new features sit in.

## Storyboard, 2 November (later): any material, for a university student

This is the recommended recording script. It shows the widest use of Muse Spark online and the broadest audience, and
it needs no curriculum. Every time below was measured live on 2 November against this build, on a new learner, with
a synthetic six-page lecture (Intermediate Microeconomics, monopoly). Bring a real lecture of your own if you can.

| Time | Beat | Screen | Measured |
| --- | --- | --- | --- |
| 0:00–0:20 | New learner: name, age, **My own course and materials**. Straight to Home: no syllabus, no lessons in the sidebar | First run, Home | 4 s to Home |
| 0:20–0:45 | Add material: the lecture PDF. "Ready to study", no review step, page images beside the tools. Mention the same path took a 1,000-page PDF | My materials | under 12 s; 1,000 pages under 23 s |
| 0:45–1:10 | One press of **Summary**: cited page by page, maths rendered, "Made online with Muse Spark, then checked against your material." | Generate | 21 s |
| 1:10–2:10 | **Quiz** with Number or expression, Fill in the blank and Written answer. Answer a blank with "MR": **Correct** (an abbreviation, marked online, not a string match). Write a wrong explanation: **Incorrect**, no answer shown. Correct it: **Correct**. The numeric question: "Q = 20" **Correct**. **Finish quiz**: 4 of 4, then **Retake quiz** exists | Generate → Settings: Quiz | 25 s to make, 3–9 s per answer |
| 2:10–2:40 | **Your tutor**: "Why does a monopolist never operate on the inelastic part of demand?" A grounded answer that ends with a guiding question | Your tutor | 12 s |
| 2:40–3:00 | Close on the two-model line: online with Muse Spark, private on this computer with Muse Glimmer. Optionally a glance at the O-level learner's map to show the curriculum depth is still there | Spoken | none |

Tick **Written answer** and **Number or expression** and untick the others in the quiz settings before Generate. Make
the quiz before recording if you would rather cut the 25 s; the tutor and marking are fast enough to show live.

After a quiz, three things now carry on from it. **Help with this question** on a lecture question gives a tailored, cited hint
rather than the fallback sentence. **Progress** lists "Practised in Study today" with **Check this idea** when a real
check can run, or **Practise this idea** when it cannot yet. A saved quiz has **Retake quiz**. A window narrower than 1180 px
opens a material on the study tools, with **View source** and **Study tools** to swap sides.

A reliability run on 2 November put 30 generated files through upload, summary and quiz with Muse Spark, plus the real
machine-learning notes. After fixes, every readable file gave a summary and all but one gave a quiz. The exception was
a tiny notebook, refused as too little to test. Corrupt, encrypted, blank and speechless files were refused. These are
varied test files, not students' own documents.

| Size | Example | Time, summary and quiz | Meta cost |
| --- | --- | --- | --- |
| A few pages | Lecture notes | 20 s | $0.03 |
| 69 pages, heavy maths | Machine-learning notes | 100 s | $0.34 |
| 117 pages | Long history text, sampled | 290 s | $0.84 |

Rough edges still to know about: a marking the judge and the separate check disagree on says **Not marked** and shows
the explanation; a long source with no focus reads 24 sections spread across it and says so; research still asks the
level as a quick reply. PDF formulas come from the text layer, so a heavily mathematical PDF can read badly in the
source pane, though the page image beside it is always right.

## Storyboard, 2 November build: one lecture, fully learned

This replaces the 1 November storyboard below as the recording script. It was walked live, beat by beat, on the night
of 1 November against this repository's gateway (version 1.2, port 8081, restarted on the current code) and the
stable host on port 5197 with the Demo Ada profile in `/tmp/jana-demo`. Every count, time and sentence below is what
the screen showed; the model was Muse Spark (`muse-spark-1.3`) through the gateway for every generated piece.

What is new in this build and why it matters for the judges: **every generated study aid now says which model made it
and where.** The aid record carries `made_by` (`online` or `device`, plus the model id the gateway or the device
reported), and the screen shows one line under the aid's title: "Made online with Muse Spark, then checked against
your material." A research pack says "Researched online with Muse Spark: a web search, then every statement checked
against the page it cites." Aids made before this build have no line. Nothing is inferred by the client; a gateway
that does not name a model gives "Made online, then checked against your material."

| Time | Beat | Screen | Muse Spark at work |
| --- | --- | --- | --- |
| 0:00–0:15 | Opening: Home leads with Continue learning, "Find the time of flight of a projectile from the vertical motion", Learn · Practise · Check | Home | none, code |
| 0:15–0:50 | The lecture, understood: open the projectile lecture (the only YouTube video left in the library), then the saved **What it teaches** of 2 November, 4 objectives, 3 worked examples, "Made online with Muse Spark, then checked against your material." | My materials → YouTube video → My Sets | the outline, drafted and verified (observed: 10–20 s when made; one attempt in two was refused by the verifier and had to be pressed again) |
| 0:50–1:15 | Its ideas: the saved **Concept map**, 7 concepts, 5 marked "Matches a syllabus skill" | My Sets → Concept map | drafted and verified (observed: about 25 s when made) |
| 1:15–1:45 | Research the weak idea: Explore, the saved pack **Time of Flight of a Projectile**, "Your pack is ready, made from 25 pages", then **Open the pack**: the cited pages and its Quiz · 9 questions | Explore | the research agent: two questions, a six-question plan, web search, verification (minutes; made before recording) |
| 1:45–2:35 | Practise from the lecture, made live: Quiz settings, tick **Multiple choice only**, 3 questions, Generate (13 s). Swap the components on question 1: "Incorrect. Not quite yet. Try a hint, then have another go." (no answer shown). Correct it: "Correct · Judged, not checked" with the cited explanation at 0:48. Next question twice, **Finish quiz**: "3 of 3 correct" | Generate → Settings: Quiz | drafting and the support check; each answer judged by the model against the cited line in 4 s or less |
| 2:35–2:55 | Your tutor (the material's tab): `What haven't I got yet?` → one sentence from Muse Spark, then two facts bound by code: "Of the skills YouTube video teaches, not yet secure: 5 skills" and "not started (YouTube video teaches it at 1:14). Source: teaching outline (2026-11-02)", with **See what your tutor knows** | Your tutor | the companion turn (observed: 10–20 s) |
| 2:55–3:10 | Close: Progress → Show my map → Physics → the Projectile motion tile: "Learning, 0 of 6 secure, Practised today, 1 mistake being watched". Say, not read: cited online with Muse Spark, kept private on this computer. | Progress | none |

**Captions.** Read the provenance line aloud once, on the outline, and let it stay on screen for the map, the quiz
and the pack. Caption the tutor's two facts as code, the sentence above them as Muse Spark.

### Timed pass, 2 November (early morning)

Run end to end on the stable host (5197) and gateway 8081, both on commit f0b862f2, at a 1440 × 900 viewport, every
beat driven for real. Wall clock for the whole pass was 12½ minutes because of the detours listed below; the beats
themselves, once the detours are removed, add up to about 3:10 at a presenter's pace. The three-minute target holds
only if the quiz is generated live in one press and the tutor answer lands in the 10–20 s seen tonight.

| Beat | Measured | What the screen showed |
| --- | --- | --- |
| Home → My materials | 23 s (sidebar expanded first) | Home now says "Last time you worked on physics in Study on 2026-11-01; 1 card is due." |
| Lecture → saved outline | 8 s | the 22:51 outline read "Made online, then checked" with no model name: it was made a minute before the 22:52 gateway restart. Regenerated; first attempt "Could not finish · 0/8, some generated content did not pass source verification", second attempt done in 10–20 s and named Muse Spark |
| Saved concept map | 9 s | 7 concepts, 5 "Matches a syllabus skill", line names Muse Spark |
| Explore → pack → Open the pack | 33 s | "Researched online with Muse Spark…", 25 pages, Key concepts and Quiz Ready, Quiz · 9 questions and Notes in My Sets. The pack's source view showed raw Markdown and LaTeX (fixed since) |
| Quiz, generated live and taken | 13 s to generate, 91 s to take at automation pace (about 60 s by hand) | wrong answer refused in under 4 s with no answer shown; corrected answer "Correct · Judged, not checked" at 0:48; "3 of 3 correct" |
| Your tutor | 10–20 s | sentence from Muse Spark plus two code-bound facts, sources dated 2026-11-02 |
| Progress → map | 12 s to the map, 33 s with Layers | Projectile motion tile "Learning, 0 of 6 secure, Practised today, 1 mistake being watched" |

Detours and what was changed for them:

- **Two materials were both called "YouTube video"**, and the first was a one-hour talk on language models, not the
  lecture. Opening it cost 20 s and would have derailed a recording. The actions menu offers only Archive, so that
  material is now archived (the Archived tab holds it); the library shows the pack and the lecture only.
- **The study panel (tools and My Sets) is hidden below a 896 px content width.** At 1024 px with the sidebar expanded
  there is no way to reach My Sets. Record at 1280 px or wider, or collapse the sidebar.
- **The saved Quiz · 3 questions cannot be retaken**: it opens on its review ("2 of 3 correct", every answer shown)
  and has no retake control. The beat therefore generates the quiz live. Settings default to Multiple choice, Fill in
  the blank and True or false all ticked: untick the last two by clicking their labels (a programmatic toggle does not
  register). Pressing Generate with settings identical to a saved set brings up "This study set already exists" with
  Open existing set / Generate a new set; different settings skip that dialog.
- **"Back to study" on a material hides the source pane; it does not leave the material.** Use Back to library. After
  leaving the pack, the Explore tab stays selected, so getting back to the lecture is Back to library → Materials →
  the video → My Sets: 45 s in this pass. Plan the order so the quiz follows the outline and map directly, and visit
  Explore last before the tutor, or accept the extra clicks.
- **The closing line about Muse Spark and Glimmer is not on the Progress page** or anywhere in the product copy; it
  was a narration line written as if it were on screen. The table now marks it as spoken.
- **Small inconsistencies seen, fixed the same morning:** Home said "1 card is due" while the tutor's status line
  said "11 cards are due" (Home's card left out Study's own due cards; it now counts them the way the thread does);
  the tutor's second fact truncated the skill name mid-word ("…changes its vertica:"; statements are now clipped at a
  word with an ellipsis); Progress opened on the Mathematics tab with nothing in it (it now opens on the subject with
  an idea that moved today, else the one with the most ideas past Not started); and the research pack's source view
  showed raw Markdown and LaTeX (it now reads as Markdown with its maths, except while a citation is highlighted in
  it). The thread's status line keeps the day's opener as worded when the episode opened, so after a session ends
  it can lag Home's until the next day.
- **Spend.** The pass (two outline attempts, one quiz, four markings, one tutor turn) added about $0.06 to the ledger
  for 2 November.

### Seen live on 1 November (night), and what to do about it

- **What it teaches** makes a new outline on every press, even when one exists (the earlier one moves under "Earlier
  What it teaches sets"). During the recording open the saved one from My Sets; press the button only if the narration
  wants to show generation, and then wait the 20 s on camera or cut with an elapsed-time caption.
- **The outline** gave 4 objectives (opening at 0:21, 0:29, 0:35, 0:41), 2 worked examples at 9:40, 10 concepts of
  which 7 map to the pack's projectile skills and 3 ("projectile motion", "projectile", "weight") are outside the
  packs, "Assumes you know: how to resolve a vector", one skill not covered (the trajectory graphs), and "For you":
  resolve **learning**, the other four **not started**.
- **The concept map** drew projectile motion, launch velocity components, horizontal motion, vertical motion, time of
  flight, range and maximum height; time of flight sits between range and vertical motion.
- **Start learning journey** on the time-of-flight objective hands off to the curriculum lesson "Two motions at once"
  (about 12 min, 8 parts); its first check, "a ball thrown straight up at 12 m/s, how long to the top", marked 1.2 s
  "Correct, 3 of 3 marks" by code. Not in the three minutes; it is where **Continue learning** on Home now points.
- **The quiz settings.** The rehearsal quiz came out as one multiple-choice, one fill-in-the-blank and one true-or-false
  item although Multiple choice alone was meant: check the question-type boxes by eye before pressing Generate. The
  formula typed into the blank ("2u sin theta / g") was marked "Could not verify", so a blank that wants a formula is a
  poor demo item; the 3-question set saved in My Sets is the one to use (question 1 is the components, question 3 is
  "range greatest at 45°", true).
- **Need help? on question 1** returned the general strategy twice ("the tailored explanation could not be verified")
  for both "Give me a hint" and "Walk me through it": the question is pure recall of the two components, so any
  tailored hint names the answer and the verifier refuses it. That is the safe behaviour; caption it as the fallback,
  or skip the hint and show the follow-up box instead. Do not promise a tailored hint on this question.
- **The research pack** asked two questions ("what feels tricky?", "what should I put in your pack, 5 or 20 minutes?"),
  proposed six sub-questions, and after Start research reported "Found 25 pages. Making your pack…", then Key concepts
  and Quiz ready. One poll failed while it was making and the line "The research planner isn't available right now"
  stayed on the pack until the page was reopened; fixed in this build (a failed poll is retried and a successful read
  clears the line). The pack's quiz carries the provenance line too.
- **The profile closed itself** after about twenty minutes of the walk-through (the profile chooser came back, the
  draft answers and sets were kept). Unlock the profile just before recording; three minutes is well inside the limit.
- **Hosts.** The provenance line needs the gateway and the host's engine on this build: the gateway on 8081 was
  restarted at 22:50 for it, and on 2 November at 01:10 the ML Demo host on 5199 and the gateway on 8083 were
  restarted on the pushed build too. (Port 8082 belongs to the jana-nebius project's gateway, not to this repository.)
  Aids made before a restart keep the unnamed line; regenerate any aid the recording will show.
- **Spend.** The gateway's ledger for 1 November stood at about $0.73 for the whole day after this preparation (the
  outline, the map, the quiz, two hint attempts, one companion turn and the 25-page research), within the $10 daily cap.

## Earlier storyboard (1 November: practice, Companion, lecture, map)

| Time | Beat | Screen |
| --- | --- | --- |
| 0:00–0:15 | Opening | Home, Demo Ada |
| 0:15–0:55 | A short practice run | Lessons, Physics, Projectile motion |
| 0:55–1:25 | The Companion: what haven't I got yet | My materials (Study), Your tutor |
| 1:25–2:15 | A YouTube lecture, understood | My materials (Study), Add a YouTube video |
| 2:15–2:50 | The learner's map | Progress, My map |
| 2:50–3:00 | Close | Progress or Your tutor |

**0:00–0:15, opening.** *Screen:* Home with the synthetic Demo Ada profile (O level Physics). *Learner action:* none.
*Tutor shows:* the code-built Last time card (SPEC §19.1), if the profile has an ended session to name; a new profile
sees the first-time card. *Model:* none; the card is code, every number beside its label. *Narration:* “Adult learners
returning to exam preparation need a tutor that knows what they have and have not got. We extended Jana during this
hackathon with a Study companion, lectures from YouTube, and a map of the learner's own knowledge, built on Meta models.”

**0:15–0:55, a short practice run.** *Screen:* Lessons, then the Physics tab, then the Projectile motion card, then **Practise
this**. *Learner action:* practice opens on the first skill, resolving a launch velocity (seen live: a ball kicked at
12 m/s at 60°, find both components, 4 marks). Answer with the components swapped, 10.4 and 6 m/s, then ask for a hint
(this needs the cloud tutor, see the setup list). *Tutor shows:* “Not quite”, 0 of 4 marks and “This idea moved from Not started to Learning”, marked by code; the hint
ladder (“Hint 2 of 5” and so on); and on the map the Projectile motion tile reads “1 mistake being watched”. The
feedback line itself does not name the mistake. *Model:* the marking is the sandboxed maths
worker, not a model; with consent on, the guided tutor's Diagnoser and Coach run on Muse Spark through the gateway,
and on Muse Glimmer with `--local-model` when the cloud is off. *Narration:* “Every number is checked by code before
the tutor says it. A wrong answer here is the classic one: the two components swapped.”

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

- **First run.** A new profile goes through “Choose your tutor” and two skippable questions, then lands on Home with
  Mathematics' “Index laws with letters” as Next up and no subject chosen. Create Demo Ada, finish these, and pick
  Physics before recording. The dev host also lists Accounting; the submission tree does not ship it.
- **Consents.** Either start the host with `--online-demo` (below), which records them for the profile it creates, or
  do them by hand, in this order (verified live): Settings → Online features: *Cloud tutor* → Give consent → Turn on;
  *Online study materials* → Review Study consent → Turn on (it asks twice, once for the computer and once for the
  profile). Then open **My materials** and answer **OK** on “Talk with the online tutor?” in **Your tutor**, or answer
  **OK** on the “Use the cloud tutor?” card that a hint, an Ask or a guided question now shows. Until that notice is
  answered no tutor turn is sent (see the walk-through's re-check).

- **The pack.** Pack 1.1.0 (with Projectile motion) must be the one installed in the demo profile's data folder. A
  folder seeded earlier has an older Physics pack and the lecture's concepts will show “outside the packs”. Check that
  Learn lists Projectile motion before recording.
- **A baseline for “since last time”.** The map marks only skills whose band rose or appeared since the map was last
  opened, and the first open marks nothing (SPEC §21.5). Open Progress once before the practice beat, then again in the
  map beat.
- **Dates for the scrubber.** It offers weekly dates from the profile's first learning event, at most 26 weeks. A
  profile created for the recording has no date four weeks back, and the machine clock must not be changed to
  manufacture one. Seen live on a new profile: the scrubber is not on the page at all. Either use a profile that genuinely has older history, or show the control and describe the
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
3. Launch `uv run python -m jana_tools.hackathon_dev --stable --port 5197 --data-dir /tmp/jana-demo`. For a demo
   with no Settings steps add `--online-demo` and a new, empty `--data-dir`: an adult profile created on that host starts
   with the cloud tutor, online Study materials and the cloud tutor's first-use notice already recorded (the same
   stores Settings and the cards write). It is off by default, needs an explicit `--data-dir`, leaves Personal tutor
   memory online off, never touches a profile that existed before the host started, and refuses a profile of under 18.
   For local inference add `--local-model /path/to/Muse-Glimmer-30B-KQuant-17GB-Q4_K_M.gguf`.
4. Create only invented adult profiles. Sign-up asks for a first name and an age (a whole number, 18 or over; a
   younger age creates nothing). Preinstall packs and models; do not spend the video downloading them.
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

## Live walk-through, 1 November

Run against this repository's gateway (version 1.2, port 8081) and the stable host on port 5197 with a new data
folder, invented profile Demo Ada, cloud tutor and online Study materials on, tutor memory online off. The two
gateways already listening on 8082 and 8083 both answered version 1.1 (8082 belongs to the parent project), exactly
the wrong-gateway case above, so a new one was started on 8081. The lecture used the synthetic fixture transcript
under a made-up video id; no link was opened. Muse Spark answered through the gateway (`POST /v1/chat/completions`
and `/v1/study/process`, both 200). What happened, beat by beat:

- **Opening.** Home shows the first-time Last time card (“When you've studied here, this card will say where you left
  off.”). Works as the spec says.
- **Practice.** The swapped answer was marked by code (“Not quite”, 0 of 4, Not started → Learning). The hint ladder
  advanced, but the tutor turn behind it failed until the consent card above was answered (cause found in
  `turn.py`'s first-use notice; the trace's `connectivity.state_at_start: "off"` was a hardcoded default, not a
  reading). *Now:* with the cloud tutor allowed, no model on the computer and the notice unanswered, every tutoring
  turn (hint, Ask, guided question) shows the “Use the cloud tutor?” card once and says “I need your OK before I can
  use the online tutor, so nothing has been sent. Choose OK on the card above, then ask again.” (after “Keep it on this
  computer”: that there is no tutor on this computer and the online tutor can be allowed in Settings). Ask anything on
  Home names the missing OK in its own words instead of “need the online plan”. The trace records the connectivity
  state the turn started in and whether the cloud tier served it.
- **Companion, before any lecture.** The first “What haven't I got yet?” returned the canned line (“Sorry, I couldn't
  put that together just now”); the trace gate was `fact_binding`, detail `number:1:unit:none`, `exhausted_canned`.
  The code-built fallback of 1 November covered only the case where an outline already exists. The same question
  asked again worked: it named two not-started projectile skills, each “Source: checked practice records
  (2026-11-01)”, with **See what your tutor knows**. The wording showed the raw band code `not_started`, and it did
  not mention the skill Ada had practised. *Now:* a reply refused twice with only `progress_read` in hand becomes a
  line built by code (“I couldn't put a fuller answer together, so here is where your checked practice records
  stand:”, then up to six skills, those not yet secure first, each with its source and date and **See what your tutor
  knows**), and a band is always said in words (“not started”, “learning”, “secure”).
- **Lecture.** The source was ready at once, with six chapters and an **Open at m:ss** on every chapter and line; the
  transcript lines are full width. **What this video teaches** took about 20 s and gave 4 objectives, 2 worked
  examples, 10 concepts mapped to the pack's skills, “Assumes you know: How to resolve a vector…”, one “Not
  covered here” skill (the trajectory graphs), and “For you” with five skills: resolve **learning**, the other four
  not started. Rough edges seen: the first three objectives show **Open at 0:00** (their lines are at 0:21, 0:29 and
  0:35); the assumed-knowledge moment prints “00:48” where the buttons print “0:48”; some generic concepts (“projectile
  motion”, “air resistance”) are tagged to the time-of-flight skill; the fixture has no air-resistance concept.
  *Now (re-run on a new data folder, 1 November):* the objectives open at 0:21, 0:29, 0:35 and 0:41 (a citation that
  spans several lines is read at the line that says the objective), every time reads “0:48” style, and “projectile
  motion” and “projectile” are marked outside the packs (a test covers “air resistance” too), while “time of flight”,
  “range equation”, “maximum height” and the two components still map to their own skills.
- **Ask about this moment (4:12).** The thread showed “About 4:12 in YouTube video”. The reply to “Why does the range
  depend on sin two theta?” offered to open that part of the video instead of explaining, with **Open the moment,
  4:12**. *Now:* the same question is
  explained from the ±30 s lines (the model may say the lecture's own figures, “two theta”, “ninety degrees”, “4:30”,
  which fact binding used to refuse, and the role no longer offers the video in place of an answer); **Open the moment**
  appears only when asked for. “What does this video teach that I haven't got yet?” was answered from the outline and Ada's bands: time of
  flight “(YouTube video teaches it at 6:40)” and the horizontal-velocity skill at 0:48, each “Source: teaching
  outline (2026-11-01)”.
- **Map.** Progress opens on **My map** with Mastery, Freshness and Mistakes; the Physics tile for Projectile motion
  read “Learning · 0 of 6 secure · 1 mistake being watched”. **Open the Physics map** opens the skill map inside
  Lessons, with layers Mastery, Freshness, Mistakes, Study, Notes and Tutor's topics, a legend, a table option and the
  node PHY-O-01.09.K01 “Learning … Asked 3 times · 1 mistake”. The scrubber, the Freshness and Study layers' contents
  and the skill sheet were not checked.

*Re-check, 1 November (host started with `--online-demo` on `/tmp/jana-demo-online`, new profile Demo Ada, no
Settings steps):* a guided question, a practice hint (wrong answer first), the Companion's “What haven't I got yet?”,
the lecture outline and “Ask about this moment” at 4:12 all reached Muse Spark through the gateway and finished. A copy
of the earlier folder with the cloud tutor's notice cleared, on a host without the flag, showed the card and the plain
sentence above and sent nothing, then worked after **OK**. Not re-run live: the Companion's canned-line fallback (it
needs the model to fail; covered by `test_w9_companion_moment.py`).

Not covered: voice, photos, Glimmer offline, the Open-at link in a real browser, tutor-memory online.

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

## Technical-notes alternative: ridge versus lasso (rehearsed 1 November)

This is the recommended short material demo when presenting to a technical audience. Use the supplied
`notes.pdf`, *Introduction to Machine Learning Class Notes* by Huy Nguyen. PDF pages **14–16** (printed pages
13–15) cover regularized least squares, ridge/lasso penalties and Gaussian/Laplace priors. The separate
**ML Demo** adult profile at `http://127.0.0.1:5199/` contains the imported notes, saved explanation and quizzes.
Its data directory is `/tmp/jana-ridge-lasso-demo`; copy or preserve that directory before clearing temporary files.
The local runner is `python -m jana_tools.hackathon_dev --port 5199 --data-dir /tmp/jana-ridge-lasso-demo --online-demo`.

| Time | Action and narration |
| --- | --- |
| 0:00–0:25 | Study → Materials → notes.pdf. Show page 14, then page 15's diagrams. “These are my actual lecture notes. Jana keeps the original equations and diagrams available.” |
| 0:25–1:15 | Back to study → Ask this material → History → the saved ridge/lasso question. Show the L2 and L1 equations. “Ridge favours small coefficients; lasso encourages sparse solutions. The explanation connects these penalties to Gaussian and Laplace priors.” |
| 1:15–1:45 | Open a page citation, compare it with the original PDF, then Back to study aid. “I can inspect the passage behind the explanation.” Page numbers are PDF page numbers, not printed page numbers. |
| 1:45–2:35 | Generate → My Sets → the **three-question** quiz (one question at a time; Need help? holds the hints). Choose lasso's L1 penalty for ridge once; Check answer gives Incorrect without immediately revealing the key. Correct it, then Next question through the sparsity and prior questions. |
| 2:35–3:00 | Finish quiz and show the results screen: 3 of 3 correct, then the cited explanations. “I can turn my own technical material into practice and trace the answers back to it.” These Study results do not update syllabus mastery. |

Question used for the saved explanation:

> Using sections 3.3.1 and 3.3.2, explain ridge versus lasso regression. Start with intuition, then show the two penalty equations and connect them to Gaussian and Laplace priors. Cite the relevant passages.

For a fresh quiz, open **Settings: Quiz**, keep Multiple choice only, choose 3 questions, review the extraction,
and use this Focus:

> PDF pages 14–16: ridge versus lasso. Test the L2/L1 penalty, sparse solutions, and the Gaussian/Laplace prior connection. Preserve the source qualifiers in every correct option. Use clear LaTeX for equations.

The `PDF pages …:` prefix narrows the source before batching; an ordinary free-text focus alone still sends
all selected pages. Leave focus blank for whole-document coverage. Generate before recording and use the saved
quiz during the three-minute demo. The final rehearsal generation took about **9 seconds**, but model latency
is variable. Do not present a cut or a saved result as instantaneous live generation.

Verified in the live app:

- All 69 pages extracted; none unreadable. Native extraction flattens some formula notation, so the paged
  original PDF is the reference for equations and diagrams. Extracted citation text stays unchanged.
- The saved explanation's 11 citations and the final quiz's 6 stem/explanation citations exactly matched their
  source offsets. Main penalty equations and quiz equations rendered without KaTeX errors.
- Wrong-answer feedback, correction, next/previous navigation, a source-linked hint, final submission and three
  Correct verdicts worked. The hint was safe but terse (a penalty-function definition); use the cited explanation
  for the main demo rather than promising rich hints on every question.
- The first unscoped quiz failed on unrelated batches. Explicit page scoping fixed that path. An intermediate
  two-question quiz remains in My Sets; use the later three-question set. Wording was tightened after an early
  option overstated lasso's bias as a guarantee.
- Materials, Your tutor and Explore now have separate library tabs. Common tools appear first; other formats
  are under More study tools. Citations open one original page, while answers and quizzes use the main area.
- Responsive checks at 1280 and 772 pixels: no horizontal overflow. 104 UI tests and 36 backend/gateway tests
  passed; TypeScript, mypy and Ruff checks passed for the changed code.

This demo shows Muse Spark's grounded generation through the Meta gateway. Native PDF text extraction and
PDF page rendering are document processing, not a demonstration of Muse vision or SAM. Quiz explanations are
labelled “Judged, not checked”; do not claim that every generated mathematical statement was formally proved.
