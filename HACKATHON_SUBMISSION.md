# Submission preparation — 30 October 2026, updated 1 November 2026

Status: draft materials prepared; no submission or video upload performed. The code is public at
<https://github.com/ruhu-inc/jana-meta> (`main` at `4ccd5c4c`, tagged `demo-2026-11-01`).

**Update, 2 November:** Jana is no longer only an O-level tutor. Study works for any material, and a new learner can
choose "My own course and materials", which hides the curriculum. HACKATHON_DEMO.md has the matching script. Check the
copy below against this before submitting.

## Official requirements checked

The [event page](https://cerebralvalley.ai/e/meta-ai-developer-hackathon) lists the deadline as **4 November 2026,
9 PM Eastern**, which is **5 November, 3 AM in Lagos**. Dates may change; recheck before submitting. Jana's intended
track is Startup and its theme is Build for Your World. The event emphasizes technical execution and production
readiness for that track.

The [participant details](https://cerebralvalley.ai/e/meta-ai-developer-hackathon/details), read in the signed-in
browser on 30 October, require a public repository, a three-minute demo video, accessible links and identification
of contributors. Teams have at most four people and one representative submits one project. Existing startup
products may be used, but the demo must clearly distinguish the features and functionality built during the event.
Confirm the final form and official rules in the portal before submission; this document does not accept them.

## Draft project description

**Jana — a personal Study agent that remembers, explains, understands a lecture and shows the learner their own map.**

Jana supports adults preparing for foundational mathematics and science exams. During the hackathon we extended
its existing tutoring foundation with a persistent Study companion, YouTube lectures as a Study source, a map of the
learner's own knowledge and Meta model integrations. A learner can state a preference, study, return after
restarting, continue an agreement and inspect why the tutor personalizes its response. Explicit remember, correct
and forget commands keep the learner in control of saved memory.

The demo centres on three Study features built in the last days of the event (SPEC §19 to §21); the rest of the event
work, from 26 October, is listed under Contribution boundary.

- **The Companion.** One persistent conversation per learner, **Your tutor**, that remembers the last session,
  searches the learner's own materials, reads their progress, plans, makes Study aids and starts research. Code
  decides and writes; the model chooses and phrases; every progress number comes from a tool. Privacy: the thread
  and its memory are local-only by default; tutor notes and one-line records of practice leave the device only under a
  separate consent, Personal tutor memory online, which is off by default.
- **A YouTube lecture as a Study source.** The learner pastes a YouTube link and the video's transcript; Jana
  returns a teaching outline (objectives, worked examples, concepts and what the lecture assumes), each statement citing
  a transcript line, mapped to the learner's syllabus skills and compared with their own bands. Every moment has an
  **Open at m:ss** link that opens the learner's browser; there is no embedded player in this release. Privacy:
  nothing is downloaded, Jana opens no connection to YouTube, and the pasted transcript is the learner's private copy,
  sent to the gateway only under the Study-materials consent.
- **The learner's map.** Progress opens on a map of every installed subject, with Mastery, Freshness, Mistakes,
  Study and Notes layers, marks for what moved since last time, and a time scrubber that replays the learner's own
  record to an earlier date. Privacy: device-only, no model call, nothing in it reaches a prompt or leaves the
  computer.

The demonstration subject is the Physics pack's new subtopic Projectile motion (PHY-O-01.09, pack 1.1.0).

Muse Spark supplies cloud reasoning and tool use, the Companion's wording and the lecture outline through a budgeted
gateway; Muse Glimmer supports local tutoring and the Companion on suitable hardware; SAM 3.1 outlines the lines on
photos and diagrams; Kokoro-82M reads replies aloud. Deterministic checks and recorded attempts govern progress evidence. Preferences, study
activity and demonstrated understanding remain distinct. Profile boundaries and filtered outbound context protect
the separation between learners. Encrypted restoration preserves authorized state, with raw history subject to
separate authorization.

The engineering contribution is the integration of durable memory, verifiable learner evidence, controlled model
access and a usable study workflow. We have regression evidence for a simulated multi-day learner journey. We do
not yet claim measured learning gains or a longitudinal learner study.

## Contribution boundary

Prior work: Jana's core tutoring engine, authored curriculum, desktop shell, checking worker and underlying learning
tools. The baseline is `7cf6c6ed` (25 October, the prior source imported without history); the hackathon ran from
26 October and event work starts with the next commits. Event work, by the workstreams of `SPEC.md` (the spec's own
status table, 28 October, and the later sections; each is built unless noted):

| Dates | Workstream | What was built |
| --- | --- | --- |
| 26–28 Oct | W1 Muse Spark | A Meta adapter in the gateway; the cloud tutor (Diagnoser, Solver, Checker, Coach, input guard) and Study run on Muse Spark in Standard mode; reasoning effort set per model alias; spending budget holds released only for calls that were not billed. |
| 26 Oct | W2 Vision | SAM 3.1 behind the gateway at `/v1/vision/segment`; photos of working read in the cloud, outlined while the learner confirms, with Jana pointing at the line on the learner's own photo; photographed sketches checked; a diagram drill. |
| 27 Oct | W3 Muse Glimmer | Offline tutoring on Muse Glimmer 30B from the browser host, with its vision projector and DFlash draft; a fall back to the local model within seconds of a power cut and a return to the cloud after it; authored hints shown at once offline. Open at the spec's last status: a typed question's first words were 30–48 s offline on a loaded machine against an 8 s target. |
| 27–28 Oct | W4 Speech | Muse Voice Transcribe online through the gateway; Kokoro-82M as the only voice; a voice bar in the tutor (JM-D20) where every spoken word still comes from an accepted, checked turn. Offline speech to text was not finished at the spec's last status. |
| 26–27 Oct | W5 Adult product | Age at sign-up (a whole number of years, changed from a date of birth on 1 Nov) and an 18-and-over check in the engine and API (Meta's terms), adult copy, parent sections removed. |
| 27 Oct | W7 Research agent | A conversation and plan on the device, a gateway job that searches, fetches safe pages, checkpoints and resumes, and import into Study as one cited material with a concept map. |
| 26–28 Oct | Teaching features | Checked figures on items and lessons, tracing a misconception to the earlier skill it comes from, explain-it-back before mastery on the skills whose key points are written (7 of 367 so far), predict-before-you-see simulations; every learner-visible number held to a code check; hardening of the maths worker against huge powers. |
| 28 Oct | Meta-only entry | Nebius, Nemotron, Tavily web search, the Google/Gemini stack and NVIDIA's trial voice removed (JM-D14); only Muse Glimmer recommended offline; identifiers and key references renamed for jana-meta. |
| 27 Oct | Packaging | `scripts/build-submission.sh` builds the submission tree from one commit; README rewritten for Meta's models. |
| 29–30 Oct | W8 Companion | `7a92235d`, `aed35cbf`: the personal Study companion (SPEC §19). |
| 31 Oct | W9, W10 | `b814436d`, merged in `f1578e33`: a YouTube lecture as a Study source (§20) and the learner's map (§21). |
| 1 Nov | Demo build | `4ccd5c4c`, tagged `demo-2026-11-01`: Projectile motion in the Physics pack (1.1.0) and the W9/W10 live-run fixes. |

Several of the 26–28 October workstreams were built in parallel sessions and merged; confirm the dates and the list
against the history before it goes into the form. Physics pack 1.1.0 is new content written during the event.
Keep the original private history as provenance; the submission builder intentionally creates a history-free tree.
Have the owner review the exact contribution list and human contributor names before publishing.

## Remaining release inputs and gates

| Item | Status / required action |
| --- | --- |
| Human contributor names and roles | Owner must supply or confirm; do not infer people from agent commit authors. |
| Public repository URL | <https://github.com/ruhu-inc/jana-meta>, `main` at `4ccd5c4c`, tag `demo-2026-11-01`. Owner to confirm this is the repository to submit, and whether it is the filtered candidate below or carries this history, before the contribution list cites commits. |
| Video URL | Script in `HACKATHON_DEMO.md` (rewritten 1 November around the projectile-motion storyboard: practice, Companion, YouTube lecture, learner's map). Not yet rehearsed end to end; recording and link verification still required. |
| Live cloud walkthrough | Owner consent enabled 31 October. Real Muse Spark Study reply and guided maths handoff observed (13.213 s and 16.384 s core traces); online agreement recall after core/browser restart completed in 9.035 s without retry. Preferences persisted and forgotten modality stayed cleared. Symbolic-verification blocker fixed. Rich-editor answer entry could not be completed through the available browser controls; do not claim a live marking pass from this run. |
| W9 and W10 live run | SPEC §20 and §21 record a live run of both in the browser host on 31 October and the fixes of 1 November (each with a test). The full storyboard has not been rehearsed against the live gateway, and the packaged desktop app's opening of external links is unverified, so the video should be recorded from the browser host. The scrubber needs a profile with real history; see the demo notes. |
| Local walkthrough | Real Muse Glimmer tool use, memory controls, profile isolation and checked practice observed. Agreement recall passed after restart and retry; the intermittent first-send stall still needs resolution. |
| Final form and rules | Read and review at submission time; no agreement accepted here. |
| Evidence | Keep targeted test results separate from real-provider UI observations; see `LEARNING_AGENT_REVIEW.md`. |

## Reproducible candidate

Finish and commit the reviewed changes first. The builder reads a committed ref and excludes uncommitted files:

```sh
scripts/build-submission.sh --ref <reviewed-commit> --verify /tmp/jana-submission-candidate
```

This creates a local candidate, not a publication. It includes Mathematics, Physics and Chemistry, excludes
Accounting and private specification/governance material, regenerates the smaller workspace's lockfiles, and
checks the isolated result. Inspect its README, licences, dependencies and secret scan before making it public.
The README carries the contribution boundary and stable-demo setup because this private preparation document is
not included by the builder. Preserve test failures and fix them; do not replace a failed fresh-install gate with
the working checkout's passing tests.
