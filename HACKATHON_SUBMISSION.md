# Submission preparation — 30 October 2026

Status: draft materials prepared; no submission, public publication or video upload performed.

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

**Jana — a personal Study agent that remembers, explains and lets learners correct it.**

Jana supports adults preparing for foundational mathematics and science exams. During the hackathon we extended
its existing tutoring foundation with a persistent Study companion and Meta model integrations. A learner can
state a preference, study, return after restarting, continue an agreement and inspect why the tutor personalizes
its response. Explicit remember, correct and forget commands keep the learner in control of saved memory.

Muse Spark supplies cloud reasoning and tool use through a budgeted gateway; Muse Glimmer supports local tutoring
on suitable hardware. Deterministic checks and recorded attempts govern progress evidence. Preferences, study
activity and demonstrated understanding remain distinct. Profile boundaries and filtered outbound context protect
the separation between learners. Encrypted restoration preserves authorized state, with raw history subject to
separate authorization.

The engineering contribution is the integration of durable memory, verifiable learner evidence, controlled model
access and a usable study workflow. We have regression evidence for a simulated multi-day learner journey. We do
not yet claim measured learning gains or a longitudinal learner study.

## Contribution boundary

Prior work: Jana's core tutoring engine, authored curriculum, desktop shell, checking worker and underlying learning
tools. Event work: Meta adaptation and the Study learning agent, including persistence, memory controls, isolation,
evidence binding and restoration. Companion commits `7a92235d` and `aed35cbf` document the October 29–30 work.
Keep the original private history as provenance; the submission builder intentionally creates a history-free tree.
Have the owner review the exact contribution list and human contributor names before publishing.

## Remaining release inputs and gates

| Item | Status / required action |
| --- | --- |
| Human contributor names and roles | Owner must supply or confirm; do not infer people from agent commit authors. |
| Public repository URL | Not published by this task. Build and inspect the filtered tree before publication. |
| Video URL | Script in `HACKATHON_DEMO.md`; recording and link verification still required. |
| Live cloud walkthrough | Owner consent enabled 31 October. Real Muse Spark Study reply and guided maths handoff observed (13.213 s and 16.384 s core traces); online agreement recall after core/browser restart completed in 9.035 s without retry. Preferences persisted and forgotten modality stayed cleared. Symbolic-verification blocker fixed. Rich-editor answer entry could not be completed through the available browser controls; do not claim a live marking pass from this run. |
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
