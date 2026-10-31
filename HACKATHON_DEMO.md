# Jana: three-minute learning-agent demo

Draft for rehearsal, updated 31 October 2026. This is a recording script, not a completed video.
Use a synthetic adult learner and the stable build. Show only the app window. Keep credentials and real profiles
out of the recording. Retain the original recording so any cuts and elapsed-time captions can be checked.

## Storyboard

| Time | Visible action | Narration |
| --- | --- | --- |
| 0:00–0:20 | Study, synthetic Demo Ada profile | “Adult learners returning to exam preparation need a tutor that remembers where they struggled and what they agreed to do next. We extended Jana during this hackathon with a personal Study agent built on Meta models.” |
| 0:20–0:45 | Send `Remember that I prefer short explanations.` Open what the tutor knows. | “Ada asks for short explanations. This is saved as a stated preference, with its source. It is not treated as evidence that she understands a topic. She can inspect and change what the tutor remembers.” |
| 0:45–1:20 | Ask the real model what to study next; follow its practice action and complete one checked question | “The agent connects conversation to actual study actions. Meta handles the conversation and tool selection; Jana's checking and learner-state code determine what evidence is recorded. Reading a lesson alone does not become a mastery claim.” |
| 1:20–1:50 | Set a small agreement, close and reopen the app on the same profile, show continuation | “Here is the same learner returning after a restart. Her conversation, preference and agreement survive. This restart is real; a multi-day journey is additionally covered by simulated regression tests.” |
| 1:50–2:15 | Send `Actually, I prefer hints first.` Then forget a separately saved diagram preference and inspect memory | “Ada remains in control. Correction changes the saved preference. Forgetting removes the memory from future recall; it does not pretend the visible conversation never happened.” |
| 2:15–2:40 | Show cloud off and a real local reply, or clearly label the content-only fallback | “With the installed Muse Glimmer model, the tutor can run locally. Without a local model, saved history and authored practice still work. These are different capabilities, and the app makes the distinction visible.” |
| 2:40–3:00 | Evidence view, then brief second-profile switch | “Personalization should be inspectable. This profile has its own memory; another learner starts with their own context. We are demonstrating continuity and evidence-backed adaptation, not claiming measured improvements in exam scores.” |

Use the actual observed model name in captions. Do not label a deterministic memory acknowledgement as a model
response. Only use a checked question and model interaction already rehearsed successfully. If the sequence runs
long, keep preference → real model action → restart → correction, and show isolation in the supporting walkthrough.

## Rehearsal and fallback

The owner has enabled online tutoring for the isolated Demo Ada profile at `http://127.0.0.1:5197/`, using
`/tmp/jana-learning-agent-live-demo-20261030`. Real Muse Spark Study and guided tutor calls have completed;
the original symbolic-verification failure was fixed and the same question passed online. See
`LEARNING_AGENT_REVIEW.md` for exact evidence and limits. The current running build is online-only: restart
with `--local-model` below before promising an offline generated reply. Saved content still works offline.
An agreement made locally is not automatically available to the online tutor under the current permissions;
use an agreement made during the online conversation for the online continuity demonstration.
That sequence now has a passing live rehearsal: a fresh message after a full core/browser restart recalled the
online index-laws agreement without retry. The preference view retained Short and Hint first, with diagrams cleared.

1. Start the gateway before the app, within its existing durable budget. Enable online tutoring only with consent.
2. Launch `uv run python -m jana_tools.hackathon_dev --stable --port 5197 --data-dir /tmp/jana-demo`.
   For local inference add `--local-model /path/to/Muse-Glimmer-30B-KQuant-17GB-Q4_K_M.gguf`.
3. Create only invented adult profiles. Preinstall packs and models; do not spend the video downloading them.
4. Run the storyboard without recording. Confirm every reply finishes, every button works, and every personalized
   statement has the right source. Restart the actual core as well as the browser during the supporting rehearsal.
5. Record a successful real-provider run with readable captions, then keep a local copy as the presentation fallback.
   Cut idle waits only with an honest elapsed-time caption. Never substitute scripted output for a failed model call.
6. Play the exported video from beginning to end, check the duration is at most three minutes, and check audio and
   caption legibility. Test the shared link without the owner's login before submitting it.

If the network fails live, use the verified local-model path or show the prerecorded run with a clear “recorded
earlier” label. If no verified recording exists, show offline saved memory and authored practice and state that
online inference is unavailable. A storyboard is not a fallback video.

## Supporting acceptance walkthrough

Record separate evidence for: saved preference; study and checked attempt; core restart; continued agreement;
corrected preference; forgotten memory absent from future recall; encrypted export and restoration; profile B
isolation; return to A; explanation sources. Use the API regression journey for simulated days, clearly labelled.
The default profile export does not promise raw chat history; test the separately authorized archive path when
claiming transcript restoration. Do not change the machine clock to manufacture a multi-day live demo.
