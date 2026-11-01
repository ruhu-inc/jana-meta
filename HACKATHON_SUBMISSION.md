# Submission preparation — 30 October 2026, updated 1 November 2026

Status: draft materials prepared; no submission or video upload performed. The code is public at
<https://github.com/ruhu-inc/jana-meta> (`main` at `4ccd5c4c`, tagged `demo-2026-11-01`).

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

Three features were built during the event (SPEC §19 to §21):

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
tools. Event work: Meta adaptation and the Study learning agent, including persistence, memory controls, isolation,
evidence binding and restoration (W8, SPEC §19), a YouTube lecture as a Study source (W9, §20) and the learner's map
(W10, §21). Commits `7a92235d` and `aed35cbf` document the October 29–30 Companion work; `b814436d` (merged in
`f1578e33`) is W9 and W10 of October 31; `4ccd5c4c` (1 November) adds the Projectile motion pack subtopic and the
live-run fixes, and is tagged `demo-2026-11-01`. Physics pack 1.1.0 is new content written during the event.
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
