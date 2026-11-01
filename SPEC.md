# jana-meta — specification for moving the fork onto Meta models

Status: **approved to build** (owner, 2026-10-26). This replaces the spec-only version of 2026-10-20 (kept in commit
7cf6c6e and in `../jana-meta-spec-backup`). The codebase is a history-free copy of jana-nebius at c4354de. This spec
says what changes, in which files, and what "done" means. It changes nothing in Jana's product (`../jana`).

Sources: the research brief `../jana-hackathon-research/meta-hackathon-brief.md` (models, prices, limits as of
2026-10-20), the event page and Official Rules (read 2026-10-25), and a file-level map of this repository.
Every Meta API detail marked **(verify)** must be confirmed with a real key on day 1 before code depends on it. On
2026-10-26 the Meta docs (dev.meta.ai/docs) confirmed or corrected most of them; §16 records what they say, and items
still marked (verify) are not documented and need a real call.

## Status (updated 2026-10-28)

Work landed on `main` today, from this session and from parallel sessions merged at 17:33–17:41:

| W | State | Remaining |
|---|---|---|
| W1 Muse Spark | **Done**: Meta adapter, Nebius and Tavily removed, live typed maths and physics turns, latency halved (12.8–15 s), effort per alias, schemas self-contained, input guard on Spark, budget holds released for unbilled refusals | Dropped-stream accounting (§4.3), health probes spending credit, turn latency (§12: speculative Solver done, ~4 s off a new question) |
| W2 Vision | **Done**: SAM 3.1 at `/v1/vision/segment`, photos of working read in the cloud, outlines while the student confirms, `photo_region` pointing on the photo, photographed sketches checked, base64 false positive fixed (parallel session); the diagram drill (§5.2, 2026-10-26) | Read time of a diagram (~15–20 s) |
| W3 Glimmer | **Built 2026-10-27** (§7): launcher with projector and DFlash, router and recommendations entries, reasoning strength per request, lean offline turns, authored hints offline, power-cut fallback in seconds and return to the cloud; practice and mock papers measured offline | A typed question's first words in ≤ 8 s (now 30–48 s on a loaded machine; needs the owner's call on streaming before the gates, §7); the Wi-Fi-off run on the demo laptop |
| W4 Speech | **Online done**: Muse Voice Transcribe in the gateway (paced, silence between turns, budgeted, per-turn re-checks; branch `claude/bold-bardeen-60a405`), Kokoro served by the gateway (the only online voice; NVIDIA's trial voice retired 2026-10-28), a 600 ms end-of-speech hold, subject-first keywords, the voice bar in the tutor (JM-D20), a spoken checked turn in the browser host (§12) | The engine turn (the 4 s target), the browser's filler at 2.6 s, offline (§6.3), spoken unit names |
| W5 Adult | Sign-up with age, adult copy, parent sections removed, safety wording | Engine-side band check, remaining guardian copy (§17) |
| W6 Bugs | #1, #4, #6 done; #5 partly (parallel session) | #2, #3, #7 |
| W7 Research agent | **Built 2026-10-27, end-to-end check next**: the conversation and plan on the device (§18.1a), the gateway job (search, safe fetch, checkpoints, source steering; 4 questions → 16 s, 22 pages, $0.04), import into Study as one cited material with Study's verified parts, the Study UI and "Make a study pack" from the diagram drill | A full pack from the browser, timed; the podcast read by Kokoro on the device |
| Standout features (parallel session) | Checked figures, gap tracing, explain-back, predict-before-you-see sims merged | — |
| Glimmer-free check | `phys_circuit`'s recursive schema unrolled for Spark (§16) | — |
| Meta-only entry (JM-D12, JM-D14, JM-D19) | **Done 2026-10-28**: NVIDIA's trial voice removed (Study Podcasts are read by the gateway's Kokoro through the podcast route), the Google/Gemini stack and the old production release material deleted, only Muse Glimmer recommended offline, key references renamed `jana-meta.` | — |
| W8 Learning agent | **Specified 2026-10-29, reworked after review** (§19, `LEARNING_AGENT_REVIEW.md`): phases 1–3, decisions JM-D21–JM-D29 proposed for the owner; phase 1 built 2026-10-29; phases 2 and 3 follow at once (owner) | phases 2–3 |
| W9 Video source | **Specified 2026-10-31, reworked after review; JM-D42 spike answered** (§20, `SPEC_W9_W10_REVIEW.md`, `SPIKE_JMD42.md`): a YouTube lecture as a Study source (link plus pasted transcript), Watch on YouTube at the moment (the embedded player does not play in the packaged app), a "What this video teaches" aid mapped to skills by code, moments from the thread, Ask about this moment; video files with board writing read as text; JM-D30–D34 agreed, JM-D40, D43, D44 proposed | all |
| W10 Learner's map | **Specified 2026-10-31, reworked after review** (§21): Progress opens on the learner's map with freshness, mistakes, Study and notes layers and a read-only time scrubber replayed from the event log; JM-D35–D39, D45 proposed | all |

## 1. What we are building

**Jana for adult learners, on Meta.** An exam-prep system for learners **aged 18 and over** preparing for O level
exams, or refreshing those foundations for university entry and first-year study. The packs cover Mathematics,
Physics, Chemistry and Accounting on the Cambridge O level topic structure (5054, 5070), in our own words; they cover
the core O level topics that WAEC, NECO and GCE syllabuses share, so the pitch says that and no more (§17 Claims).
It keeps Jana's teaching rules: it never just hands over an answer, every number is checked by code before it is
said, and anything it could not check is labelled. It sees (photos of working, diagrams), hears, reasons, researches
(§18) and keeps working offline. It is not presented as a chatbot (§14).

Event: Meta Global AI Developer Hackathon, remote, **Oct 26 12:00 PM – Nov 4 9:00 PM ET**, Startup track, theme
"Build for Your World". Judging: Impact 30%, Use of Meta AI tooling 25% (beyond a basic integration), Technical
depth 20%, Demo 25% (works live, holds up, video quality).

## 2. Decisions

Kept from 2026-10-20: JM-D1 (18+ only), JM-D6 (cascaded voice; every spoken word comes from an accepted engine
turn), JM-D7 (separate hosting project), JM-D8 (nothing with a non-commercial licence goes back into Jana).
JM-D1 rests on the Meta Model API Terms of Service (dev.meta.ai/legal/terms-of-service, checked 2026-10-26): "You and
your End Users must be at least 18 years of age to use the Services and Integrated Products, and you will not create
Integrated Products targeted at individuals under the age of 18." A parent signing in for a child, or a shared
parent-and-child account, does not change who the end user is, so it is out of scope for this entry. The rule covers
every Model API service (Spark, SAM, Voice Transcribe); only Glimmer's open weights fall outside it. Owner decision,
2026-10-26: the entry stays 18+, and school-age learners, with parent and guardian visibility, use Jana on its own
stack, which keeps its guardian consent, parent summary and alerts. The under-18 sign-up message may point to Jana
for schools once it has a public link.

| # | Decision |
|---|---|
| JM-D9 | **Online reasoning is Muse Spark** for the engine roles that may leave the device (Coach, Diagnoser, Solver, Checker, the input guard and other auxiliary roles; the Reflector stays local because it reads private notes), for Study and for the research agent (§18). No other cloud language model is configured. |
| JM-D10 | **Online vision is Muse Spark + SAM 3.1.** Muse Spark reads the photo (what the question is, which regions matter); SAM 3.1 turns those regions into exact masks so Jana can crop for a second, sharper read and point at the exact place on the learner's own photo. |
| JM-D11 | **Local inference is Muse Glimmer 30B** (Apache-2.0, official GGUF Q4_K_M, ~16.8 GB) under the existing llama-server supervisor, on 32 GB+ machines. Smaller machines run online only. No non-Meta local language model ships in the entry (offline speech models are covered by JM-D12 and JM-D13). |
| JM-D12 | **Speech to text is Meta.** Online: Muse Voice Transcribe (realtime). Offline: Meta **Omnilingual ASR** (Apache-2.0) if it passes the latency gate in §6.3; otherwise faster-whisper stays as the offline fallback. English only (JM-D18). Speech out is Kokoro-82M (JM-D13): the NVIDIA trial voice was retired 2026-10-28 and its code removed. |
| JM-D13 | **Text to speech is not Meta**, because Meta has no commercially usable TTS (MMS-TTS is CC-BY-NC and not streaming). Online and offline: **Kokoro-82M** (Apache-2.0, already in the speech pack), served by the gateway online and read on the device offline. Study Podcasts are read online by the gateway's Kokoro through the podcast route (`podcast_speech.py`). (NVIDIA's trial voice was used in development until 2026-10-28; its audio could not be distributed, and it is removed.) |
| JM-D14 | **Removed:** Nebius Token Factory, all Nemotron models, Tavily web search, and the Google/Gemini cloud stack (Gemini models, Gemini Live, Chirp STT/TTS) from configuration and from the submission. Done: the Google stack's code, tests and release material were deleted 2026-10-28 (§8.1). |
| JM-D15 | **Adult product:** every profile is `18_plus`; guardian consent, parent summaries, family plan and under-18 Ask policies are hidden or removed. Sign-up asks for age (whole years) and blocks under-18s. *Changed 2026-11-01 from a date of birth: less friction, and the check is a self-declaration either way; only the `18_plus` band is stored, as before.* |
| JM-D16 | **Muse Spark Standard mode only**, never Contributor mode (Meta trains on Contributor data). Contributor mode is a separate model id (`muse-spark-1.3-contributor`), so the gateway configures only Standard ids. Zero data retention for the project account is requested only if the owner chooses it over the research agent (§15 item 2): it disables search grounding, background and stored requests, and file uploads. Muse Code, if used, must not run in Contributor mode on this repository: **Muse Code subscriptions default to Contributor mode**, so run it with `--contributor-mode off` or `MUSE_CONTRIBUTOR_MODE=0`. |
| JM-D17 | **Submission scope:** the organisers receive a perpetual licence to whatever is submitted (Official Rules, "Hackathon Submission"). Only what the entry needs is submitted (§9). The owner signs off on the scope before submission. Owner, 2026-10-27: Chemistry ships with Mathematics and Physics; Accounting stays out. |
| JM-D18 | **English only** (owner, 2026-10-26). No Yoruba, Hausa, Igbo or Pidgin input in the entry; Voice Transcribe does not support the first three anyway. |
| JM-D19 | **Meta-native presentation** (owner, 2026-10-26). The code, configuration names, interface copy and documentation read as a project built for Meta's models from the start: no Nebius, Nemotron, Tavily or earlier-hackathon framing remains (for example the keychain service is `jana-meta.cloud-gateway`, and the README is about Meta). Done 2026-10-28: identifier `app.jana-meta.desktop`, key references `jana-meta.`, no NVIDIA, Google, Qwen or Gemma in what ships (§17 Identity). |
| JM-D20 | **Voice conversation in the tutor** (owner, 2026-10-27; replaces D130 on the tutor screen for this entry). With Cloud voice switched on, the tutor screen offers the voice bar ("Start a conversation", push to talk, hands-free): every spoken question is a full tutor turn, with the filler at 1.5 s and the accepted spoken form read sentence by sentence by Kokoro; every spoken word still comes from an accepted engine turn (JM-D6). Without Cloud voice the tutor keeps dictation and read-aloud only; Ask anything and Study keep their own conversations. |

## 3. Architecture

```
 Learner (browser demo host or desktop app)
   mic ─► voice bridge (barge-in is a server `flush`) ┐        photo ─► perception worker (local, sandboxed):
   speaker ◄──────────────────────────────────┐       │        orientation, face/person screen, crop, deskew,
                                              │       ▼        privacy mask, ≤1600 px JPEG
 ┌──────────── cloud gateway (jana-meta) ─────┴──────────────────┐        │
 │ voice WS: Muse Voice Transcribe (STT) ─► transcript ──────────┼──► Jana engine (agent-core, on device)
 │           Kokoro-82M ◄──────── accepted say_spoken only ◄─────┼─── input guard → Diagnoser → Solver + tools
 │ chat:     Muse Spark, Chat Completions (api.meta.ai/v1) ◄─────┼─── → Checker → Coach → release gates
 │ vision:   Muse Spark (read) ⇄ SAM 3.1 at /v1/vision/segment ◄──┼─── PhotoReader (engine/vision.py)
 │ research: agent jobs on the Responses API + web_search (§18) ◄─┼─── Study: Learn from a picture / Research a topic
 │ budget ledger (credits cap) · secrets · no payload logging    │
 └───────────────────────────────────────────────────────────────┘
 Offline, any laptop: signed packs: lessons, practice with checked marking and hints, mock papers, saved study packs
 Offline, 32 GB+: llama-server + Muse Glimmer 30B (+ DFlash draft) · faster-whisper or Omnilingual · Kokoro
```

The engine, tools, gates and voice bridge do not change design. Only providers, configuration, speech stages and
the vision step change.

## 4. Online reasoning: Muse Spark (JM-D9)

### 4.1 Model and routing

| Alias (device sends `primary/<alias>`) | Model | Used by | Reasoning |
|---|---|---|---|
| `fast-model` | `muse-spark-1.3` (chosen; 1.2 has the same price and limits) | coach, diagnoser, title, input_guard, rule_matcher, compaction | device low → Spark `minimal` |
| `strong-model` | same model id | solver, checker, study, research agent | device high → Spark `low`; medium → `minimal` |

The device still asks low, medium or high; each alias's `thinking` map in `defaults.toml` sets the Spark effort
(2026-10-26: this halved a guided turn from ~23 s to 12.8 s with the checks still passing).
| `small-model` | removed | — | — |

One model serves both aliases; the aliases stay so the router's tiers and `router.yaml` keep working. Muse Wonder is
not used (preview, about 5× the output price).

### 4.2 Changes

| File | Change |
|---|---|
| `services/cloud-gateway/cloud_gateway/providers/meta.py` (new) | `MetaAdapter(OpenAICompatAdapter)`: base `https://api.meta.ai/v1`, Bearer `meta_api_key`. `prepare_body` (a module function, as `nebius.py` had, called from `_body`): `tool_choice` `"required"` → `"auto"` (Spark accepts only `auto`; anything else is a 400; the engine's existing tool nudge stays), a named-function `tool_choice` → `"auto"`, `"none"` → send no `tools` and no `tool_choice` (whether earlier tool calls in the history are accepted then is **(verify)**); send `response_format: json_schema` with `strict: false` (still decoded under the schema; strict additionally demands every property be required, which the engine's contracts do not meet), with every cross-document `$ref` copied into the schema (`bundled_schemas`, done); drop `chat_template_kwargs`, `stop`, `logprobs`, `n` and other fields Spark rejects (§16); map `reasoning_effort` none → `minimal` (Spark always reasons; `none` is a 400). Usage: `completion_tokens` already includes reasoning tokens, so bill `completion_tokens` only (adding `reasoning_tokens` would double-count). Streams: drop any reasoning delta before it reaches the device. |
| `cloud_gateway/providers/__init__.py`, `config.py` (`AdapterKind`) | Register `meta`; remove `nebius`. |
| `cloud_gateway/defaults.toml` | `[slots] primary="meta"`; `[providers.meta]` with the aliases above; prices $1.25 input / $0.15 cached / $4.25 output per 1M tokens (confirmed for 1.3, 1.2 and 1.1). |
| `cloud_gateway/custody.py`, `secret_scan.py` | `META_API_KEY` environment secret (Meta's docs call it `MODEL_API_KEY`; ours is a gateway-only name) and keychain account `meta_api_key` under service `jana-meta.cloud-gateway`; remove the Nebius and Tavily sources; add a Meta key pattern (keys look like `LLM_<digits>_<secret>`; the secret's alphabet is **(verify)**). The `tvly-` pattern stays in the scanner as `legacy_search_key` (done 2026-10-26): an old Tavily key may still be on the machine, and catching it costs nothing. |
| `services/agent-core/agent_core/router/cloud_models.json` | Two aliases with Spark's context (1M advertised; cap the engine at 131072 to bound cost), max output 16384 (reasoning tokens share the budget), `vision: true`, prices. |
| `agent_core/router/router.yaml` | Comments and tier lists name Spark; `cloud.send_photos: true` (still gated by the photo notice, §5). |
| `cloud_gateway/study.py` | Remove the Nebius branches (~507, ~542, `structured_math = provider == "nebius"` ~1048, malformed-verifier retry ~1643); use the generic path. |
| `scripts/jana_tools/hackathon_app.py` | Expect `slots.primary == "meta"`; `GatewayHop` forwards the device's request unchanged (adding provider fields there broke the gateway's device contract); env vars `JANA_META_*`. Done. |
| `apps/desktop/dev/sidecar.ts`, `scripts/jana_tools/hackathon_dev.py` | Same renames; default data dir `jana-meta-browser` in the system temporary folder; provider keys scrubbed from child processes. Done. |
| `services/cloud-gateway/deploy/meta-dev.toml` (rename of `nebius-dev.toml`) | Meta slot; $10 a day, $120 in total, valid until 2026-11-09 (judging); ledger in `~/.jana-meta/gateway`, outside `/tmp`; `[tavily]` removed. Done. |

### 4.3 Budget fixes that matter with $150 of credit

From the 2026-10-25 review; both protect the credit (images: done; dropped streams: done 2026-10-28):
- A dropped stream is recorded at $0 (`cloud_gateway/app.py` ~283–302). Charge at least the input estimate on
  disconnect and record `client_disconnected`.
- `InferenceBudget.reserve` refuses image content parts (`inference_budget.py` ~70–73). Allow image parts and price
  them: Spark bills images as input tokens (about 1,300–1,500 for a ~1280 px image; no flat rate), so bound each
  image at a fixed token allowance instead of the current 2× body-bytes rule; SAM is $2.50 per 1,000 images.

### 4.4 Day-1 checks (before building on Spark)

1. Tool calling with `tool_choice: auto` and the engine's tools: the Solver calls tools on 10 seeded items.
2. `json_schema` output with `tutor-turn.schema.json` validates first time on 10 Coach turns.
3. Streaming with `stream_options.include_usage` returns usage, including reasoning tokens.
4. Image input (`image_url` data URL) is accepted.
5. Latency: time to an accepted Coach turn at `reasoning_effort: low`. Target ≤ 3 s typical (§12).
6. 1.2 vs 1.3: pick the one that passes 1–4 with the better latency.

Results (2026-10-26, `jana_tools.meta_checks`): 1 tool calls 10/10; 2 bare-prompt Coach JSON 0/10, failing only the
schema's conditional rules, which the engine's own prompt and retry meet in real turns; 3 usage on the final chunk;
4 images read correctly; 5 Coach 6.0 s at `low`, 3.8 s at `minimal`; 6 1.3 kept (same price, recommended).

**Done when:** (met 2026-10-26) `test_m19_gw_conformance.py` runs with the `meta` provider, and a typed maths and a typed physics
question each complete a full tutoring turn on Spark in the browser demo host, with checked numbers.

## 5. Online vision: Muse Spark + SAM 3.1 (JM-D10)

### 5.1 Flow

1. **Local privacy pass first** (unchanged): the perception worker screens faces and people, crops, deskews,
   masks private text, outputs ≤ 1600 px JPEG. Nothing leaves the device before this and the photo notice.
2. **Spark reads** (`engine/vision.py`, `PhotoReader.read`): the existing `reader_output` — question text, regions
   with `bbox` (0–1000 scale), `number_label`, `diagram_description`, `refusal`.
3. **SAM 3.1 sharpens** (new): for each region Spark returns, call SAM 3.1 through the **Responses API**
   (`POST /v1/responses`, `model: "sam-3.1"`) with box prompts converted from Spark's 0–1000 grid to the image's own
   pixels (clamp 1001 to 1000). For diagrams, a separate request with a text concept ("force arrow", "angle label"):
   a request takes a noun phrase **or** box/point prompts, never both, one concept per request, at most 16 prompted
   objects. Result: a mask and tight box per region (box/point prompts always return `one_bit` masks).
4. **Spark re-reads crops** only when the first read marked a region uncertain (`[?]` tokens or low-confidence
   numbers): crop by the SAM mask, send the crop, merge. One extra call at most per photo.
5. **Pointing on the learner's photo**: masks become pointer targets on the photo, so the tutor's `<point at>` cue
   (`engine/pointing.py`, `client-core/src/pointer.ts`) highlights the exact line of working or part of the diagram
   ("this line is where the sign changed").

### 5.2 Uses in the demo

- **Marking photographed working line by line**: SAM separates the lines; the Checker marks each line; the first wrong
  line lights up on the learner's own photo.
- **Diagram questions**: SAM finds every arrow or label in a physics diagram so Jana can ask "which of these is the
  normal force?" by pointing, not describing.
- **Diagram drill** (done 2026-10-26; the research agent reuses it, §18): "Photo of a diagram to learn" in the tutor's
  composer (capture purpose `diagram`). Spark names each labelled part and boxes the part and its printed label; SAM
  outlines the part; the student confirms the names. "Learn the parts" names a tapped part; "Practise" covers the
  printed labels and asks "Tap the …"; each tap is marked by code (`client-core/src/diagram-drill.ts`: inside the
  outline, smallest part when parts nest, a finger's width of slack); two misses show the part; the end says how many
  were found first time. Label covers use the device's own OCR line that names the part, since Spark's label boxes
  were a line off in testing. Parts' roles are not shown (unchecked model text); study packs add verified roles (§18).
  Measured on a synthetic labelled plant diagram (live Spark + SAM): all 5 parts named, 4–5 of 5 outlined by SAM (an
  unoutlined part keeps its box), read ready in ~15–20 s, a wrong-part tap and a right tap marked correctly.

### 5.3 Changes

| File | Change |
|---|---|
| `cloud_gateway/providers/sam.py` (new) + route `POST /v1/vision/segment` | SAM 3.1 client over the Responses API: image + box/point prompts or one text concept → boxes and masks. The reply is special-token text in `output_text` (`<\|box;…\|><\|mask;x=..;y=..;data=H,W,~payload\|>`, base85, lossless `~` or one-bit `!`); decode with Meta's `meta-sam-parser` or our own parser, and treat an empty `output_text` as "no match", not an error. $2.50 per 1,000 images (confirmed); budgeted like chat. |
| `agent_core/engine/vision.py` | After `read()`, call the segment route for returned regions; attach masks; optional crop re-read. Offline fallback: Glimmer's own read with boxes only (no SAM offline). |
| `agent_core/engine/pointing.py`, `packages/client-core/src/pointer.ts`, `packages/ui/src/composer/CaptureDiagrams.tsx` | New pointer target kind `photo_region` (mask outline drawn over the learner's photo). |
| `cloud_models.json`, `router.yaml`, `inference_budget.py` | Enable cloud vision (§4.2, §4.3). |

**Done when:** a photo of three lines of handwritten working with one sign error is read, the wrong line is
highlighted on the photo, and the tutor asks about that line, within ~6 s of upload.

## 6. Speech (JM-D12, JM-D13)

### 6.1 Online speech to text: Muse Voice Transcribe

`wss://api.meta.ai/v1/asr/realtime` (confirmed). The first JSON frame, within 10 s, carries
`authorization.accessToken: "Bearer <key>"` (an HTTP header is ignored), `model: "muse-voice-transcribe-1.0"`,
`audioEncoding: "PCM_24KHZ"`, `mode: "ENDPOINTING"`, `languageBias: ["English"]` (language names, not codes) and
`keywords` from the curriculum glossary; neither can change mid-session. Wait for the acknowledgement before sending
audio, paced at real time (at most 5 s ahead). Server events: `speechStart` → Heard(begin), `transcript` →
Heard(partial) (cumulative: replace, don't append), `speechEnd` → Heard(end), `speechComplete.transcript` →
Heard(final). Barge-in stays ours (cancel TTS on `speechStart`). $0.18 per audio hour, billed per second. Sessions
are capped at 60 minutes (close 1011) and the server closes a stream that stops sending audio, so the gateway sends
PCM silence between turns or reconnects; `endStream` ends the whole session.

| File | Change |
|---|---|
| `cloud_gateway/providers/meta_speech.py` (new) | `MetaRecognizer` / `MetaRecognition` implementing `Recognizer` and `Recognition` from `providers/speech.py`. Done 2026-10-27 (branch `claude/bold-bardeen-60a405`); the server's end of speech is held at least 600 ms; keywords fit Meta's limits (at most 500, each at most 30 characters, measured live), the session's subject first. |
| `cloud_gateway/voice.py`, `config.py` | Build `SpeechStack(MetaRecognizer, live=None, <synthesizer>)`; replace `config.voice_google` with `config.voice_meta`; `voice_enabled=true` in the dev config. With `live=None` the TTS-only reader path is used (it already exists as the drift fallback). Done: the synthesizer is Kokoro (§6.4); the development-only NVIDIA synthesizer was removed 2026-10-28. |
| `cloud_gateway/voice.py` (~1054–1067) | Re-check quota and credential every turn (review finding: sessions currently run past caps). Done (branch `claude/bold-bardeen-60a405`): credential, operations and quotas before each turn. |

### 6.2 Online text to speech: Kokoro-82M

The gateway reads accepted sentences with Kokoro-82M (`providers/kokoro_speech.py`, a worker under the speech
runtime's interpreter), resampled for the bridge. NVIDIA's API-catalog trial voice was used in development until
2026-10-28; the trial forbids distributing its audio, so its synthesizer, configuration and key source were deleted.
Study Podcasts keep their route (`podcast_speech.py`, `/v1/podcast/voice` and `/v1/podcast/speech`), which reads each
frozen passage with the same Kokoro synthesizer; reading them with Kokoro on the device, offline, is §18's open item.

### 6.3 Offline speech to text: Omnilingual ASR, gated

Omnilingual ASR is per utterance (clips under 40 s), which fits Jana's VAD-endpointed turns. It is a new
`speech_to_speech` STT handler: add `"omnilingual"` to `SpeechProfile.stt` and the allowed engines
(`agent_core/store/speech_packs.py` ~45), its arguments in `net/voice_sidecar.py`, and package the 300M model in the
dev speech pack (`apps/desktop/dev/speech_pack.py`).

**Gate (day 3):** on the demo laptop, a 10 s English utterance transcribes in ≤ 0.6 s, and word error on 20 recorded
physics questions is no more than 2 points worse than faster-whisper `small.en`. If it fails, faster-whisper stays the
offline default. English only (JM-D18): no other input language is offered.

### 6.4 Offline text to speech, and the licence rule for demo audio

- Offline: Kokoro-82M (`af_heart`), unchanged.
- Online: Kokoro-82M served by the gateway (Apache-2.0), so the audio judges hear is licence-clean.

**Done when:** a spoken physics question gets a spoken, checked answer online in ≤ 4 s typical from end of speech
(filler at 1.5 s), barge-in stops playback, and the same works offline after the network is pulled.

## 7. Local inference: Muse Glimmer 30B (JM-D11)

| File | Change |
|---|---|
| `agent_core/router/recommended_models.json` | Replace the Qwen/Gemma entries with `muse-glimmer-30b` (dense 30B; GGUF `meta-models/Muse-Glimmer-30B-GGUF`, file `Muse-Glimmer-30B-KQuant-17GB-Q4_K_M.gguf`, 16.8 GB), class `high` only (32 GB+), `context_for_agents` 16384 (native 131,072), `max_output` at least 8192 (long reasoning can use up 4096 and return empty content with `finish_reason: "length"`), `thinking.available: true`, `default: on` (reasoning cannot be turned off), sampling temperature 1.0, top_p 0.95, top_k 64. One tool call per turn (no parallel calls). Done 2026-10-28: the Qwen and Gemma entries are removed; the router keeps their ids only for an already installed model. |
| `agent_core/router/router.yaml` (`local:`) | Budget Glimmer's reasoning rather than disable it: `chat_template_kwargs.reasoning_strength` (`low`…`xhigh`, default `high`) per request, and a hard cap with llama-server `--reasoning-budget N` (`reasoning_effort` is not implemented by llama.cpp); `thinking_budget` must still equal the `keys.py` value its test checks. Tiers list only `local:muse-glimmer-30b`. |
| `agent_core/providers/llama.py` | Use the chat template embedded in the GGUF (no `--chat-template-file`); llama.cpp `b10353` or newer with `-a muse-glimmer`; reasoning arrives in `message.reasoning_content` and must stay out of the released text. Whether a JSON-schema grammar works from the first token with a model that always reasons is **(verify)**. |
| `scripts/jana_tools/hackathon_dev.py` | `--local-model` takes the official Glimmer GGUF instead of Nemotron Nano 4B; Meta publishes no SHA-256, so record it on first use and pin it (whether the launcher may download weights itself, against its current "never downloads" rule, is an owner decision, §15). Drop `--reasoning off`; size `--ctx-size`/`--parallel` for 32 GB. `hackathon_app.connect()` keeps the `local` provider so offline works. |
| Model pack | Glimmer ships a vision projector, `mmproj-Muse-Glimmer-30B-Q4_K_M.gguf` (1.4 GB): include it as `vision_projector` so offline photos work. |
| Hardware class | The high class needs 25 tokens/s (`keys.py` ~477). Meta publishes no laptop tokens/s or RAM figures for Glimmer, so measure on the demo laptop on day 1–3; if it benchmarks below, the class rule (not just the model list) must change or Glimmer is excluded. |

**Measured 2026-10-26** on an Apple M4 Max (128 GB, llama.cpp build 11429, Q4_K_M with the vision projector, 16K
context; weights verified against Hugging Face's SHA-256): generation 27 tokens/s on a short prompt and 24 tokens/s
with 3K tokens of context; prompt reading ~230 tokens/s. One Coach-sized call with a 3K-token prompt took ~36 s, most
of it reasoning (~580 tokens at `reasoning_strength: low`). The replies were properly guiding on a short prompt.
`--reasoning-budget 96` had no visible effect **(verify the template's thinking tags with llama.cpp)**. A full engine
turn (4–5 calls) would take minutes even on this machine, and a 32 GB laptop with less memory bandwidth will be slower
still, so the power-cut demo needs a lean offline path: fewer calls (the engine's own deterministic steps where they
exist), short prompts (the low-class lean prompts), capped reasoning, and streaming the Coach; and the demo laptop's
own numbers before the class gate is set.

**Why it is slow and what helps** (A/B on the same machine, 2026-10-26): generation is bound by memory bandwidth (a
dense 30B reads ~16.8 GB per token, so the M4 Max tops out near 32 tokens/s; 27 measured idle). Other work on the
same machine halved it (12 tokens/s with two other llama-servers and test runs going), so the demo laptop must run
nothing else. **DFlash speculative decoding** (`dflash-Muse-Glimmer-30B-Q4_K_M.gguf`, 1.6 GB, verified; `-md …
--spec-type draft-dflash -ngld 99 --spec-draft-n-max 4`) raised generation 30–45% on short prompts (≈45% of drafts
accepted) and did not help on a 2,600-token prompt. At `reasoning_strength: low` Glimmer reasons only ~150–250 tokens,
so a 256-token `--reasoning-budget` never bound. The biggest per-call cost is reading the prompt (~230 tokens/s):
keep each role's prompt cached in its own server slot (a repeated 3,000-token prompt read in ~0 s), use the short
low-class prompts, make fewer calls per offline turn, and stream the Coach. Replies stayed properly guiding throughout.

Power cut: when the gateway is unreachable the router falls to `local:muse-glimmer-30b` and the offline speech pack
(§6.3, §6.4); the UI shows "Working offline".

**Built 2026-10-27 (W3).** `hackathon_dev --local-model <Glimmer GGUF>` checks the GGUF, projector and draft
against pinned SHA-256s and starts llama-server with `--jinja`, `--alias muse-glimmer-30b,muse-glimmer`, the
projector, DFlash (`--spec-type draft-dflash --spec-draft-n-max 4`) and four 8,192-token slots (Coach, Solver,
Diagnoser, auxiliary: each role's prompt stays cached in its own slot); `--reasoning off` is gone. The adapter sends
the router's effort as `reasoning_strength` (its lowest, `low`, where other models' thinking is off), and a local
model that always reasons gets 1,024 output tokens of room on top of the role's cap (a 24-token auxiliary cap had
ended inside the reasoning). With `offline_lean_classes` (on for the browser host) a turn the Coach's local model
serves runs as the low class (short prompts, lean shapes, no guard or title call), and a practice hint is the
authored rung shown at once instead of the Coach's rephrase. Power cut: the gateway's 502 `upstream_unreachable`
now counts as the network gone (served locally at once, no retries with backoff); a cloud call still unanswered
after 5 s has the network probed and is dropped to the local model when the probe fails; `cloud_offline` resets once
a probe succeeds, and a turn the cloud would have served asks for a probe while offline. The browser host's probe
asks its own gateway `GET /v1/ping?upstream=1` (Meta's host takes a TCP connection), since a gateway on the same
laptop answers its own ping with Wi-Fi off.

**Measured 2026-10-27** (M4 Max, the browser host as above). Caveats: the machine was not quiet (load average
30–200 from other sessions' test runs and a Docker VM; Glimmer generated 12–20 tokens/s against 27–33 idle), and the
power cut was simulated by pointing the gateway at a Meta host that does not resolve, the failure Wi-Fi off gives,
because switching Wi-Fi off would have cut the measuring session off. Repeat on the demo laptop with Wi-Fi off.

| Check | Result |
|---|---|
| Practice: answer → mark | 47 ms and 206 ms, no model call ✔ |
| Practice hint offline | 1.2 s including opening the tutor, the authored rung, no model call ✔ (the Coach's rephrase took 38.6 s) |
| Mock paper (Mathematics Paper 1, set 1) | opened in 60 ms; submitted and marked in 230 ms, with marks by topic ✔ |
| Cloud on, gateway cannot reach Meta | the turn skipped the cloud at once ("Cloud tutor unavailable. Using the tutor on this computer."), the probe having found Meta unreachable ✔; a stalled call falls back at the first probe after 5 s (tests) |
| Network back | a turn started 12 s after Meta was reachable again ran its first call on Glimmer and its Coach on Muse Spark (3.6 s): its own probe request brought the cloud back mid-turn ✔ |
| Typed free-form question on Glimmer | 29.6 s, 39.9 s, 47.7 s to the reply ✘: Diagnoser 7.6–17.9 s (140–300 output tokens), then Coach 15.3–21.9 s (240–490 output tokens, about 250 of them reasoning); the slowest had a second Coach call when the `verified` gate refused a number. Replies properly guiding |

Why 8 s is not met, and what would meet it: even on an idle machine one Coach call is ~13–15 s (cached prefix,
~250 reasoning tokens, then the reply at ~30 tokens/s), and the engine shows nothing before the release gates pass
(API-10), so the first words arrive with the whole reply. Meeting 8 s needs both (a) one model call for a
definition-style question offline, with the Diagnoser replaced by the pack index's best topic (a deterministic
step; the guess already matches 90–97% of items, §12), and (b) streaming the Coach's `say` with each sentence
gated as it completes (leak and number checks per sentence; one-ask and length at the end), which changes API-10
and is the owner's decision (§12 left streaming to the owner). Also seen: the Reflector's background job ran 28 s on
Glimmer after a turn, competing with the next turn for memory bandwidth.

**Done when:** with Wi-Fi off on the demo laptop, practice keeps marking instantly from the packs (authored hints
served without a model), a mock paper opens and marks, and a typed free-form question gets a streamed, checked
Glimmer reply with its first words within ~8 s. A spoken offline turn is a stretch goal (W4).

## 8. Removals and the adult product (JM-D14, JM-D15)

### 8.1 Remove

| What | Where |
|---|---|
| Nebius adapter, Nemotron ids and prices | `providers/nebius.py`, `providers/__init__.py`, `config.py`, `defaults.toml`, `custody.py`, `cloud_models.json`, `deploy/nebius-dev.toml`, `test_nebius.py` |
| Tavily | `cloud_gateway/tavily.py`; `app.py` (~126–128, routes ~434–440); `ask.py` (branches ~213–249, ~316); `config.py` (`TavilySettings`, validator ~377–387); `custody.py`; `secret_scan.py`; `agent_core/api/study.py` (`/v1/study/web` ~593–656); `client-core/src/study-workspace.ts` (~291); `client-core/src/ask-anything.ts` (`web_confirmed`); UI `StudyWorkspace.tsx` (~243); i18n `ask.web_permission`, `ask.search_web`, `study.web_consent`, `study.import_web`; tests `test_tavily.py`, `test_study_web.py` |
| Google/Gemini cloud stack | Deleted 2026-10-28: the Gemini and Vertex adapters, their tests, the Gemini-shaped test stub (the gateway's tests now use a Meta stand-in), the live Gemini and Vertex staging tests, the old production release material (`M42.md`, the release handoff, `deploy/m42-*`, the systemd unit, `jana_tools/release/m42.py` and `m42_quality.py`, which named the production GCP project and an IAP command with the owner's email) and the Google mypy override. Kept: the secret scanner's Google and NVIDIA key patterns, and the authoring records of curriculum items and quantity proposals that name the model that drafted them. |

**Ask anything after Tavily:** out of the demo (§14). Without a search backend `/v1/ask` returns "unavailable"; web
research lives in the research agent (§18). **Study:** file and paste import stay; web-page import is removed (done).
Tavily removal: done. Google stack: deleted (2026-10-28).

### 8.2 Adult product

| Area | Change |
|---|---|
| Sign-up | Age field (whole number of years, 1 to 120; was a date of birth until 2026-11-01); under 18 → blocked with a short explanation. Store `age_band = "18_plus"` (`store/profiles.py` `ADULT_BAND`). Done in the app; the engine-side check is still open (§17 W5). |
| Ask policy | `engine/ask_anything.py` `policy_for()` and `cloud_gateway/ask.py` audience: adult only; the `under_18` branch is removed from the UI. |
| Consent | Keep per-feature consent (the learner's own consent now). Remove guardian flows: `store/subscription.py` guardian consent, `plans.toml` `jana_family`, UI `ParentSummary.tsx`, `FamilyControls.tsx`, guardian parts of `OnlineFeatures.tsx`, `Studies.tsx`, `StudyWorkspace.tsx`; `engine/parents.py` not wired. |
| Copy | Rewrite `parents.*`, `settings.study.needs_guardian`, `study.access.guardian`, `error.guardian_consent_required` and related keys for an adult managing their own settings; the study banner "A parent or guardian needs to approve" becomes the learner's own consent prompt. |
| Safety | Keep the input guard, distress templates and all release gates. "Trusted adult" wording in `study.safety.tpl.*` becomes adult-appropriate support wording. |

### 8.3 Credit budget

$150 of Meta credit for 10 days. Dev config: $10/day cap and $120 total, leaving $30 for judging. Output tokens
dominate (reasoning is billed as output), so Coach `reasoning_effort` stays low and `max_tokens` is clamped per role.
SAM: ≤ 300 images over the event (~$0.75).

## 9. Submission scope (JM-D17, owner signs off)

The Official Rules grant the organisers a perpetual, irrevocable, royalty-free licence to the Submission. Submit only
what `scripts/build-submission.sh` puts in the tree (revised 2026-10-27 after a trial install, §17 "§9 does not
install"; **the owner signs off this list**):

- the engine (`services/agent-core`, `services/tool-worker`, `services/perception-worker`), the cloud gateway (with
  the research agent, §18) and `services/study-worker` (agent-core and the gateway depend on it), the desktop app
  (`apps/desktop`), the shared packages and `assets/`;
- `services/pack-builder` and `services/signing-service`: the browser host builds and development-signs the packs
  from their sources on first launch (`apps/desktop/dev/seed_packs.py`), so the entry does not install without them.
  Only the published development key is used; no release key or signing record ships;
- **Mathematics, Physics and Chemistry** content packs with their shared `ref/common` lists (owner, 2026-10-27:
  Chemistry ships, so the titration predict-before-you-see sim has its lesson and misconception behind it);
  `--no-chemistry` leaves it out; Accounting stays out;
- `contracts/`, `content/agent/`, `skills/`, `evals/` without `evals/held-out` (the tests read the corpora and
  fixtures; every eval image is synthetic and `LicenseRef-Own`), and the tooling the app and its tests run:
  `scripts/jana_tools` (codegen, the browser host), `scripts/codegen`, `scripts/ci` (browser test drivers) and
  `scripts/governance/shipped-assets.toml` (the app imports this asset licence register);
- from the gateway's `deploy/` folder only `meta-dev.toml`;
- not: `apps/studio`, `apps/prototype-s0`, `services/ingest`, `SPEC.md`, `FEATURE_IMPORT.md`,
  `contract-additions-*.json`, the rest of `scripts/governance/`, `scripts/tests`, `scripts/packaging`,
  `scripts/release`, `.github/`, `AGENTS.md`, `.env.example`, `CONTRIBUTING.md` (it says the packs are CC BY 4.0,
  which contradicts the licence below) and `evals/held-out`.

The tree is built from one commit with `git archive` and committed as the first and only commit of a new repository
(no history; the author is this repository's git user). pnpm, uv and Cargo workspaces drop Studio and the ingest;
the lockfiles are regenerated for that workspace without changing any pinned version; `skills/teaching` holds only
the shipped subjects (`skills/counts.toml` follows). Build it with
`scripts/build-submission.sh [--no-chemistry] --verify <empty folder>`; `--verify` installs a copy from its lockfiles
and runs the Python, TypeScript and Rust suites there. Tests that read the private contract additions, or a pack
the tree leaves out, skip there or are deselected in the tree's pytest configuration (the list is in the script).
Licence: Apache-2.0 for code; content packs under the owner's licence (`LicenseRef-Own`).

## 10. Demo-visible bugs to fix (from the 2026-10-25 review)

Status 2026-10-26: #1, #4 and #6 done; #5 partly done (parallel session: distress screening on the explain-back and
visual-answer routes). Status 2026-10-27: #2, #3 and #7 done.

1. Maths starting with a digit shows as raw LaTeX (fixed in Jana main, uncommitted:
   `packages/ui/src/learn/PackText.tsx` and `agent_core/engine/assessment/items.py`; port it).
2. The subject switches from Mathematics to Physics mid-question; "Next up" and Practice recommend Physics after a
   Mathematics placement. **Done 2026-10-27**: the Diagnoser's chosen topic now decides the question's subject (its
   free `subject` field counts only when it chose no topic, `team.question_subject`), and once any subject has
   evidence the planner ranks never-started subjects and their ideas after the started ones (`planner.unstarted`).
3. The composer accepts questions with no model available and never says so. **Done 2026-10-27**: `tutorReach`
   (client-core) reads the model state and the connectivity slice; with no tutor model on this computer and the
   online tutor switched off or out of reach, Home's Ask box and the tutor's dock say so and offer practice and a mock
   exam (`NoTutor`). Not covered: a spent budget, which the connectivity state does not carry.
4. A message the core refused is re-sent on every reconnect (`packages/client-core/src/session.ts` ~393, ~472).
5. The learning-journey route skips input screening (`test_a1_input_routes.py`), if not already fixed upstream.
6. Tutor picker: radios announced as raw keys (`avatar.*`); "Choose this tutor" disabled when the default is picked.
7. Unit field and °C/Ω chips on unitless numeric answers. **Done 2026-10-27**: the numeric item input gains
   `unit_expected` (commands contract); the client shows the unit field and its symbols only when it is true.

## 11. Tests to update

- Gateway: `test_nebius.py` → `test_meta.py`; `test_m19_gw_conformance.py`, `test_m19_gw_keys.py`,
  `test_inference_budget.py` (images allowed), `test_m42_study.py`, `test_study_math_format.py`, `gateway_stubs.py`
  (Meta stand-in); removed `test_tavily.py` and the Gemini and Vertex adapter tests; `test_podcast_speech.py` reads with Kokoro. New:
  `test_meta_speech.py` (Recognizer against a fake socket), `test_sam.py` (segment route, budget).
- Agent core: remove `test_study_web.py`; update `test_a1_input_routes.py`, `test_study_podcast_speech.py`; new tests
  for `photo_region` pointing and the Glimmer model entry.
- Scripts: `test_hackathon_app.py`, `test_m42_release_preparation.py`.
- TypeScript: `client-core` `ask-anything.test.ts`, `study-workspace.test.ts`; `ui` `ask-anything.test.tsx`,
  `study-workspace.test.tsx`; `i18n` catalogue checks.

## 12. Latency budget (measure on days 1–3)

**Re-baselined 2026-10-26** after measuring: the original table below is the voice ambition; the working targets are
**first words of the reply ≤ 3 s** (stream the Coach), **a typed turn ≤ 8 s**, spoken replies starting ≤ 4 s after
the end of speech with a filler at 1.5 s, and offline: pack hints instant, Glimmer's first words ≤ 8 s. A guided
typed turn measured 12.8–15 s after the effort change (§4.1).

**Where a turn's time goes** (live traces, 2026-10-26 evening; Spark 1.3 through the gateway, efforts as in §4.1):

| Turn | Total | Calls (each: time, reasoning tokens) |
|---|---|---|
| New question | 18.4 s | Diagnoser 5.1 s (543) → Solver 2.3 s tool call + 5.9 s (646) → Coach 2.0 s (209), first token 1.7 s |
| Step with words and numbers ("add 7 to both sides") | 10.2 s | Checker 2.5 + 3.1 s ∥ Diagnoser 6.1 s (506) → Coach 1.8 s, first token 1.2 s |
| Step the code checked ("4x = 28") | 7.9 s | Coach 4.9 s, first token 4.2 s |

The Coach's first token is 70–90% of its call (Spark reasons before it writes, ~100–250 tokens even at `minimal`), so
**streaming the Coach's text would bring first words forward by only 0.3–0.7 s**, and it would have to show text
before the release gates finish (API-10). Not pursued without the owner's go-ahead. The morning's correction retries
(15 of 21 first Coach replies failing the schema, each costing a second call) did not recur in four turns that evening.
The time is in the number of sequential Spark calls and Spark's reasoning before its first token.

**Speculative Solver** (done 2026-10-26, owner's choice over streaming): on a new question served online, the Solver
starts beside the Diagnoser with the teaching skill of the pack index's best-matching KC (the Diagnoser's first
candidate; no model call). Its plan is used when the diagnosis gives the same teaching skill; otherwise it is dropped
and the Solver runs with the diagnosis as before, so a wrong guess costs one Solver call (~$0.005) and no time. It is
dropped when the diagnosis ends the turn without a plan (a clarifying question, a definition, the topic chooser, a
Stop), and never runs on local models (one call at a time) or with `speculative_solver` off (`config/keys.py`).
Offline check over 3,203 pack items: the guess picks the item's own teaching skill for 97% of maths and 90% of
physics items. Live: two new questions took 15.2 and 15.3 s (the same calls in sequence: 18.4 and ~19.1 s); both used
the guess. The critical path is now the input guard (~3 s, before anything) → the Solver's tool call and plan
(~9–11 s) → the Coach (1.5–3 s). Next candidates: start the guess beside the input guard (its text goes to the same
place; nothing is shown before the guard passes), and the Solver's two sequential calls.

| Step | Target |
|---|---|
| End of speech → final transcript (Voice Transcribe) | ≤ 0.7 s |
| Filler if no reply yet | at 1.5 s |
| Engine turn on Muse Spark (guard, tools, Coach, gates) | ≤ 3 s typical |
| Kokoro first audio after an accepted sentence | ≤ 0.4 s |
| **End of speech → first answer audio** | **≤ 4 s typical** |
| Photo upload → highlighted line (Spark + SAM) | ≤ 6 s |

Levers if slow: one Spark call for Coach+Solver on simple turns; the conceptual path for definitions; skip the crop
re-read.

**Measured 2026-10-26** (Muse Spark 1.3 through the gateway, browser demo host, typed questions): a full guided turn
took **21–25 s** ("Solve 7x − 3 = 18", the car-acceleration question). Per call: Diagnoser ~5 s (≈700 reasoning
tokens at low), Solver tool call 1–4 s, Solver plan **7–14 s** (1,400–3,600 reasoning tokens at high, sometimes a
second round), Coach ~4 s; Coach alone at `minimal` 3.8 s median versus 6.0 s at `low`. The 4 s voice target needs
the levers above, plus Solver effort below `high` and running the Diagnoser and Solver less often, before voice work
(W4) can meet §12. Photo marking (2026-10-26, three handwritten lines, Spark + SAM through the gateway): local privacy
pass 0.4 s; Spark's structured read 2.1–6.3 s; SAM 2.2–4.2 s, run while the student confirms the reading; upload to a
confirmable reading 4.6–6.7 s; the wrong line lit 0.04 s after confirming and the tutor's question 2.7–3.8 s after. A
photographed free-body sketch: read and outlined in 13–15 s (more elements), the sketch turn 2.5–3.6 s. Day-1 checks:
tools 10/10, streaming usage, image input pass; bare-prompt Coach JSON failed only the schema's conditional rules
(if/then is not enforced by constrained decoding), which the engine's own prompt and retry handle.

**Measured again 2026-10-26, after the latency work** (`uv run python -m jana_tools.turn_latency --repeat 2`: ten
seeded Maths and Physics turns, eight openings and two follow-up answers, through the shipped engine with the tool
worker and the installed packs, against the gateway's Meta adapter and ledger in process): **median 8.7 s** over 20
turns (passes of 9.5 s and 7.9 s; an earlier single pass 7.9 s), openings 9.0 s, follow-ups 4.4–9.9 s, p90 14.6 s;
20/20 kept the rules (plans verified by tools, every board number checked, nothing withheld shown, no degraded turn).
Per call (median): input guard 1.25 s, Diagnoser 2.5 s, Solver 1.6 s per call (one tool call, one plan), Coach 2.1 s,
Checker 1.6 s. A call costs about 0.9 s plus 0.37 s per 100 output tokens; Spark still reasons 100–500 tokens at
`minimal`, and about one call in 25 is slower than that by 1.5–8 s, which sets the tail. Muse Spark 1.2 was no faster
(median 11 s). What changed: the Solver at `minimal`; one tool round with the units check, then a named plan phase;
a plan step on the way to a checked answer is checked at that answer instead of refusing the plan; an empty optional
`sketch_wanted` no longer costs a Coach retry; the rule matcher's judgement and the session title run alongside the
specialists; no guard model call for a line of working or a "Solve …" question (its patterns, classifier and redaction
still run); and (on main, 577fa5f) `phys_circuit`'s self-referring schema, which Spark refused with a 400 on every
physics Solver call, is unrolled. An opening is still five calls in a row (guard, Diagnoser, Solver tool, Solver plan, Coach), so ≤ 3 s needs
fewer of them: running the guard alongside the Diagnoser (about 1.2 s; `test_agt02` now requires no other call when
the guard answers), the Coach alongside the Solver's plan (about 1.5 s; the opening note now depends on the plan), or
streaming the Coach's `say` to speech before the gates finish.

**Measured 2026-10-27 on main 51c07ec** (with the speculative Solver and the Checker's error-category line;
`turn_latency --repeat 2 --wrong-answers`, the ten seeded turns plus five wrong answers that run the Checker): the ten
seeded turns **median 7.2 s, p90 11.4 s** over 20 turns (openings 7.8 s); all 30 turns 7.4 s, p90 12.4 s; 30/30 kept
the rules. Per call (median, seeded turns): input guard 1.15 s, Diagnoser 2.7 s, Solver 1.7 s, Coach 2.0 s, Checker
1.8 s, rule matcher 1.4 s, title 1.3 s (on 2026-10-26: 1.25, 2.5, 1.6, 2.1, 1.6 s in the 8.7 s run; 1.19, 3.65, 2.44,
2.24, 1.79 s in a 12.6 s run during a slow Spark period). The Solver now starts beside the Diagnoser, so an opening is
four calls deep (guard, Diagnoser beside the Solver's tool call, Solver plan, Coach). Checker verdicts redone by a
decode-only call: 6 of 13 (46%), none for the incorrect-needs-a-category rule (3 of 14 before the line), all six for an
error category outside the contract's list (`calculation`, `calculation_error`, `wrong_value`, `substitution_error`),
about 1.4 s each; the role prompt names no categories. The 30 turns spent $0.79 and left $0.37 of holds (dropped
speculative and timed-out calls keep their bound). With the categories listed in the Checker's prompt (216b681), 14
wrong-answer turns gave 14 verdicts and no redo, each in two Checker calls (tools, then the verdict); those turns took
7.2 s median, p90 11.1 s.

**Measured 2026-10-27, spoken turns (W4)** (Muse Voice Transcribe and Kokoro through the gateway; times from the end of
speech in the recording). The runs below the first bullet used an earlier recognizer on this branch; after merging
`claude/bold-bardeen-60a405`'s recognizer, three recorded questions were re-measured: final transcript 1.08–1.22 s,
**filler audio 1.38–1.52 s**, Kokoro's first audio 0.28–0.37 s, first answer audio 8.5–12.8 s (engine 7.1–11.2 s).
That re-run first failed every handshake: Voice Transcribe refuses more than 500 keywords and any keyword over 30
characters (an `invalid_request_error`), which the glossary list of 1,368 terms exceeded; both limits are now applied.
- *Voice Transcribe alone* (a recorded 6.9 s car question streamed in real time): final transcript **0.6 s** after the
  speech ends (target ≤ 0.7 s); first connect and acknowledgement 3.4 s (hidden: the microphone opens at once and
  audio is held); 200 glossary keywords accepted.
- *`jana_tools.voice_latency`* (five recorded Maths and Physics questions through the gateway's real voice
  connection, answered by a real engine turn on Spark the way the voice adapter answers, on a heavily loaded laptop):
  after the changes below, **filler audio 1.57 s** median (1.40–1.81 s; target 1.5 s), gateway's final transcript
  1.27 s (Voice Transcribe's ~0.6 s plus the 600 ms hold), Kokoro's first audio **0.26 s** after the accepted words,
  engine turn 11.1 s, **first answer audio 12.6 s** median (11.4–14.6 s); 5/5 kept the rules. The earlier ten-turn run
  (before the hold, the 300 ms cloud filler and the replayed filler): transcript 0.67 s, filler 2.51 s, Kokoro 1.49 s
  under CPU contention, answer audio 13.3 s, 8/10 kept the rules (one question split at a sentence pause, one
  degraded turn).
- *Browser demo host* (tutor screen: hold-to-dictate, then Send, with read-aloud on; before JM-D20 the tutor had no
  voice bar): draft in the composer **1.5 s** after the speech ends (the key released 1.0 s after it); a guided, checked
  reply (units checked, the board's Given and Find) read aloud **18.1 s** after Send: the turn took 16 s, a fresh
  voice connection waited 2 s for a Voice Transcribe stream it did not need (the dev config now waits 0.3 s), and
  Kokoro's first audio came 0.2–0.3 s after each sentence was requested.
- **The ≤ 4 s target is not met and cannot be by speech work**: speech costs about 1.3 s before the turn and 0.3 s after
  it; the rest is the engine turn on Spark (7–16 s today). The filler plays at 1.5 s.
- Fixed on the way: Voice Transcribe ends a turn about 0.6 s into a pause, so "... through a resistor. What is its
  resistance?" became two turns: the gateway now holds its end of speech at least 600 ms; releasing hold-to-dictate
  waited out the 10 s silence it was held with (draft 10.3 s after the speech): a silence change now re-times the hold;
  an adult turning on Cloud voice never recorded the profile's `cloud_voice` consent (and no notice existed for it),
  and accepting "Use online voice?" was not announced, so voice was not offered until the next network event.
- Spend: Voice Transcribe about $0.03 for all runs (settled in the budget ledger); Spark about $1.05 (the harness
  runs and the browser turns; the ledger rose about $1.20 meanwhile, parallel sessions included). Kokoro and the NVIDIA trial voice (since removed) cost nothing.

**Measured 2026-10-27 (later), voice in the tutor (JM-D20)** (browser demo host on main c6b07c09 plus this work; the
recorded car question):
- *A spoken question on the tutor screen* ("Start a conversation", hands-free): the question was heard whole, the
  filler's audio began **2.6 s** after the end of speech (1.4–1.5 s in the harness; the extra second in the browser is
  not yet explained), and a guided, checked reply (worked out, units checked, the board updated) was spoken from
  **18.4 s**: "A car speeds up from rest to 20 m/s in 5 s and we want its acceleration. What do you think the
  acceleration is, with units?" The turn itself took about 15 s on Spark.
- *Hold-to-dictate, twice on fresh connections*: the release reached the core both times and the draft appeared
  **1.42 s and 1.45 s** after the end of speech. The hang (2 of 4 runs earlier) was a race: each dictation opens a
  fresh connection, the press can reach the bridge before the endpoint's `session.created`, and the bridge then rested
  as `idle` on the tutor screen; the client took that for the dictation's end and dropped the release. A held
  dictation now rests as `listening`. A second cause of hangs in the test runs was the browser's six connections per
  host: several open tabs of the app held them all, so a dictation's request queued.
- *After a restart* the core offered voice only at the next connectivity change, so the voice bar and microphone were
  missing for a profile that had already accepted Cloud voice; it now re-checks when a profile opens.
- *Keywords*: Voice Transcribe's 500 are filled with the session's subject first (the device names it in the voice
  URL), then the other demo subject; Accounting is never first.
- Spend for this round: Voice Transcribe $0.003, one Spark turn; the ledger showed $8.76 of today's $10 afterwards
  (spent and held, parallel sessions included).

**Measured 2026-10-27 (afternoon), why a spoken tutor turn took ~15 s in the browser against 7.2 s in
`turn_latency`** (the car question; browser timings from the turn traces in the dev data folder, harness timings from
`turn_latency`'s engine and in-process gateway run the same hour):
- *Per hop, browser spoken turn before the fixes* (end of speech = 0): Voice Transcribe's end of speech 0.76 s, the
  gateway's hold 0.60 s, request → filler words 1.32 s (filler audio 2.6–2.7 s); then the engine turn 15.6 s: input
  guard 3.0 s (timed out), Diagnoser ∥ speculative Solver 3.9 s, Coach 8.0 s in three calls (a schema correction
  retry, then a second iteration for a refused graph); Kokoro first audio 0.4 s after the accepted words, browser
  playback start 0.55 s after that; first answer audio 18.4 s.
- *The same hour in the harness*: typed 11.8 s, spoken wording 10.6 s, spoken in voice mode 13.2 s (every Spark call
  slower than the morning's 7.2 s run, and the guard timed out at 3 s on one of them): so about 4 s of the gap was
  that afternoon's Spark, not the browser.
- *Causes found and fixed*: (1) a spoken question writes small numbers as words ("in five seconds"), so a Solver plan
  restating the givens was refused as untraced and the Solver ran a second round (6.7 s); spelled-out numbers in the
  statement now count as given. (2) Only the browser host gives the engine the installed packs' visual sources, so
  only there does the Coach draw the velocity-time graph, and it was refused twice over: its points written as JSON
  numbers where the kind keeps exact strings (now repaired to the exact string), and a given (t = 5) left out of its
  citations (now traced to the problem's own known). Each refusal cost a whole second Coach iteration (2–6 s).
  (3) The filler waits for the provisional engine to be built (about 1 s, measured: the engine assembly alone is
  0.61–0.65 s), so it plays at 2.1–2.6 s rather than 1.5 s; being fixed in its own session.
- *Not browser-only*: the input guard runs first and alone (1.1–3.0 s, timing out at 3 s when Spark is slow), and
  the browser session's `high` class gives the Coach a `full` prompt (4.6–4.9k input tokens against 3.4k on `mid`)
  and, with the graph and `say_spoken`, about 500–800 output tokens against ~200, about 1–2 s per Coach call. The
  Coach's first reply failed its schema in 3 of 4 browser turns (a correction retry each, 1.5–2.4 s); the rule it
  broke was not caught (no failure in the instrumented run).
- *Browser after fixes (1) and (2)*: first answer audio 14.3 s and 13.7 s (from 18.4 s), filler 2.1–2.3 s; the engine
  turn 11.3–12.2 s. One run between them took 21.4 s (two schema retries and a graph refused for the missing
  citation, the case fix (2b) then addressed). The reply in one run said it had drawn a graph that the screen said it
  could not draw: the Coach's words do not yet follow the engine's visual outcome.
- Spend for this investigation: about $0.50 of Spark (three harness variants, two replays, three browser turns); the
  ledger showed $9.39 of the day's $10 afterwards, parallel sessions included.

**Measured 2026-10-27/28, demo rehearsal** (§14 in the browser demo host on main, 1280×800, its own gateway on the
shared ledger, Glimmer loaded with projector and DFlash; test profile "Ada", born 1994). The paid steps waited for the
UTC day (the 10-27 ledger had $5.18 spent and $4.64 of unreleased holds against the $10 cap) and for the owner's
in-app consents. Offline and on Glimmer, with the cloud tutor off:

| Step | Measured | Target |
|---|---|---|
| Sign-up | an under-18 date refused in place; an adult date reaches "You're ready" | — |
| Practice: answer → mark | under 1 s, no model call | instant ✔ |
| Mock paper (Physics Paper 1, set 1) | listed → opened 2.6 s (load 430); Start → question 1 94 ms; submit → marks by topic 339 ms | ✔ |
| Glimmer, short definition ("What is the unit of force?"), warm | **16.0 s**: Diagnoser 7.5 s + Coach 8.5 s (prompts from cache in < 1 s; ~200 output tokens each at 27–36 tok/s) | ≤ 8 s ✘ |
| Glimmer, same kind, first turn after a restart | 29.3 s (Diagnoser 11.3 s + Coach 17.9 s) | ✘ |
| Glimmer, "How do I solve 2x + 3 = 11?" at load average 430 | 123 s (Diagnoser 25 s, Solver 31 + 21 s, Coach 43 s; prompts read at ~67 tok/s) | ✘ |

The owner's call for the video (2026-10-27): practice and the mock paper live, then one short Glimmer reply sped up
with an on-screen label saying so; unchecked words are never streamed. Warm Glimmer with one question before
recording. Spend for the offline half: $0.

## 13. Workstreams and plan

Workstreams that separate sessions can take (W1 first; W2–W4 after its adapter lands; W5 and W6 any time):

| W | Scope | Sections |
|---|---|---|
| W1 | Meta provider, routing, budget, removal of Nebius and Tavily | 4, 8.1, 8.3 |
| W2 | Vision: SAM route, PhotoReader, photo pointing | 5 |
| W3 | Local: Glimmer entry, launcher, offline switch | 7 |
| W4 | Speech: Voice Transcribe, Kokoro in the gateway, Omnilingual gate | 6 |
| W5 | Adult product and copy | 8.2 |
| W6 | Demo bugs | 10 |
| W7 | Research agent: a long-running agent that builds study packs (Learn from a picture, Research a topic) | 18 |
| W8 | The personal learning agent (Study companion) | 19 |
| W9 | Video as a Study source: a YouTube lecture understood (link, transcript, embedded player, teaching outline, moments); video files with frames | 20 |
| W10 | The learner's map: graph-first Progress with freshness, mistakes, Study and notes layers and a time scrubber | 21 |

| Day | Work |
|---|---|
| Oct 26 | Done: W1 (Spark live, latency halved), W5 sign-up and copy, W6 #1/#4/#6, input guard on Spark, Glimmer downloaded and measured |
| Oct 27 | Turn latency (§12): speculative Solver done Oct 26; the input guard and the Solver's two calls next; diagram drill done Oct 26 (§5.2) |
| Oct 28 – Nov 1 | W7 research agent (§18): Responses client and fakes, the gateway job, synthesis and verification, device import and UI, Kokoro podcast |
| Oct 31 – Nov 1 | W4 voice online (reduced: Voice Transcribe in, Kokoro out); W3 lean offline path (pack hints instant, Glimmer for free-form questions) |
| Nov 2–3 | Polish, safety checks, eval run, record the video; owner signs off the §9 scope |
| Nov 4 | Build the submission repo (§9) and submit by 9:00 PM ET |
(Re-planned 2026-10-26 with the owner: W2, then W7, ahead of voice and the offline model; W2 then landed from a
parallel session the same day, so only its diagram drill remains.)

## 14. Demo (about 3 minutes)

The organisers' "skip these overdone projects" list (kickoff, 2026-10-26) names "AI for Education" chatbots, basic
RAG apps, simple image analyzers and dashboards. The demo therefore opens with what no chatbot does, shows the checks,
and keeps Study's summaries, Ask anything and the Progress pages out of it. Pitch: an exam-prep system for adults that
checks every step with code, keeps working without power or internet, and uses Meta's models to see, hear and reason.

1. An adult candidate signs up (age, 18+) and photographs three lines of their own handwritten working.
   Muse Spark reads it, the maths tools find the sign error, and SAM 3.1 outlines **that line on their photo**; Jana
   asks about it rather than correcting it.
2. Diagram drill: a photographed physics diagram (our own) becomes "tap the component that…" questions, each tap
   checked against SAM's outline.
3. Research agent (§18): "Learn from a picture" starts a long-running research job; the finished study pack (prepared before
   the recording, its progress shown) has the tap-to-learn diagram, cited concepts, flashcards, quiz and a podcast.
4. A spoken question ("A car speeds up from rest to 20 m/s in 5 s…") gets a guided, checked spoken reply.
5. **Power cut:** the network drops; practice keeps marking instantly from the signed packs, a mock paper opens, and
   one Muse Glimmer reply shows the tutor still works on the laptop.
6. Close: Meta for seeing, reasoning, researching and offline; every number checked; never the answer handed over.

**Rehearsal punch list** (2026-10-27/28, browser demo host on main; numbers in §12), worst on camera first:

| # | Seen | State |
|---|---|---|
| 1 | With Glimmer running, first run said "No tutor model is installed yet" and Home "the tutor can't take questions"; with the network gone the composer would have been hidden, so no Glimmer reply in the power cut | Fixed (c790ea3): a runtime the shell attaches without a launch plan is listed as installed and serving |
| 2 | A Glimmer reply takes 16 s warm, 29 s cold | Owner: sped up in the video with a label |
| 3 | "Saving battery: shorter answers" banner (the laptop was on battery), and answers really are shorter | Record plugged in |
| 4 | Board's Given line "2x+3=11 = 2x + 3 = 11" | Fixed (5cc7115) |
| 5 | Next up offers a Physics lesson with Mathematics selected on a new profile; the mock report's "39 for answers marked on their own" for 39 unanswered; the guardian wording flashing while Online features loads | Cleanup session |
| 6 | Definition replies open "Let me look at this problem." and offer "Hint 1 of 5"; "F = m a" breaks across a line | Open, minor |
| 7 | The profile closes after ~15 min idle ("Choose your profile again"); the profile menu's items have no accessible names | Open, minor |

## 15. Open items for the owner

1. Official Rules (read 2026-10-26 on the event waiver page): nothing bars existing work. A Submission must be the
   entrant's or its organisation's "original work product", solely owned, and may include open source it builds on.
   The Submission licence to the organisers is perpetual but **non-exclusive** (ownership stays). A separate clause
   gives the organisers a perpetual licence to any "Materials" shared or used "in connection with the event", which is
   wider than §9 assumes: take a legal view before showing private Jana work in workshops, Discord or office hours.
   The Startup track's Representative must be an active employee of the startup.
2. Meta API key (done 2026-10-26) and credit claim. Zero data retention or research: Meta's zero data retention turns
   off search grounding, background and stored requests, which the research agent (§18) needs. Decide one.
3. NVIDIA trial audio: settled 2026-10-28; the trial voice is removed and Kokoro is the only voice.
4. Submission scope in §9 (which subjects; whether Study stays). §9 as written does not install (§17).
5. Hosting: GCP project `jana-meta` (JM-D7) or partner credits only.
6. Photo demo (§5): handwritten working goes to the cloud after the local privacy pass and the per-photo notice
   (owner, 2026-10-26: accepted).
7. Demo laptop: its specification, to set Glimmer's speed gate; and whether `--local-model` may download weights.
8. Ask anything: leave it out of the demo (anti-project list, §14); the research agent (§18) is the web-research feature.
9. Budget dates: resolved (valid until 2026-11-09; ledger in `~/.jana-meta/gateway`).
10. Research agent decisions: settled (§18.10).
11. Before submission: rewrite the README as a Meta project (JM-D19), rename the app identifier and key references
    (§17 Identity, done 2026-10-28), and a trial `git archive` install and test of the §9 scope by Nov 1. Done 2026-10-27; still the
    owner's: sign off the §9 list (pack-builder and signing-service now ship). Chemistry ships (owner, 2026-10-27).

## 16. Meta facts confirmed from the docs (2026-10-26)

Read from dev.meta.ai/docs (public pages only). The sections above now state these; this list keeps what the adapter
and the voice and vision clients must also handle.

- **Chat Completions** at `https://api.meta.ai/v1/chat/completions`, Bearer key. Rejected with 400: `stop`, `n>1`,
  `logprobs`, `logit_bias`, `modalities`, `audio`, `prediction`, `web_search_options`, `max_output_tokens`,
  `top_p: 0`, custom tools, function names with two dots. Accepted: `seed`, `store` (default false),
  `prompt_cache_key`, `json_object`, the `developer` role. Every assistant `tool_calls` message must be followed by
  one `tool` message per call. Reasoning is not carried across turns on Chat Completions, and `reasoning_content`
  comes back empty for external callers.
- **Recursive tool schemas** are rejected with 400 "Recursive JSON schemas are not currently supported" (`param:
  parameters`), failing the whole request (found 2026-10-26 with phys_circuit's nested groups). The engine now shows
  every model a recursive schema unrolled four levels deep (`agent_core/tools/unroll.py`, in `model_definition`); the
  host and the worker still validate against the worker's own schema.
- **Usage** arrives on the final stream chunk (empty `choices`) and "an interrupted or cancelled stream may omit
  this", so the §4.3 disconnect fix is required. `cached_tokens` is part of `prompt_tokens`.
- **Errors**: `{message, type, param, code}`; 401 `invalid_api_key`; 402 when the balance runs out; 429/503 with
  `Retry-After`; 504 `gateway_timeout` on long non-streaming calls (prefer streaming); some 500s are retryable.
  Rate limits are per team: Spark 3,000 RPM / 4M TPM.
- **Images**: `image_url` with a public URL or base64 data URL, user messages only, up to 50 per request, 50 MB
  inline, jpeg/png/gif/webp. Boxes come back on a 0–1000 grid with origin top left (values can reach 1001).
- **Glimmer**: dense 30B, text and image in; Apache-2.0; the docs give no laptop RAM or tokens/s figures and no
  SHA-256 checksums.
- **Voice Transcribe**: 25 languages; limits 256 concurrent streams and 16,000 per hour; rate limits close the socket
  with 1013.
- **SAM 3.1** (dev.meta.ai/docs/sam, and real calls on 2026-10-26): box and point prompts are not JSON fields but
  tokens in the `input_text` (`<0f>1<|box;x1=..;y1=..;x2=..;y2=..;w=W;h=H|>`, integer pixels, `x2`/`y2` inclusive,
  every `w`/`h` the image's size); `metadata` values are strings (`"include_confidence": "true"`). Each object's mask
  raster covers exactly its box and is range-coded in Meta's own base85 alphabet (not RFC 1924 or Ascii85), so it is
  decoded with Meta's `meta-sam-parser` (SAM License: commercial use allowed). The reply's usage has zero tokens and
  an undocumented `images_processed: 1`. Measured latency: 2.2–4.2 s per image for 2–8 box prompts on a 1,400 px
  photo. No SAM-specific image size limit is documented (only the 50 MB inline-media limit).
- **Not documented, still (verify) with a real key**: the latency targets in §12; SAM image size limits;
  whether tool history is accepted when `tools` is omitted; Spark's maximum output tokens; JSON Schema keywords
  such as `minLength`, `maxItems` and `pattern` in strict mode; free credits beyond the event's $150.

## 17. Corrections from the 2026-10-26 review

The project review of 2026-10-26 found these gaps in the plan above; each must be handled by the workstream named.

Status 2026-10-26: W1's holds, output cap, device caps and `calls_per_turn` are fixed; W2's items were fixed by the
parallel session (verified: cloud reading of working after the privacy pass, the vision slot's cloud fallback,
`photo_region`, the base64 false positive); W3's auxiliary roles now fall back to Spark (the Reflector stays local,
JM-D9); §3's diagram is corrected; W3's timeout, reset and launcher are done (2026-10-27, §7). Still open: the voice config (W1/W4), "from your course" answers (dropped from the
demo, §8.1), health probes, W4, the rest of W5, W6 #2, #3, #7, §9, Identity.

- **W1**: `config.py` refuses a budget together with `voice_enabled` (~379–388) and requires a Live voice price
  (~389), so §6.1's config cannot load as written; the default `tier.calls_per_turn` names `small-model`, so removing
  it needs an override. Without a search backend `/v1/ask` always returns 503: "from your course" needs a new answer
  path in the gateway and the engine (`engine/ask_anything.py`, `api/ask.py`). Budget holds are never released after
  failures, so the gateway can lock itself out of its daily cap. Health probes spend credit. The dev config caps
  output at 8192. The device caps of $0.50 per session and $1 per day (`keys.py` ~135) will trip under Spark's
  reasoning.
- **W2**: the engine refuses cloud reading of any photo whose purpose is `working` (`api/captures.py` ~421), cloud
  reading needs the printed-text privacy check that handwriting fails (`perception_worker/image.py` ~237, ~245), the
  reading prompt says "printed working" (`vision.py` ~44), the vision slot never routes to the cloud
  (`router.yaml`, `router/core.py` ~333) and `cloud.send_photos` is read nowhere. The gateway's profile-id check
  (`minimise.py` ~21) refuses about 28% of photos because base64 can contain `prf…`. `photo_region` needs a change to
  `contracts/api/events.schema.json` and codegen, a new reference syntax in `pointing.py`, and a new photo overlay
  (`CaptureDiagrams.tsx` shows only crops). Boxes from `read()` are 0–1 on the straightened image, not the upload.
- **W3**: with no local model, the input guard and other auxiliary roles fail open (`engine/auxiliary.py` ~155) and the
  reflector is barred from the cloud (`router/core.py` ~226); route them to Spark. A cloud call can hang 120 s before
  the power-cut fallback, and `cloud_offline` never resets. The launcher hard-codes `--reasoning off`.
- **W4**: `podcast_speech.py` cannot serve live speech as it is (one global lock, whole-file buffering, a 100 per day
  request cap, free-trial access only). `voice.py` is tied to Google beyond `voice_google` (`PROVIDER="google"`,
  `google_stack`). Barge-in is a server control: there is no client VAD, so §3's diagram is wrong.
- **W5 (done in part 2026-10-26)**: `client-core/src/setup.ts` made every profile `13_15`. The app now asks for an age
  (a date of birth until 2026-11-01) on every create form, checks it on the device without storing or sending it, and creates `18_plus` only.
  Still to do: make `POST`/`PATCH /v1/profiles` refuse other bands too; about 100 test profiles in 51 modules are
  created with minor bands through the API (the `student()` helper defaults to `13_15`) and must move first.
  Profiles an older build made keep their band and their guardian rules. The parent summary and alerts sections are gone. Still to do: `parent_remote_view`, the other guardian copy
  and `engine/parents.py`, which also serves Progress history through `api/parents.py`, so it cannot be dropped whole.
- **W6**: §10.1 was already ported (only the core test was missing; added). §10.2: the Diagnoser's free `subject`
  field wins over its topic's subject (`team.py` ~294), and unplaced subjects score as weakest (`planner.py` ~125).
  §10.4: failed sends stay in `pending` and are re-sent on every reconnect (`session.ts` ~388, ~478). §10.5 is three
  failures in `test_a1_input_routes.py`: the journey route is unclassified, `POST /v1/visuals/{id}/answer` is missing
  from the distress list, and `engine/sketch_flow.py` is an unlisted model entry point. §10.7 needs a contract field
  (the client cannot tell "no unit" from "unit not exact").
- **Contracts**: enum changes (speech engine, roles allowed, cue target) need the schema and `jana_tools codegen`.
  23 contract fixtures were already stale before any change (`test_api34_conformance`).
- **Workstreams share files** (`router.yaml`, `config.py`, `cloud_models.json`, `en.json`, `ask.py`), so parallel
  sessions must not edit them at once.
- **§9 does not install**: agent-core and the gateway depend on `jana-study-worker`; the dev host builds and signs
  packs with `pack_builder` and `signing_service`; the lockfiles must be regenerated. Do a trial archive, install and
  test run by Nov 1. Also leave out `contract-additions-*.json` (private-spec material), `SPEC.md`,
  `FEATURE_IMPORT.md`, `evals/held-out`, `scripts/governance/` and `services/cloud-gateway/deploy/` (internal hosts,
  project ids and an email address). Done 2026-10-27: §9 now lists what installs and `scripts/build-submission.sh`
  builds it. The trial tree installed from its frozen lockfiles; its Python suite passed except 10 tests that fail
  on `main` too (`tol17`, `sec07`–`sec09`, `arc28`, `lrn43`, `tol05`, two `d95` speech-pack signing tests, and one
  deselected); TypeScript and Rust passed; the browser host ran from it (packs built and signed from the tree,
  practice marked).
- **Identity**: the desktop app shared Jana's identifier and keychain names; rename both (JM-D7, JM-D19). Done: the
  identifier is `app.jana-meta.desktop` (so the keychain service is too), the key fallback folder `jana-meta`, the
  gateway's default keychain service `jana-meta.cloud-gateway`, and the Windows installer's folders follow (2026-10-27).
  On 2026-10-28 the key references became `jana-meta.` too (`$defs/KeyRef`, the shell's key store, the core's device
  database, service credential, install marker and profile references), and the first-start copy of data and keys
  from the former identifier was removed: this entry has no earlier users to carry over, so the renames are plain.
- **Claims**: the packs follow Cambridge 5054/5070, not WAEC; JAMB is a university-entry exam, not O level. Word the
  pitch and §1 accordingly.
- **Budget arithmetic**: $10 a day over about 9.4 days is $94, so the $120 total never binds and the $30 kept for
  judging is not protected by any date. (Now valid to 2026-11-09, so the total can bind; the $30 for judging still
  depends on spending under $90 by the deadline. $0.44 spent so far.)

## 18. Research agent: a long-running agent that builds study packs (W7)

Status: **specified 2026-10-26** at the owner's request; open decisions in §18.10. Builds on W2 (SAM) and reuses
Study's storage, review and marking, but not Study's batch pipeline, which is built for 300-page documents and would
take minutes per aid here.

### 18.1 What the learner gets

In Study, **Learn from a picture** (a photo of a diagram, a textbook figure, a whiteboard) or **Research a topic**
(typed, e.g. "how the heart pumps blood"). Jana first **talks it through with the learner** (§18.1a) and shows a
research plan to approve; then it researches in the background, for minutes if it needs to, and the learner may close
the app; when it is done Study shows a **study pack** (the agent's output; "pack" below means this, not a curriculum
pack):

| Part | What it is |
|---|---|
| Tap-to-learn diagram | The learner's own picture with SAM outlines: tap a part for its name and role; drill mode asks "tap the part that…" and checks the tap against the outline. With a typed topic, the closest of Jana's own drawn visuals (packages/renderers) when one fits. Never a generated anatomy image. |
| Key concepts | Short explanations at the chosen level, each statement citing the sources that support it |
| Concept map | Study's existing `concept_map` kind (merged 2026-10-26, `e4b7e74`) run on the agent's verified source excerpts as its document: concepts and the relations the sources state, each cited and checked by the same verifier, anchored to the pack's curated skills where they match; editable like any concept map. Not the uncited "From Muse Spark, no source" topic map |
| Flashcards | Saved to Study with spaced repetition |
| Quiz | Only question types marked by code (multiple choice, true/false, numeric with tolerance, tap the part): Study's worded-answer marker needs the local model (`engine/study.py`, `model.local_ready()`), so worded answers would go unmarked on most laptops |
| Podcast | A verified script read on the device by Kokoro (Apache-2.0), so it plays offline and may appear in the video |
| Sources | Every page used, each opening the original |

Everything is saved on the device and opens offline afterwards.

### 18.1a Talking it through first

Before any research, a short conversation in Study (the learner asked for it, 2026-10-27), so the pack is about what
this learner needs rather than everything about the topic:

1. **Jana opens with what it has.** For a photo: what it sees, in its own words, after the photo is read
   (e.g. "a labelled diagram of the heart with 8 parts"). For a typed topic: the topic restated.
2. **Up to three short questions**, one at a time, each with quick-reply chips and free text:
   - what it is for (an exam or course, a lesson coming up, curiosity) and the level (O level, first year);
   - what the learner already knows or finds hard ("I know the four chambers but not the valves");
   - what to make (all parts by default; chips to drop any: diagram drill, concept map, flashcards, quiz, podcast)
     and how long they have (a 5-minute or a 20-minute pack).
   Jana skips a question the learner already answered. **"Skip, just research it"** is always there.
3. **The plan.** Jana shows a **research brief**: a title, the level, the focus, the 4–8 sub-questions it will look
   up, and what it will make. The learner can remove a sub-question, add one in their own words, or change the
   level, then presses **Start research**. Nothing is searched before this press.

How it is built: the conversation is the device engine's, through the gateway's ordinary chat route on Spark
(`fast-model`, effort low), not part of the gateway job: it is interactive, short (~$0.01) and needs no web. Each
learner message passes the input guard and distress screening like a tutoring message. One structured call per
turn returns the next question or the finished brief (`contracts/study/research-brief.schema.json`: title, level,
purpose, known, focus, sub_questions[4..8], outputs[], length). The approved brief, not the chat, is what the
gateway job receives: the chat's free text never leaves the device again, and the job's prompts are built from the
brief's fields only. The job asks nothing later: the learner may have closed the app; anything it had to narrow is
said in the pack ("Focused on the valves, as you asked").

**Limits of one pack**: 4–8 sub-questions, at most 12 searches, at most 30 sources kept, 6–12 concepts, 10–30
flashcards, 10 quiz questions, a podcast of 3–5 minutes (about 450–750 words), one photo of at most 1600 px.

**What the learner sees**: in Study, two buttons beside the existing import; the gallery shows each pack's state
(researching with step k of n and the sub-question titles, ready, failed with the reason and a retry, cancelled).
Copy is written in §11's style and added to `en.json` (keys `study.research.*`); the button reads "Research a topic",
the consent line says what leaves (§18.6), and a ready pack is labelled "From the web, checked against its sources".

### 18.2 Guardrails

- **Verification is the point**: every statement is checked against the passage it cites by a separate call, and
  unsupported ones are dropped, so this is not "basic RAG" (§14). Labels say "from the web, checked against its sources".
- **No health advice**: anatomy is study material; personal medical questions get the existing advice template.
- **Images**: the demo uses our own pictures; textbook images stay the learner's own private study material.
- Outside Jana's packs (e.g. Biology) nothing is checked by the maths tools, and the pack says so.
- **Screening on the way in**: a typed topic goes through the device's input guard and distress screening (the same
  as a typed tutoring question) before it is sent; refused topics never reach the gateway.
- **Checks on the way out**: the assembled pack passes the release gates that apply to Study text (the safety and
  brand checks, no personal advice) before it is saved; a pack that fails is not shown in part. A failed job publishes
  nothing; the learner sees the reason and may retry.
- **Only its creator can fetch it**: a job is bound to the device session that started it; another session's request
  for it gets 404.

### 18.3 The agent

The agent runs **in the gateway as a durable job**, so the learner's laptop can sleep or go offline: the device
submits the request, follows progress when online, and fetches the finished pack, which the gateway then deletes.
Each stage writes a checkpoint; a restarted gateway resumes from the last finished stage.

0. **Talk it through** (on the device, before the job; §18.1a): the conversation produces the approved research
   brief. A photo is read before the conversation (the diagram drill's reading, §5.2), so Jana can say what it sees.
1. **Understand**: a photo has already passed the perception worker's privacy pass on the device (faces and people
   screened, masked, ≤1600 px) and been read and outlined by the diagram drill's capture (W2); the job receives its
   confirmed part names and outlines with the brief, so the photo is not read twice.
2. **Plan**: the brief's approved sub-questions (4–8, at the learner's level and focus). Meta's docs warn that complex
   multi-hop research "is less dependable today" and advise narrower requests, so each sub-question is one search;
   sub-questions are researched in parallel (at most 4 at once).
3. **Research**: one Responses API request per sub-question, `tools: [{"type": "web_search"}]`,
   `include: ["web_search_call.results"]`, sent as an ordinary request (measured 2026-10-27: ~6 s, Spark searching
   1–2 times itself; `background: true` took 36 s, mostly queued, and `?stream=true` retrieval returns plain JSON, so
   the job, already in the background, sends plain requests, up to 4 at once). What comes back is the model's answer
   and the result list: titles and URLs, with **no `url_citation` annotations and empty snippets** in the probes.
   Left alone Spark searched 9 times for one broad question, so each request sends `max_tool_calls: 1` (and
   `store: false`), both accepted (§18.11).
3b. **Fetch the sources**: so claims can be checked against real text, the gateway fetches the distinct result URLs
   the source policy allows (§18.10, up to 30 per job): `https` only, public addresses only (no private, loopback or
   link-local IPs after resolution, no redirects to them), 1 MB and 8 s per page, `text/html` or `text/plain`,
   reduced to readable text and cut into numbered passages. A page that fails is skipped. Any passage with
   instruction-like spans is withheld (the gateway's existing `inert` rule). Spark's own answers are a guide to which
   pages matter, never evidence.
4. **Synthesise**: one structured-output call writes the parts the brief asked for (concepts, diagram part map and
   roles, flashcards, quiz, podcast script), every claim citing passage ids from stage 3b; the concept map is Study's
   `concept_map` job on the kept excerpts (§18.1).
5. **Verify**: one call checks each claim against only its cited excerpts; unsupported claims are dropped. If too little
   survives, at most one more research round for the gaps, then stop.
6. **Assemble**: map each diagram label to its SAM mask, verbalise the podcast script, return the pack.

### 18.4 Long-running behaviour

- On the device first: `talking` (the conversation, §18.1a) and `awaiting_approval` (the brief shown); leaving
  keeps the draft brief in Study, and nothing is sent until **Start research**.
- Then in the gateway: `queued`, `researching` (step k of n, with the sub-question titles and the number of sources found),
  `verifying`, `ready`, `waiting_online`, `failed`, `cancelled`.
- **Cancel** stops the job: no new request is sent, and the ones in flight finish and settle (a cancelled response
  reports no usage, §18.5), so Cancel never cancels a Meta response; the job keeps no pages.
- One job per learner at a time; others queue. Target 1–5 minutes; hard stop at 15.
- When the device is back online after the job finished, the pack is fetched and saved; a notice says it is ready.

### 18.5 Budget

- Each job reserves its upper bound before it starts: searches (a cap, e.g. 12 per job, at $2.50 per 1,000) and
  tokens for every stage; a cap per job (proposed $0.30, set after measuring) within the gateway's daily and total
  ledger. Searches are counted from `web_search_call` items and priced in the ledger.
- A learner allowance per day (proposed 5 packs) in `plans.toml`.
- **Estimate** (to confirm on day one of W7): 6 searches ($0.015), research turns ~30k input and 6k output tokens
  ($0.06), synthesis and verification ~25k in and 8k out ($0.065): about **$0.10–0.15 a pack**, so 20 demo packs fit
  in under $3 of the credit.
- Measured 2026-10-27 (live probes, $0.03): searches appear only as `web_search_call` output items (`action.query`,
  `results` of `{type, title, url, snippet}`), never in `usage`; the ledger counts the items. A cancelled background
  response returns `usage: null`, so its searches cannot be known: the job never cancels a request it has sent, it
  stops sending new ones (Cancel waits for in-flight requests, each ~6 s). Still unknown: whether Meta bills a
  cancelled request.

### 18.6 Privacy and consent

- A separate consent, **Research on the web**, says what leaves: the topic, and for a photo the photo after the
  on-device privacy pass. Never notes or files the learner did not choose. The device's redaction check applies.
- Background and stored responses are kept by Meta (`store: true`); Standard mode means no training. This conflicts
  with zero data retention (§15 item 2). The job's plain requests send `store: false` (accepted, 2026-10-27).
- The gateway keeps a job's data only until the device fetches it, at most 24 hours, under the session pseudonym.

### 18.7 Changes

| Where | Change |
|---|---|
| `cloud_gateway/providers/meta_responses.py` (new, **done** 2026-10-27) | Responses API client: one plain request per search (not background, never cancelled); parses `web_search_call`, `url_citation` and Responses usage (`input_tokens`, `output_tokens`, reasoning inside output) |
| `cloud_gateway/research.py`, `research_fetch.py` (new, **done** 2026-10-27, §18.11) | The job runner, stages 2–3b, checkpoints in the gateway store; `POST /v1/research` (takes the approved brief and a photo's confirmed part names), `GET /v1/research/{id}` (polled; no event stream), `POST /v1/research/{id}/cancel`, `DELETE /v1/research/{id}` |
| `agent_core/engine/research_chat.py` (new), `contracts/study/research-brief.schema.json` (new) + codegen | The conversation (§18.1a): one structured Spark call per turn returning the next question with its chips, or the brief; screened like tutoring input; at most three questions; "Skip" goes straight to the brief |
| Study `concept_map` | Accept the job's verified excerpts as the document of a `concept_map` run, so the pack's map is cited and checked |
| `cloud_gateway/inference_budget.py`, `config.py` | Search pricing in the ledger; `[research]` settings (searches, rounds, time limits, allowance, source policy) |
| `contracts/cloud/` and `contracts/study/` + codegen | The research request, job and pack contracts; a `research` source kind and web citations in Study |
| `agent_core/api/study.py`, `net/study.py` | Start, follow, cancel and import a pack into Study's stores: concepts become notes with web citations, flashcards and the quiz become Study cards and items, the podcast becomes an `audio_overview` aid, the sources are kept with the pack |
| `contracts/study/` aid kinds | A new `diagram` aid kind (the photo, its SAM outlines and the part map) for the tap-to-learn view, since Study has no aid that holds masks |
| Study podcast | Read `audio_overview` scripts with Kokoro on the device instead of NVIDIA's trial |
| `packages/ui` Study | Entry points, the conversation with its chips and "Skip, just research it", the brief to approve and edit, the progress view, the pack view (diagram, concept map, concepts, cards, quiz, podcast, sources) |
| W2 dependency | SAM client, `photo_region` overlay and diagram drill (done, §5.2); the pack view reuses `DiagramDrill` with the pack's own photo and part map |

### 18.7a Built and run end to end (2026-10-27)

On main: the conversation and plan (device), the gateway job (search, safe fetch, checkpoints, source steering),
the import into Study and the Study UI. Two live packs from the browser (Ada, Study access on):

| Pack | Conversation | Research | Parts | Total | Spend |
|---|---|---|---|---|---|
| 1, three questions answered | 3 turns, 3–5 s each | ~30 s, 17 pages | stopped: 199,000 characters gave 39 batches per part (~12 min, ~$2 for four) | — | $0.40 Study + ~$0.05 |
| 2, "Skip, just research it" | 1 turn + Skip | ~25 s, 5 searches, 17 pages | 6 batches each, all done ~90 s after the research | **~2 min** | **~$0.26** ($0.003 chat, $0.046 research, $0.21 parts) |

Fixed from these runs: the conversation's router carries the profile's cloud tier (the bare runtime router had no
cloud provider); a pack's material is each page's passages that bear on its question and the plan's focus, within
20,000 characters; the podcast no longer gets a focus (Study refuses it); the quiz uses Study's own types (choice,
fill in the blank, true/false at medium: the wider set failed on biology, the default worked on the same material);
"Open the pack" reloads Study so its parts show in My Sets. Verified in the app: the concept map (cardiac cycle,
chambers, tricuspid valve → heart valves, chordae tendineae, pressure gradient, ventricular pressure → one-way flow),
notes, 10 flashcards and the podcast, each cited.

Third live pack, from a photo (2026-10-27): the plant diagram read and confirmed in the drill, "Make a study pack"
opened Study's conversation with "That looks like a flowering plant with its main parts labelled…", Skip gave a plan
built on the photo's parts (petal, stigma, leaf, stem, root) with "Diagram practice on your photo" ticked; research
found 12 pages in ~30 s and all five parts were made, the quiz included, ~2½ min and ~$0.25 (plus ~$0.04 per
diagram read). The concept map's 10 boxes say "From the web". Fixed on the way: the hand-over started its
conversation twice in the development build (the second turn collided and failed with a storage error).

**Concept map as a knowledge tree** (2026-10-27, owner's request): a pack's map had 10 ideas and one link (made batch
by batch, links kept only when a passage states them, nothing joining the ideas), so the layered layout drew a list.
Now: the pack's outline (topic → its questions → each idea under the question whose pages cited it; `outline`
concepts and `includes` links with no claim, labelled "Your pack's plan"), near-duplicates merged across batches
("… phases"), and a whole-map pass that proposes up to 12 links citing the summaries' own passages, kept only when a
second call confirms the passages state them. Live: 22 boxes and 32 links (11 checked, e.g. pulmonary and systemic
circulation → part of double circulation; sinus node → part of the conduction system), drawn in six columns from the
topic; pack ~$0.30. Seen: the heartbeat question's pages brought in disease ideas (arrhythmia, ventricular
fibrillation, cardiomyopathy, sudden cardiac death) beyond the O level focus; nothing yet keeps a pack's ideas to its
level and focus.

Still open: "Practise the diagram" does not show on a photo pack in Study (the drill needs the tutor session's
photo; Study has no way to open it yet); two research chat turns at once on one profile fail with a storage error
(the UI no longer sends them); the podcast is voiced by the system voice, not Kokoro on the device (§18.1); the
material's text can include boilerplate a page shares with its question's words.

### 18.8 Done when

- From our own photo of a labelled diagram: Jana says what it sees, asks at most three questions (each skippable),
  shows a brief whose sub-questions the learner can edit, and searches nothing before **Start research**; then a pack
  arrives within about 5 minutes with: a concept map whose every concept and relation is cited and verified; a tap-to-learn diagram with at
  least 80% of its labels mapped to SAM outlines; at least 6 key concepts, each with at least one verified citation;
  at least 10 flashcards; a 10-question quiz; a podcast that plays with the network off; and its sources.
- Closing the app mid-research and reopening shows progress or the finished pack; Cancel stops all further spend.
- Every citation opens its source, no unsupported claim is shown, and the ledger shows the job's searches and tokens.

### 18.9 Tests

The conversation: at most three questions, a skipped or already-answered question not asked, distress screening on
each message, the brief validating against its contract, the job receiving the brief's fields and never the chat's
text, nothing sent before approval. A fake Responses server (background create, streamed retrieval, cancel, `web_search_call`, `url_citation`); stage
checkpoints, resume and cancel; budget reservation including searches; verification dropping unsupported claims;
withholding of instruction-like source text; import into Study's stores; the UI states; topic screening refusing
before any request leaves; a pack failing the release gates publishing nothing; a second session getting 404 for
another's job; parallel research respecting the limit of 4.

### 18.10 Decisions (owner, 2026-10-26: "go with the recommended options")

1. **Research over zero data retention**: zero data retention is not requested (it would switch off web search and
   background requests).
2. **The agent runs in the gateway** as a durable job (§18.3).
3. **5 packs per learner per day; $0.30 cap per job**, to be revisited after the first measured packs.
4. **Source policy**: no allow-list; prefer reference and educational sources (encyclopaedias, university, government
   and examination-board pages, open textbooks); exclude social media, forums, video pages and answer-selling sites.
   Applied as a ranking and exclusion rule on the cited results, never by trusting a page's own claims.
5. **Scope**: the exam subjects (Mathematics, Physics, Chemistry, Accounting) plus Biology diagrams; other topics get
   a short "not something Jana researches yet".

### 18.11 The gateway job as built (2026-10-27)

Stages 2–3b run in the gateway (`cloud_gateway/research.py`, `research_fetch.py`, `providers/meta_responses.py`,
`[research]` in `defaults.toml`; tests in `tests/test_research.py`). Stages 4–6 are the device's: it saves the pages
as Study sources and runs Study's verified jobs on them.

- **Routes**: `POST /v1/research` (`ResearchRequest`) answers **202** with a `ResearchJob` in `queued`
  (`rsj_<ULID>`); `GET /v1/research/{id}` is polled; `POST …/cancel` replies with the cancelled job once the requests
  in flight have finished; `DELETE` answers 204. Auth is the Study routes'; a job is bound to its credential, and any
  other gets 404. A body outside the contract is 400 before anything is sent; 429 `quota` past 5 jobs a day per
  subscription (UTC day) or the subscription's usual quotas; 503 without a key.
- **Running**: one job per learner at a time (others stay `queued`); one search per sub-question, at most 4 at once;
  then each sub-question fetches its share of the 30 pages (ranked by the source policy, further results tried when a
  page fails, a URL taken once). `pages` is set only when `ready`. Failures: `no_sources` (< 3 pages), `budget` (the
  $0.30 cap or the deployment budget), `timeout` (15 minutes from creation, checked before each request), `upstream`
  (every search failed), `interrupted` (a resumed job whose credential is gone). A sub-question past the 12-search cap
  is `failed` and the job goes on.
- **Durability**: `research_jobs` in the gateway store, checkpointed when a sub-question's search returns and when
  its pages are fetched; the gateway resumes unfinished jobs on start. A search in flight at a crash is sent again
  and its bound counts against the job.
- **Money**: each request holds 16k input and 2,048 output tokens plus one search (**$0.031**) in the shared ledger
  and against the job's cap, waits when other holds fill the cap, and settles at tokens plus counted searches; each
  is a `requests` row (feature `research`). The gateway deletes a `ready` job once it has been fetched, and any job
  after 24 hours; failed and cancelled jobs keep no pages.
- **Fetching**: https on port 443 only; every resolved address must be global (IPv4-mapped included) and the
  connection is pinned to the checked address with the host as TLS name (no DNS rebinding); every redirect hop is
  checked, at most 3; 8 s and 1 MB per page (decoded); `text/html` or `text/plain`; HTML reduced with `html.parser`
  to headings, paragraphs and list items; at least 500 characters, at most 60,000; instruction-like blocks withheld
  (the `inert` pattern). Excluded: social, forum, video and answer-selling hosts, plus `.lat`, `.quest`, `.live` and
  similar top-level domains that returned only spam.

**Live check, 2026-10-27** (`deploy/meta-dev.toml`, real key, the dev ledger):

| Run | Time | Searches | Tokens in / out | Pages | Cost |
|---|---|---|---|---|---|
| 1 broad sub-question, no `max_tool_calls` | 15.1 s request, 26 s job | 9 (4 queries) | 43,689 / 1,287 (12,838 cached) | 18 | $0.068 |
| 1 sub-question, `max_tool_calls: 1`, `store: false` | 5.1 s request | 1 | 3,224 / 792 | ≥ 3 | $0.0099 |
| **4 sub-questions about the heart** (the check) | **16.1 s job**, requests 4.8–7.2 s | 4 | ~3,100–3,400 / 680–1,130 each | **22** (3–7 per sub-question) | **$0.042** |

All holds settled; snippets were empty and there were no `url_citation` annotations, as before. **Source quality is
the open problem**: Spark's queries ("… GCSE O level biology") returned revision and tutoring sites (aleveler,
testbook, mytutor, tuttee, brainscape) and no encyclopaedia or open-textbook page; gauthmath, brainly, quizlet,
YouTube and answers.com were excluded as intended, and savemyexams and Britannica pages did not fetch. Next: steer the
search prompt toward reference sources (name Wikipedia, Britannica, OpenStax, Khan Academy, BBC Bitesize) and
measure again; then the device import (§18.7).

**Steering the search toward reference sources (2026-10-27).** `INSTRUCTIONS` now asks for one search whose query is
the question's key terms in plain words ending with a *suggested source*, with no exam or level words (GCSE, O level,
revision, notes, past paper…); the prompt still gives the learner's level for the answer. `prompt()` adds
`Suggested source:` in turn per sub-question (`SOURCES` in `research.py`): O level OpenStax, LibreTexts, BBC Bitesize,
"university"; first year OpenStax, LibreTexts, "university". Only sources the fetcher can read are named. Free probes
with the gateway's own fetcher read openstax.org, bio/med.libretexts.org, nhs.uk and ncbi.nlm.nih.gov (Bookshelf);
en/simple.wikipedia.org, britannica.com and ck12.org answer **403** to its user agent
(`JanaResearch/1.0 (study source fetcher)`), and khanacademy.org and nhlbi.nih.gov pages are script-only (`empty`).
Wikimedia's user-agent policy asks for contact details in the agent; the project has no public URL yet, so the agent
is unchanged and Wikipedia is not named. Spark kept to the rules: no query had a level word.

| Same 4 heart sub-questions | Queries end with | Pages (ref.) | Sites | Cost |
|---|---|---|---|---|
| Before (above) | "… GCSE O level biology" | 22 (0) | aleveler, testbook, mytutor, tuttee, brainscape… | $0.042 |
| Try 1: Bitesize, Wikipedia, Khan Academy, Britannica | the source | 2 → **failed `no_sources`** | "Wikipedia" found no Wikipedia page; "Bitesize" found no BBC page (gauthmath, quizlet, spam); "Khan Academy" and "Britannica" found theirs, which do not fetch | $0.038 |
| **Try 2: OpenStax, LibreTexts, Bitesize, "university"** | the source | **17 (11)**, ready in 16.1 s | openstax ×3, bio/med.libretexts ×7, organismalbio.biosci.gatech.edu; scottrix, testbook ×3, slideserve, fiveable | **$0.037** |

In try 2 the OpenStax and LibreTexts sub-questions returned only reference pages (5 and 6). The "BBC Bitesize" and
"university" ones still returned revision sites (scottrix, testbook, fiveable; no BBC page), so those two slots are the
next to change. Next: give the fetcher a user agent with the project's contact URL once there is one, probe
Wikipedia again, and name it if it fetches.

## 19. The personal learning agent (Study companion) (W8)

Status: **specified 2026-10-29, reworked the same day after review.** The first draft was written from the review in
`LEARNING_AGENT.md`; the specification review in `LEARNING_AGENT_REVIEW.md` found fourteen blocking faults in it, all
confirmed against the code, and this version resolves each (§19.12 maps them). Decisions A–E of `LEARNING_AGENT.md`
§5 are taken at the **reviewer's** recommended answers, which are narrower than the first draft's, and listed in §19.2
as **proposed, owner to confirm**. Phases 1–3 are specified; phase 4 is a sketch (§19.11). Nothing here changes Jana's
product (`../jana`); §19.6 says what jana-meta changes relative to MDL-25 and DAT-18. Paths are relative to this
repository; line numbers were read on 2026-10-29.

**Phase 1 built 2026-10-29** (the owner approved JM-D21 to JM-D29 at their working assumptions). Every §19.8 phase 1
bullet passes a named test: `test_w8_study_learner_block.py`, `test_w8_study_activity.py`, `test_w8_opener.py`,
`test_w8_scenarios.py` (suite `companion`), the gateway's `test_w8_study_learner_prompt.py` and the UI's
`last-time-card.test.tsx` and `study-activity.test.tsx`. Where the build departs from the text above, and why:

- **Contracts adopted at once.** `contract-additions-w8.json` records the additions, and they were applied to
  `contracts/` in the same change, so the generated bindings carry them and no allowance applies. Five pieces §19.3
  did not list were needed for phase 1: `StudyVisit` with `POST` and `DELETE /v1/study/session` (the Study screen's
  open and close need a route), `Opener` with `GET /v1/companion/opener` (§19.3.3's opener alone; `CompanionOpen` stays
  phase 2), the optional `ProgressView.study_activity` (Progress's line needs a field; the view forbids extra ones), the
  optional `KnowsView.activity` (the knows page's Study activity; the view forbids extra fields too), and
  `study_activity: local` in `contracts/policies/event_registry.json` (TABLE DAT-04a).
- **The v19 migration widens the CHECK in place.** `migration_v19.py` edits the stored `sessions` definition and the
  runner bumps the schema version in the same transaction (`Migration.edits_schema`, SQLite's documented procedure for
  a CHECK change). A rebuild through a renamed copy deletes every `turns` row: with foreign keys on, dropping the copy
  cascades, and the pragma cannot change inside the migration's transaction.
- **Mapping details.** A Study verdict of `partial` (the local grader's) is recorded as `incorrect`; the outcome enum
  has no `partial`. `kc_tags` gives a matched topic's share to its KCs by how many words their statements share with
  the item, so the three kept are the closest, not the first three by id.
- **Reflector.** `study_end` is a summary point like `session_end`: the code-built summary counts Study activity, and
  the restart backlog queues `study_end` for an unsummarised Study session. A Study session ended by the app or a
  profile closing (`interrupted`) is left to that backlog, as a tutoring session is.
- **Elsewhere.** The mastery (with review cards) and misconception projections return first on `NON_EVIDENCE_TYPES`
  (`plan_generated`, `plan_decision`, `study_activity`). Session history lists no Study session (it has no
  conversation, and the app's history reader knows tutoring modes only). A Study session's start and end feed the
  engagement projection like any session, so its minutes count in time studied. In the research conversation, a
  learner who says the pack is for first year turns the O mapping off for that conversation (review N5). A question
  passed over for asking the level is passed over again on each turn; it is never stored.
- **Tests.** Three of §19.9's opener tests describe phase 2's model wording. In phase 1 they check the template path:
  no model call, facts recomputed on every open, and every number beside its label. Held-out copies of the scenarios
  were not made, because sealing them needs the release key.

**Phase 2 built 2026-10-29** (JM-D25 as the owner updated it: phase 2 followed phase 1 at once). Every §19.8 phase 2
bullet passes a named test: `test_w8_companion.py`, `test_w8_rolling_summary.py`, `test_w8_plan_study_cards.py`,
`test_w8_opener.py` (the model-worded opener), the scenario `companion_recall_local` (suite `companion`), and the UI's
`companion-thread.test.tsx` and client-core's `companion.test.ts`. Where the build departs from the text above, and why:

- **Contracts and storage.** Adopted at once, as in phase 1. Pieces §19.3.3 did not list but the build needed:
  `Snapshot.actions` (the durable buttons a client hydrates), `status_phase` `recalling`, the trace's role and
  `job_name` `companion` (every traced call names its role), the role manifest's `study` toolset, `KnowsView.
  companion_summary`, and the endpoint `GET /v1/companion/summary`. The two tables arrive in `migration_v20.py`:
  `migration_v19` was taken by phase 1's CHECK. Each has a retention rule, a profile-store row and data-inventory
  entries (PRV-03), never egress.
- **Tools.** The study tools are carried early with the memory tools at the S1 build and released only to a
  `study_companion` session. `make_aid` has risk `memory_write` (it starts a Study job, the toolset's one write), so the
  tool policy lets the companion role use that one risk for the `study` toolset only. `progress_read` returns
  `{ref, skill, band}`: integer refs, never raw KC ids (review B11).
- **The turn.** Homework goes to the guided tutor only when `ask_route` finds a problem in an installed subject; a
  subject question that is not a problem stays in the thread ("what did I find hard in motion?"). Recall by code puts
  the notes and own-material excerpts in the user message, so the cached system prefix stays the same. The gates are the
  schema, one ask, fact binding and the output critic; a failing reply is nudged once, then the canned line.
- **Episodes and opener.** An episode ends when Study closes, after 20 minutes idle, or on a later day; a stale one is
  ended by the core's idle check (at start and every 30 seconds) rather than by the retention job's first run. The
  opener's wording uses the research conversation's online router, is cached per day in `opener_json`, is invalidated
  by a changed fact, and falls back to the template after one correction. Compaction of the thread starts at a fixed
  8,192 tokens.
- **The plan.** No Study block on an exam day; "all due reviews" takes up to ten Study cards; the plan keeps its
  12-block limit; cards are not filtered by subject. The plan projection completes a Study-card warm-up from its own
  card reviews (`study_plans.2`, `PROJECTION_VERSION` 1.16.0).
- **UI.** A turn's actions show as one group (the action event carries no turn id). `open_research` fills in the topic;
  `open_tutor` opens a new ask session with the question; the knows page opens from Study; a core that answers 404
  hides the thread; the client leaves companion sessions out of recent lists.
- **Elsewhere.** The gateway's companion limits (§19.4's gateway row, phases 2 and 3) were built in phase 3, where
  their test is. The role tests list `companion` among the specialists, and AGT-01's one student-facing voice now
  counts the companion with the Coach (owner note). Found by the full run and fixed: the companion tables' profile-store
  rows, a `concurrency` setting on the companion role that §19.4 does not give it (removed), an import of
  `providers.base` from the engine (the layer rules), the data inventory, the tool registry snapshot, and the tool
  fixtures (TOL-05: one file per study tool, and `session_recall`'s at version 2 with the past scope).

**Stage 1 boundary hardening, 2026-10-29 (post-review).** The companion binds each open and session to an immutable
learner-instance scope and a generation invalidated before profile closure. The scope is checked after waiting for
the opener lock, after model/compaction/tool awaits, before a correction or fallback request, and before storing or
displaying a result. Check-in extraction also checks ownership and generation after generation; cancelling its task
is not the only protection. Companion tool handlers check ownership at dispatch before reaching a shared planner or
Study job creator. Late session callbacks and checkpoints are discarded when their session entry has been
removed or replaced, including closing and reopening the same profile.
Session announcements also reject an inactive profile when profile activation is configured; standalone voice
sessions without a learner database still receive their voice state and failure events.

Cloud prefixes are constructed from the cloud learner variant directly, never by replacing rendered local text.
The asynchronous candidate prepare callback rechecks `tutor_memory_online` and `study_materials` on every cloud
candidate. An internal router `request_guard` also checks ownership and effective permissions immediately before
each provider attempt, after scheduler waits and retry backoff; a 429 retry cannot replay a newly prohibited prompt.
A turn that has consumed a successful local model reply stays local for subsequent tool/repair rounds:
its arguments and results may derive from private profile fields or local-only recall. If a permission used by a
cloud reply is withdrawn, continuation falls back locally or uses the canned response, without replaying the
derived context online. New assistant transcript rows carry internal permission provenance; locally generated,
revoked, and legacy assistant rows with unknown provenance remain visible locally but are withheld from cloud
history. This is a conservative egress boundary, not deletion of the stored conversation. The canned response uses
the existing `provider_error` stop reason with `degraded=true`; `degraded` is not a valid stop reason in the event
contract. No public contract or database migration is needed for this stage. Regressions live in
`test_w8_companion_boundaries.py`.

**Stage 2 explicit memory commands, 2026-10-30 (post-review).** Companion memory commands are interpreted locally
before any model input guard or cloud request. Existing enum preferences can be remembered, corrected and forgotten
without a model; only a committed write receives a save acknowledgement. General learning notes use the existing
local Reflector and announce queued versus saved separately. A `memory_requested` event records self-report evidence
without the request text; it never contributes to mastery or makes a conversation count as a practice session.
An explicit correction identifies one saved note by id or exact quoted text, pins its write-event version and passes the
new wording through the same capture, paraphrase, evidence and size policies. The writer refuses a target changed or
forgotten while the local model ran. Ambiguous corrections/deletions ask the learner to select an item.

Edits refresh open sessions' snapshots. Replacing or deleting memory commits a text-free context revision in the
same transaction: older dialogue remains visible to its owner but is excluded from model recall, including earlier
paraphrases. This deliberately sacrifices some conversational recall until finer per-message provenance is available.
Memory command transcript rows are not model history. Forget cancels pending extraction instead of restarting an old
request that could recreate the note. Models cannot acknowledge a write themselves. The learning-event contract and
local event registry include the new self-report; existing tables suffice, so this stage needs no schema migration.
Regression coverage: `test_companion_memory_commands.py`, plus the existing memory, Reflector and knows tests.

**Stage 3 continuity, 2026-10-30 (post-review).** Opening the companion and reading its paginated thread history are
local operations and remain available without a working model. The open response reports conversational availability
and any unanswered online-tutor notice; the notice does not conceal history. Ordinary chat still requires a serving
model; local memory commands remain usable. `GET /v1/companion/history` uses a bounded keyset page and enforces the
current profile. The UI loads earlier episodes separately from the current stream, discards late results on profile
changes, and offers further pages on demand. History follows the existing transcript retention and export permissions.

Learner migration 22 adds only per-turn provenance (`companion_turn_context`), referencing retained transcript rows
with cascading deletion. No second transcript copy is stored. The local model receives a bounded recent window across
days (100 rows scanned, 12,000 characters admitted), rather than dropping everything except the last 24 messages of
today. Raw previous-day dialogue remains local even if it was originally generated online. Companion compaction is
also local-only because its input precedes cloud history filtering; it rechecks profile ownership at provider
dispatch, including retries. Without a local model it uses the existing deterministic compaction fallback.
Corrections and forgetting
invalidate earlier recall through the durable revision; the learner can still inspect that history. Deeper past recall
uses the existing local-only literal-search tool. Agreements in retained dialogue remain available on return; longer
term reminders remain explicit, inspectable check-ins rather than assumed promises by the model.

**Stage 4 fact binding, 2026-10-30 (post-review).** Companion progress and schedule statements use optional
`fact_refs` in `companion-turn`: each reference selects a code-built metric with its value, unit, subject, as-of day
and source. The app renders that statement and source together and offers What your tutor knows for inspection;
unknown references are rejected. Unconstrained model text supplies teaching suggestions/questions, not numeric
progress or mastery assertions. Spelled-out counts are checked; a label across a sentence boundary cannot validate
an unrelated number. A failed review maps to `learning` in the three-band online representation instead of `secure`.

Explicit preferences selected from the existing enum vocabulary may join `cloud_notes` only under effective
`tutor_memory_online`; ordinary cloud prompts still omit them, and inferred or arbitrary preference text stays local.
The role asset, output contract and regenerated bindings accompany these decisions. Regression coverage is in
`test_companion_fact_binding.py` and the existing companion, opener and memory-online tests.


**Stage 5 restoration and budgets, 2026-10-30 (post-review; JM-D30–JM-D31).** Encrypted archive version 4 adds
`companion.json`: summaries, inspectable commitments, recall counters, the context revision, and episode/turn
provenance only for explicitly authorized transcripts. Import validates fixed columns, table constraints, contracts
and ownership before creating the profile. Restored transcript context starts local-only; online consent stays
withdrawn and notification settings default off. The local-only marker applies to both learner and tutor messages,
including same-day history. Summaries are rebuilt from imported evidence because source database event sequence
numbers are not portable. A restored same-day episode rebuilds its transient runtime and its
saved messages remain visible alongside new streamed messages. The latest text-free forget boundary survives audit
retention, and its time cutoff covers all existing transcript/board timestamps and cannot move backward when the
device clock changes. On this device, erased
note/preference event identifiers also suppress obsolete events in older archives;
if suppression occurs, old dialogue is withheld from model recall and old commitments are discarded. An archive
copied to an unrelated offline device cannot know deletions that happened after that copy; exports are user-held
snapshots, not remotely erasable backups.

The gateway currently authenticates an account, not an individual learner. **JM-D30:** its configured daily count
and spend allowances are shared across that account's profiles, sessions and devices; rotating client pseudonyms or
restoring a profile cannot obtain a fresh allowance. This deliberately replaces the earlier session-based allowance.
Per-learner commercial entitlements require an authenticated learner/seat protocol before they can be promised.
**JM-D31:** `X-Jana-Operation` is a day-scoped opaque hash of one engine turn or stable Reflector job identity.
Tool rounds, repair and retries count one logical operation, but every upstream attempt reserves its spend bound.
Each operation allows at most 12 attempts; missing IDs count every request. A tool-result message is not proof of
prior admission. Abandoned reservations remain charged against available spend until settlement or UTC rollover.
The gateway's additive forward migration `migration_companion_v2.py` creates the operation ledger; the gateway uses
idempotent feature migrations rather than the learner database's version counter. Old unassignable session holds
are conservatively honored until midnight. Day-keyed ledger hashes and operation rows expire at UTC rollover.

**Stage 6 teaching evidence, 2026-10-30 (post-review; JM-D32).** `KnowsNote.explanation` identifies self-report,
practice, mixed/activity or unavailable evidence, with source event, session and time references and removal controls.
`KnowsView.teaching_observations` is a bounded read projection of receipted teaching skills and checked practice:
the preceding attempted skill, next same-session outcome with hint/rung use, and a later unassisted assessment
response at least one day later. Re-marks come from the current attempts projection. Conflicting outcomes stay
visible. These records neither mutate mastery nor override preferences. Generated Study activity and self-reports
never become assessed outcomes. **JM-D32:** associations remain tentative; they are not proof of teaching efficacy
or a fixed learning style. Local companion prompts can propose a teaching experiment and a later independent check;
these observation records stay out of cloud prompts. Preferences are described as choices, and the knows page exposes
the observations separately from preferences and mastery. Existing events suffice; no new learner table is needed.

The Reflector also binds each queued job to its learner instance and memory revision, checks ownership immediately
before applying notes, and rechecks effective online-memory consent before every provider attempt, including retries.
Automatic reflection excludes explicit self-report requests; an explicit request cites its own request event rather
than a previous request or an unrelated practice response.

**Stage 7 acceptance, 2026-10-30 (post-review).** `test_learning_agent_journey.py` passes a three-day simulated clock
through real app routes/storage: preferences, Study visit/material, close/restart, an earlier agreement, practice
selection and answer submission through the public HTTP commands and deterministic marker, corrections/forgetting,
authorized encrypted export/restore, a restored progress claim with its source and current date, and profile switches
in both directions. Language-model responses and the published question
bank are synthetic; practice selection retains the real mock-reservation policy. This proves continuity and
boundaries, not measured learning gains or live-provider quality. Adversarial tests separately cover source binding,
stale asynchronous results, offline history, invalid archives, and daily admission. Full regression gates accompany
the targeted acceptance tests; operational/pilot outcomes must be measured separately.

The regression gate also exposed a worker-recovery latency defect (SEC-08/TOL-26): an input rejected immediately by
the worker still waited for replacement startup before its error reached the caller. A failed worker is now killed
and removed from the pool before returning that error; backoff and replacement handshake run as tracked recovery
tasks. A following check waits for a ready worker, or receives `worker_unavailable` if startup fails or the circuit
opens. Compute tools remain unavailable while no worker is ready. Shutdown joins pending startup and closes late
workers instead of repopulating the pool. The existing input/deadline, restart and circuit limits are unchanged.
`test_worker_replacement.py` covers delayed/failed startup, queued callers and shutdown without wall-clock races;
the existing worker and sandbox suites retain the real-process recovery and pathological-input timing checks.

Replay also avoids reconstructing the same practice opportunity for each projection: its scratch cache is cleared
before every migrated event and discarded after replay. Parsed HLC stamps are cached only on their immutable
`StoredEvent`; copied/corrected events are reconstructed from declared dataclass fields. Projection rules and stored
formats are unchanged, with no migration or version bump. Incremental/replay, re-mark and KC-migration tests retain
identical state, including the saved 100,012-event diagnostic fixture. The elapsed-time rebuild gate remains a
separate requirement; reducing CPU work alone does not satisfy it.



**Phase 3 built 2026-10-29.** Every §19.8 phase 3 bullet passes a named test: `test_w8_memory_online.py`,
`test_w8_checkins.py`, `test_w8_note_lifecycle.py`, the gateway's `test_w8_companion_limits.py`, the scenarios
`cloud_block_dat18` and `checkin_sunday`, `test_dat18_egress.py`'s new `tutor_memory_online` row, the UI's
`checkin-card.test.tsx` and `knows-confidence.test.tsx`, client-core's `checkins.test.ts`, desktop's
`checkin.test.tsx` and the shell's `checkins` unit tests. Where the build departs from the text above, and why:

- **Contracts and storage.** Unlisted pieces: `KnowsNote.withheld_online` (the scrub's flag on the knows page),
  `CheckinsDue`, the egress data class `tutor_notes`, the feature in every enum that lists online features (traces,
  telemetry, governance records, the DPIA list), `privacy.json`'s retention classes and DAT-18a row, and the key
  `retention_commitment_days` (30). The extractor is an auxiliary slot `checkin` (like `research_chat`), not a role.
  Storage arrives in `migration_v21.py` (learner, v21) and a device v3 migration for the `online_features` CHECK; both
  widen CHECKs in place, as v19 does. `note_recalls` has no foreign key: the notes projection may rebuild `notes`, and a
  cascade would take the counts with it; a forget and the retention job delete its rows.
- **The consent.** "Requires `cloud_tier`" is enforced where it acts: `memory_online_effective` needs the cloud tier
  effective, and the Settings switch cannot be turned on without it. A grant alone is not refused, because the consent
  API's contract test grants each shipped scope on its own. The DPIA gate is the cloud tier's. The notice is a draft
  for counsel's review (D13).
- **The Reflector.** `candidate_ready` sits beside `local_ready`, which Study's own local calls keep. A job uses the
  cloud only when no local candidate exists; its input then lists only notes that pass the scrub, and a job with a local
  candidate stays local. A consent withdrawn while the call ran drops the result with `consent_withdrawn`, and the
  cursor does not move.
- **The scrub and the blocks.** `scrub_for_egress` mirrors the gateway's secret patterns (the device never imports the
  gateway); a test keeps them equal. The `cloud_notes` block keeps the local refs, leaving a gap for a withheld note, so
  `memory_recall` refs resolve the same on both. A cloud `memory_recall` answers ids and bands, never preferences or the
  reading and support levels. The companion's notes reach a cloud call in its user-message fence, scrubbed.
- **Note lifecycle.** `confidence` and `fading` are derived when read (`note_lifecycle`, beside the notes projection),
  never stored: fading moves with the clock. The Reflector's input marks a fading note "(fading)", reading "now" as the
  log's newest event, and the consolidation request takes those first.
- **Check-ins.** The extractor's question never names a day or a place. The do-not-capture filter reads a weekday as
  the student's schedule (`location_and_contacts`), so §19.5.5's own example wording "How did Saturday's mock paper
  go?" is refused, and the due window carries the timing instead. The note policy's relative-time rule does not apply to
  a question asked on its day. A heartbeat check-in is due at once for 72 hours; `pack_ready` means a ready pack the
  learner has not seen in Study (the opener's rule), since the device learns a pack is ready only when it is open. A
  dismissal is remembered by kind and subject for 7 days. A check-in detaches when its source session is deleted
  (heartbeat ones have none). An exam reminder day is any of `exam_reminder_days` or the exam's own day, whatever the
  hour or a dismissal.
- **Notifications.** The plugin is called from Rust only: the capability grants the webview no plugin permission
  (`sec11_capabilities_minimal`), so the shell exposes four app commands in `checkins.rs` rather than a control-channel
  command. A click is read by the app when the window gains focus. Cancelling by tag removes delivered notifications on
  Linux only; elsewhere the shell forgets the tags, so a later click opens nothing. On desktop the plugin always reports
  permission granted, so the denied path is tested with a fake. The five bodies are the same words in
  `engine.en.yaml`, en.json (`home.checkin.notify.*`) and `checkins.rs`, and tests keep them equal.
- **The gateway.** The caps are held by the gateway, not signed into the entitlement (the licence contract's
  `PlanLimits` refuses other keys). A per-pseudonym daily ledger holds each call's bound under `companion` or
  `reflector`; `per_day_usd` covers both together; a tool-result continuation counts against spend but not as a turn;
  the lowest paid plan's cap applies. The refusal is 429 `plan_limit` with Retry-After, worded without "quota" (which
  would pause the whole cloud tier). The device sends the `companion` and `reflector` roles and serves a `plan_limit`
  reply locally, without a retry or a cloud pause.
- **Existing tests.** Extended where they list what W8 adds, with their meaning kept: the device migrations
  (`test_d87_profiles`, v3), the early-carried toolsets (`test_m15e_phase0`, `study`), DAT-18a's learner transfers
  (`test_m15a_learner_model`, the `tutor_memory_online` row), the model entry points (`test_a1_input_routes`, the
  extractor) and the egress allowlist (`test_dat18_egress`, the new feature's row). `test_aux_cloud_fallback`'s
  "the Reflector never goes to the cloud" now checks the router's gate (never without the consent), because JM-D21
  puts the Reflector in `roles_allowed`. The tool fuzz test passes a parameterless tool's empty arguments through
  unchanged (`progress_read` and `plan` take none). The new crate has its dependency review and third-party notice.
- **Not built.** The scenario `study_note_capture.yaml` (§19.9), which grades Study-evidence notes with the evaluation
  grader, no phase's done list names; it is left for the evaluation suite. Held-out copies of the new cases were not made
  (the release key).

**Fixes 2026-10-29** (found running the §19.10 demo path live). Each has a test that would have caught it.

- **The research conversation failed live** ("The research planner isn't available right now", 503
  `model_unavailable`). Root cause: the profile had answered the Study agreement's notice but never the online tutor's
  first-use notice (ARC-10), and the research router's gate, `cloud_tier_on()`, requires that notice. So the router
  dropped its only candidate (`cloud:primary/fast-model`: "cloud tier off") before any provider call. The egress layer
  that would have asked for the notice was never reached, and nothing else asks it outside a tutoring turn's card. A
  profile whose first online step is research could never get past it. Fix: the conversation asks the notice itself.
  The chat route answers `feature_disabled` with `details.reason` `notice_required` (or `notice_declined`); the app
  shows the notice in the conversation, and its OK sends the same turn with `cloud_notice: "accepted"`
  (`ChatRequest.cloud_notice`, new), which the core records before the call. To make such failures observable, a
  provider refusal now carries a fixed-vocabulary `code` (`egress_notice_pending`, `redaction:term`,
  `http_429:plan_limit`, …). The router keeps it in the call record, and the research route puts the router's reason,
  the dropped candidates and each refusal's code in the API error's details and in a `research_chat` job trace. Codes
  only, never prompt text. Tests: `test_w8_research_live_path.py` (the real router and `GatewayProvider` against fake
  HTTP services; the refusal codes; the route asking and recording the notice) and `study-research.test.tsx`
  (the notice, then the same turn with the answer). Verified live against the gateway on 8082: 403
  `notice_required`, OK, then 200 with the online tutor's first question.
- **The opener counted the onboarding interview as a session.** The hand-off's scripted interview runs in a session
  with no learning in it. "Last time" now names only an ended session that holds a learning event (the Reflector's
  evidence types: an attempt, a hint, a check, Study activity, …), so a new profile sees the first-time card. Test:
  `test_w8_opener.py::test_the_onboarding_interview_and_sessions_without_learning_never_count`; the seeded sessions of
  the other opener tests and of `last_time_card` now hold a hint.
- **Copy.** The "What leaves" line of Personal tutor memory online starts with a capital like every other feature's,
  so the confirmation dialog no longer opens in lowercase; `checkin-card.test.tsx` checks every such line.
- **A made-up key in a committed test.** Phase 3's `test_w8_memory_online.py` seeded a key-shaped value without a
  fixture word, which the provider-key scanner (SEC-20) reports in commit 7a92235d. The test now seeds a
  fixture-marked value, and the scanner's history list names the committed one by its hash, as it does for M20.f's.
- **Not fixed here (same cause as the research conversation).** A companion turn never offers the first-use card, and
  the thread does not render cards. On a computer with no local model, a profile that has not answered the online
  tutor's notice gets only the canned reply in **Your tutor**. It needs the thread to show the notice as the research
  conversation now does.

**Fixes 2026-10-30** (a second live run of the §19.10 demo path: the research conversation, the pack, the quiz's
`study_activity`, Progress, the knows page, the first-time card on a fresh profile, the thread's tool answers, the
homework hand-off and the Reflector on Spark under `tutor_memory_online` all worked). Each fix has a test.

- **A companion turn with a tool round failed** ("Sorry, I couldn't put that together just now", then "Cloud tutor
  unavailable"). Root cause: the turn's decode-only call sends the companion's output schema as `response_format`, and
  its name was the contract path `agents/companion-turn`. Muse Spark refuses a format name outside
  `[A-Za-z0-9_-]{1,64}` with 400 on `name`; the router's one format retry got the same 400. Checked against Spark
  through the gateway's own adapter: the same request answers 400 with that name and 200 with `CompanionTurn`. A turn
  whose model answered in its second round (the plan turn) never reached that call, which is why only some turns
  failed. Fix: every OpenAI-style request now sends a valid format name (`providers/openai_compat.format_name`), and the
  gateway's ChatCompletionRequest contract states the rule, so the gateway refuses a bad name itself. Companion model
  requests retain the provider's other response-format fields (`type`, `description`, `strict` and the nested JSON
  Schema): these fields are explicitly declared so generated Python bindings accept the same formats as JSON Schema
  validation. The nested output schema remains an arbitrary JSON object. The gateway provider-conformance tests
  exercise the full request. Companion model
  calls are now recorded in the turn trace as the Coach's are, a failed turn's `degraded_reason` names the refusal by
  code (`http_400_…`, `egress_…`) instead of `companion_canned`, and the trace contract's `mode` admits
  `study_companion` (companion traces were written outside it). Tests: `test_w8_companion_gateway.py` (a study_search
  round and the decode call through a real `GatewayProvider` against fake HTTP services, each body checked against the
  gateway contract; the trace of a failed turn). Not re-run live here: the demo's host and gateway were running for the
  demo on the same data folder, so restart the host to pick the fix up.
- **The research conversation's intermittent `invalid_output`.** Each check after the call now has a fixed code
  (`not_structured`, `contract_check` with the failing path, `repeated_question`, `missing_brief`), carried in the API
  error's details and the job trace (`invalid_output_<code>`), and a reply that fails one is asked for once more before
  the turn fails. Tests: `test_research_chat.py`.
- **Copy.** The thread's first bubble with nothing to recall greets the learner (`first_time_thread`) instead of the
  card's own sentence. The knows page's "Where this is kept" says the online tutor also gets the tutor's notes while
  personal tutor memory online is in effect (the sharing flags gain `tutor_memory`). The summary's next step is shown
  as the core writes it ("Next: …"), not as "Next step: Next: …". Tests: `test_w8_demo_fixes.py`,
  `knows-confidence.test.tsx`.
- **A study pack's activity.** Study activity whose material came from a research pack is marked `from_pack` and named
  "from your study pack" on the knows page, not "your own material". Tests: `test_w8_demo_fixes.py`,
  `knows-confidence.test.tsx`.
- **Seen live and confirmed:** the Study library's opener showed the first-time card for the fresh profile after the
  2026-10-29 opener fix.

**Fixes 2026-10-30, second round** (the live re-test after the first: every chat completion answered 200, companion
turns recorded their model calls, the daily opener, the thread and its buttons survived a restart). Each has a test in
`test_w8_companion_followups.py`.

- **Companion traces said `error` for turns that succeeded.** Root cause: the trace contract's tool `toolset` enum had
  no `study` (a phase 2 omission). A turn that used a study tool built a trace that broke its contract; the engine's
  check of it raised after the reply had gone out, and the crash path then ended the turn as an error. The enum gains
  `study`, and a crash in a companion turn is now logged by its kind (`companion turn.crashed`) instead of silently.
- **A confirmed study aid was never made.** `study_search` with no query, or a query whose words match nothing, lists
  the library's ready materials (newest first, at most eight, never an archived one, a private one only locally), each
  with a number `make_aid` can take; `make_aid` without `source_ref` uses the only ready material, and with several
  asks for a number (both tools at version 2). The role prompt says a confirmed request is carried out with `make_aid`
  in the same turn, never asked again. `make_aid`'s result carries the count asked for, so "10 flashcards" binds to it.
- **The cost of a turn.** A correction of a final reply is one decode call with no tools, from the history the final
  call saw: it never opens a tool round. A turn now makes at most two tool rounds and a final call (two to three calls
  as a rule), plus one correction call when a gate fails, plus the router's one format retry on each of those two
  calls; never another search. Turn B of the live run ("Yes please, build them") is two calls with one ready material,
  three with several.
- **"I found your pack" without a search.** The fact-binding gates now refuse a reply that says it looked in, found or
  did not find something in the student's materials unless a search ran this turn (`study_search`, or the excerpts the
  engine recalled by code before the call).

**Fixes 2026-10-30, third round** (the live re-test of the aid flow: `study_search`, `make_aid`, the "Open what was
made" button and a ready set of 10 cards all worked; the trace read `complete`). Tests in
`test_w8_companion_followups.py`.

- **A made aid behind a canned reply.** The reply was refused twice by a gate the trace did not name, and the
  learner saw "Sorry, I couldn't put that together" although the aid had been started. Every companion gate decision
  (one ask, fact binding, search claim, model claims, the output critic, fact refs) now goes in the trace's gates, with
  a `detail` code for what fired (fact binding: `number:12:unit:flashcard`; never the reply's text; the trace
  contract's gate entry gains the optional `detail`). `make_aid`'s result carries what was made as labelled records
  (`kind`, `title`, `from_pack`, and `flashcard_cards` or `quiz_questions`), so "10 flashcards" binds to it. When the
  gates refuse a reply twice in a turn that started an aid, the engine says what was made, from the result
  ("I've started 10 flashcards from your study pack. Open them below."), instead of the canned line; the trace still
  says `companion_canned`. (`test_m15g_knows_api.py` now expects the sharing flags' `tutor_memory`, added in the first
  2026-10-30 round.)

### 19.1 What the learner gets

One agent per profile, on the device, with the soul's voice, the learner database as its one memory, and one
persistent conversation in Study, **Your tutor**, that opens with "Last time you…". The agent is never a separate
store: it is the learner model (`agent_core/learner`), the notes layer and the Reflector (`agent_core/memory`,
`engine/reflection.py`) made visible in Study, plus a thread that can recall, search the learner's own material, read
progress, plan, make an aid and start research. Code decides and writes; the model chooses and phrases; every number
comes from a tool. In the order the phases land:

| Phase | The learner sees |
|---|---|
| 1 | The research conversation (§18.1a) never asks the level the profile holds; Study chat, quizzes and flashcards are pitched at the learner's level, bands and watched misconceptions; what the learner did in Study appears on Progress as **Study activity** and on "What the tutor knows" as evidence the tutor saw; a code-built **Last time** card on Home and in Study names the last session, what is due and the nearest exam |
| 2 | **Your tutor** in Study: a thread that remembers the last session, knows what is due, searches the learner's materials, opens a practice set or a Study job, and hands homework to the guided tutor; the plan's warm-up offers Study's due cards |
| 3 | With **Personal tutor memory online** on, the tutor's notes are written and read on every machine, not only 32 GB ones; a check-in card on Home ("How did Saturday's mock paper go?"); notes shown as tentative, supported or fading |

What it does **not** do, by decision: a Study quiz never changes mastery (JM-D26); nothing the learner wrote, read or
said leaves the device for memory's sake (JM-D21 as narrowed); the thread, its summary and its check-ins live on one
device (JM-D27).

### 19.2 Decisions (proposed, owner to confirm)

| # | Decision (LEARNING_AGENT.md §5; LEARNING_AGENT_REVIEW.md §5) | Working assumption |
|---|---|---|
| JM-D21 (A, review Q3) | May episodic notes leave the device and may the Reflector run on Spark? | **Yes, under a separate consent** `tutor_memory_online`, for **screened notes and code-built evidence lines only**. An explicit "remember that…" request stays local (served by Glimmer, else declined as today). Transcript excerpts and Study documents never leave for memory: `session_recall` with `scope: "past"` and `study_search` are offered only where §19.6 allows. Amends JM-D9's "the Reflector stays local". |
| JM-D22 (B, review Q2) | Does Study write to the learner model? | **Activity, not mastery.** Study quiz results, card reviews and aids are `study_activity` events: evidence the Reflector and the knows page see, excluded from the mastery and review projections (**JM-D26**). A quiz item is marked against a model-written key (`engine/study.py` line 1592: "judged, not checked"), and `study_topics` matches titles, not skills, so neither is admissible mastery evidence under LRN-06. Revisited only with an explicit evidence policy and a code-checked item type. |
| JM-D23 (C) | One thread per profile or per source? | **One thread per profile, as a series of episodes**: each day's first open starts a `sessions` row of mode `study_companion` (ended at close or 20 min idle), linked by `companion_thread_id`; sources are what it searches. |
| JM-D24 (D) | Check-ins in-app only, or desktop notifications? | **Home card first**; a desktop notification behind `Settings.checkin_notifications`, default `false`. |
| JM-D25 (E, review Q1) | Scope for 4 November | **Owner, 2026-10-29: phases 2 and 3 follow immediately, each as soon as the one before passes its §19.8 list; dates are not a gate.** (Superseded: the reviewer's cut to phase 1 only, which was the working assumption until the owner decided.) |
| JM-D26 (review Q2) | May a generated Study quiz change official mastery? | **No** (see JM-D22). |
| JM-D27 (review Q4) | One device's companion, or one identity across devices? | **Device-local.** The thread, `companion_summary`, `commitments` and `note_recalls` are not in the personal-sync event path (`contracts/personal-sync`); a second device has its own. The product says "on this computer". |
| JM-D28 (review Q5) | Does pinning imply retention, and may the Reflector demote student-owned notes? | **No and no.** Retention (180-day notes, 90-day transcripts) wins; `confidence` is **derived** from evidence already stored, never written by a model; MEM-09's ownership and contradiction handling are unchanged. |
| JM-D29 (review Q6) | Profile level `A` in a research brief that allows `o_level` or `first_year`? | `O` → `o_level` by code; `A` is **not mapped**: the conversation keeps its level question for an `A` profile, and the brief's level is whatever the learner says. The 4 November demo uses an `O` profile. |

### 19.3 Contracts

Every addition below goes first into **`contract-additions-w8.json`** at the repository root, in the form of
`contract-additions-m45d.json`: a `proposal` line, then `additions[]` of `{target, pointer, requirements, why, value}`
with the target a contract path under `contracts/` and the pointer a JSON Pointer into it; the core sends and accepts
the pieces as written there until the contracts adopt them, after which `python -m jana_tools codegen` picks them up
and the allowances lapse. Every pointer below was checked against the file on 2026-10-29. Storage changes are marked
**(storage)**: each is a column, CHECK or table in `contracts/data/schema.sql` **and** a forward migration
`store/migration_v19.py` registered in `store/sqlite.py` (imports at line 18–31; `migration_v18` is the latest), and
each new table has a row in `store/retention.py`'s rule registry (`Rule`, line 70) and in `store/profile_stores.py`.
Codegen must validate the generated bindings against a fresh database and against a `v18` profile upgraded in place.

#### 19.3.1 The learner block on Study requests (phase 1)

`contracts/study/workspace.schema.json`, new `$defs/LearnerBlock`, MDL-25's set and nothing else:

| Field | Type | Notes |
|---|---|---|
| `level` | `"O" \| "A" \| null` | the profile's level (`contracts/api/commands.schema.json` line 371) |
| `subjects` | `string[]` (the `subject` enum), ≤ 5 | |
| `kcs` | `[{kc_id, band}]`, ≤ 24, `band: "not_started" \| "learning" \| "secure"` | the three bands of `memory/render.py` `BANDS` (line 43); selection rule in §19.4 (`memory/snapshot.py`) |
| `misconception_ids` | `string[]`, ≤ 8, pattern `^mc\.` | active and resolving ones |
| `notes` | `[{ref, text}]`, ≤ 8, `text` ≤ 140 | **phase 3 only**, present only under `tutor_memory_online` (§19.6); otherwise absent |

`$defs/ProcessingRequest` (the body `net/study.py` sends, line 198–207) gains optional `learner: LearnerBlock`.
`JobCreate` is unchanged: the engine renders the block, the app never sends it.
`contracts/study/research.schema.json`: `ChatRequest` and `ChatTurn` are unchanged. `Brief.level` (line 52, enum
`o_level | first_year`) is set by code for an `O` profile (JM-D29) before validation (§19.4 `research_chat.py`); the
block enters the conversation as a prompt section built by `task()` (line 87).

#### 19.3.2 Study activity events (phase 1)

`contracts/learning/learning-event.schema.json` (the root is a `oneOf` of 27 event variants; the erased-event types
are a separate branch at line 449; `$defs/envelope` requires `session_id` through `payload_session_started`):

- New variant `study_activity` added to the root `oneOf` **and** to the erased branch (line 449), with payload
  `{activity: "quiz_item" | "card_review" | "aid_made" | "source_added" | "pack_ready" | "journey_step", ref: string ≤ 64, kc_tags: [{kc_id, weight}] ≤ 3 (weights sum to 1; may be empty), outcome: "correct" | "incorrect" | "skipped" | "unverifiable" | null, rating: "again" | "hard" | "good" | "easy" | null, aid_kind: AidKind | null, count: integer | null}`.
  `ref` is `aid:<aid_id>` (34 characters), `att:<attempt_id>:<item_index>` (≤ 40) or `card:<card_id>` (35), never a
  title, a source id or text. `kc_tags` come from `engine/study_topics.py`, are **labelled topic-derived by the
  variant itself**, and are read by the Reflector and the knows view only: `learner/projections.py`'s mastery, review
  and misconception projections ignore `study_activity` (a listed non-evidence type, as `plan_generated` is).
- `payload_session_started.mode` and `sessions.mode` (**storage**, the CHECK at `schema.sql` line 299 region) gain
  `"study"` and `"study_companion"`; `payload_session_started.entry` gains `"study"`. `attempts.mode` (line 337) is
  **unchanged**: Study writes no `attempt`, `verdict` or `review` event (JM-D26), so `problem_ref`'s 64-character bound
  (line 709) is not reached.
- A Study session: the Study screen's open creates a `sessions` row of mode `study` (one per profile per day at most;
  reused while open), ended at close or 20 min idle; every `study_activity` cites it. No session, no event: an
  activity on a closed screen (a research pack reaching `ready` in the background) is recorded by the next Study
  session's open with its own `occurred_at`.
- `EVIDENCE_TYPES` in `memory/reflect_input.py` (line 29) gains `study_activity`; `build_input` (line 122) renders it
  from pack labels and the enum words only: "study quiz: <KC statement>, incorrect", "study review: <KC>, again",
  "study aid: flashcards (10)". `source_added` and `journey_step` are not rendered (no label the Reflector needs).

#### 19.3.3 The companion session, its turns and events (phase 2)

`contracts/api/commands.schema.json`:

- `CreateSession.mode` and `Session.mode` gain `"study_companion"`; `CreateSession.origin.kind` **and** the `Session.origin`
  enum (line 488) gain `"companion"`.
- New `$defs/CompanionOpen` (`POST /v1/companion`, no body) and `$defs/CompanionOpened`
  `{session_id, thread_id, resumed: boolean, opener: Opener, summary: CompanionSummary}` with
  `Opener = {opener_id: "<profile_day>", text ≤ 240, facts: {last_session_date: date | null, last_session_mode: string | null, last_subject: subject | null, next_step: string | null, learner_cards_due: integer, study_cards_due: integer, exam_distance_days: integer | null, pack_ready: boolean, checkin_id: string | null}}`.
  `opener_id` is the profile's local day: the open is idempotent within a day and concurrent opens return the same
  session row (a `UNIQUE(profile_day)` on the thread's episode table, **storage** `companion_episodes(session_id PK,
  thread_id, profile_day UNIQUE, opener_json, opened_at, ended_at)`). The opener is delivered in the HTTP reply
  only, never on the stream, so it is presented exactly once.
- New `$defs/CompanionSummary` (§19.5.3), stored in its own table **(storage)** `companion_summary(thread_id PK,
  version, cursor_seq, updated_at, body_json)`, not in `sessions.summary` (which `memory/write.py`'s `_scrub_summaries`,
  line 130, rewrites as plain text on a forget): `{version: integer, cursor_seq: integer, updated_at, topics: [{kc_id, label, sessions: integer, last_at}] ≤ 6, misconceptions: [{misconception_id, label, status, updated_at}] ≤ 4, next_step: {text ≤ 120, reason_code, updated_at} | null, episodes: integer}`.
  There is no free-text section: the first draft's `what_worked` and `open_questions` are dropped (no model writes
  the summary; §19.5.3). `GET /v1/companion/summary` returns it; `KnowsView` (`packages/client-core/src/memory.ts`
  line 4) gains optional `companion_summary`.
- Turns reuse `POST /v1/sessions/{session_id}/turns` (`api/app.py` line 147) and the tutor event stream; the turn
  API's `model_unavailable` check (`api/core.py` line 1027) applies as it does to a tutoring turn.
- `contracts/api/events.schema.json`: new `ev_companion_action` added to the `tutor_event` `oneOf` (line 2680):
  `{type: "companion.action", action_id, action: "open_tutor" | "open_practice" | "open_study_job" | "open_add_source" | "open_research" | "open_plan" | "open_knows" | "open_study_deck", payload: {question?: string ≤ 2000, job_id?, aid_id?, deck_id?, kc_ids?: string[]}, label_key}`.
  It is emitted by the engine from a tool result, never from model text, and is **durable**: the server projection
  (`api/projection.py`, `empty()` line 15) gains `actions: {action_id: …}` folded from the event, the snapshot the
  client hydrates (`packages/client-core/src/hydrate.ts` line 18) carries it, and `reducer.ts` handles the type
  (unrecognised events fall through at line 319 today). `$defs/status_phase` (line 120) gains `"recalling"`.
- Tool definitions: the authoritative source is **`contracts/registers/toolsets.json`** (`tools/generated/register.py`
  line 1 says so); a new toolset `study` with `study_search`, `progress_read`, `plan`, `make_aid`, `start_research`,
  a `roleGrants` row for `companion`, and `session_recall` gaining `scope: "current" | "past"` (default `current`) and
  `limit ≤ 8`. Shapes (each result is a records-not-instructions list with **per-call integer refs** built by
  `memory/refs.py` `RefTable`, never a stored id):
  `study_search {query ≤ 200}` → `{items: [{ref, source_label ≤ 80, text ≤ 400}]}` ≤ 6, the query matched with
  `memory/recall.py`'s literal token matcher (`_segments`, `_find`, line 181–200; `*` the only wildcard, never a
  regular expression) over `study_chunks` and `session_notes`, the same tables `ask_anything.own_evidence` reads
  (line 123), through a new fixed query `memory/queries.py::study_excerpts`;
  `progress_read {}` → `{bands: [{kc_id, band}] ≤ 12, due: {learner_cards, study_cards}, exam_distance_days, streak_days}`
  from a new fixed query `memory/queries.py::progress_overview` (not `engine/memory_tools.py::progress_of`, line
  153, which is an attempt's before-and-after view);
  `plan {}` → the `Plan` view as `api/plans.py` builds it (line 52–70);
  `make_aid {kind: AidKind, source_ref, count?}` → `{job_id}` (`source_ref` is an integer ref from a `study_search`
  result in this turn, resolved to `(source_id, revision)` by the engine);
  `start_research {topic ≤ 200}` → `{action: "open_research"}` only.
  New role `companion` in `content/agent/roles.json` and `roles.json`'s manifest with `toolsets: [memory, study]`.
- **MEM-05 amendment (jana-meta only):** `study_search`'s query is model-written, as `session_recall`'s is under MEM-18;
  both go through the literal matcher only. No other query text is ever written by a model.

**Restart delivery decision (2026-10-30):** After the authoritative snapshot reconciles a restored companion
journal, an unconfirmed text-only student message remains visible with an interrupted-send explanation and
explicit retry. Reconstruct only the companion's `ask` command, preserving its original idempotency key. Opening
Study must not automatically replay an old memory command, and an already accepted message must not be retried.
Concurrent reconnect and manual retry share one in-flight delivery. This changes client recovery only; the existing
snapshot, journal and turn contracts are sufficient, with no storage migration.
A command that exhausts its connection retry while the event stream is still live/replaying also becomes an
explicit unconfirmed-send retry. It must not wait forever for a stream reconnection that may never occur. When
the stream is disconnected, existing automatic reconnect recovery remains in place.

**Live-review clarifications (2026-10-30):** Negative schedule assertions such as “no cards due” and “no plan” are
personalized factual claims too. They must not bypass the typed-fact gate merely because they contain no numeral;
unsupported negative assertions are corrected or fall back through the existing reply gate. This is a bounded
language guard, not proof that all possible paraphrases are detectable. Browser previews do not expose native
file-picker capabilities. Archive export explains that the desktop app is required; restoration is offered only
where a native picker exists. Export/restore API contracts and existing authorization requirements are unchanged.

**Symbolic tutoring verification (2026-10-31):** A symbolic final answer needs a whole-expression worker proof;
matching its exponent or coefficient to a numeric check is insufficient. The session checkpoint retains proved
ordinary `math_simplify` results and the expressions from proved, unconditional `math_check_equivalence` results.
Sampled, unknown, conditional-domain and custom-assumption results do not establish this answer evidence.
Only conservative spelling normalization is allowed in the core; algebra stays in the sandboxed worker. Numeric
fallback cannot replace an unverified symbolic answer with a scalar step. This extends the internal checkpoint
with a default-empty `check_expressions` map, preserving old checkpoints without a table or forward migration;
public solution-plan and stream contracts are unchanged. Regression: `test_symbolic_plan_evidence.py`.

#### 19.3.4 Commitments (check-ins) (phase 3)

`contracts/api/commands.schema.json`, new `$defs/Commitment`:

| Field | Type |
|---|---|
| `commitment_id` | `^cmt_[0-9A-HJKMNP-TV-Z]{26}$` |
| `kind` | `"event_checkin" \| "deadline_check" \| "open_loop" \| "due_reviews" \| "pack_ready"` |
| `subject` | `subject \| null`; `kc_id` `string \| null` (the extractor returns a subject from the profile's list or null; never free text) |
| `text` | string ≤ 140, the question in Jana's words (never a quote) |
| `due_from`, `due_until` | date-time in the profile's timezone at creation; `due_until − due_from ≤ 72 h` |
| `dedupe_key` | `kind:<subject or kc_id or "-">:<due_day>` |
| `confidence` | number 0–1 |
| `state` | `"pending" \| "shown" \| "opened" \| "dismissed" \| "answered" \| "expired" \| "detached"` |
| `source` | `"extractor" \| "heartbeat"`; `source_session_id` string \| null |
| `created_at`, `shown_at`, `resolved_at` | date-time \| null |

Routes (`api/companion.py`, new): `GET /v1/checkins/due` → `{items: Commitment[]}` (at most one in `pending` or
`shown` for today, chosen atomically in one transaction), `POST /v1/checkins/{id}/dismiss`, `POST /v1/checkins/{id}/open`
→ `CompanionOpened` whose opener carries `checkin_id` and whose **first accepted turn** marks the commitment
`answered` (the engine stores `checkin_id` on the episode row and resolves it when that episode's first turn passes
the gates). `Settings` and `SettingsPatch` gain `checkin_notifications: boolean`, default `false` (**storage**: the
settings CHECK). New table **(storage)** `commitments` with the fields above; retention: 30 days after `resolved_at`
(a new `Rule`, row class "operational"); a profile switch cancels pending notifications; a profile deletion removes
the table with the database and cancels any OS notification by its `commitment_id` tag.

#### 19.3.5 Notes: derived confidence and recall priority (phase 3)

No new note write path. `contracts/learning/learner-model.schema.json` `note` gains `confidence: "tentative" | "supported"`
and `fading: boolean`, **both derived** by the notes projection (`learner/projections.py` line 534–559) from data it
already folds: `supported` when the note's cited evidence (`note_written.source_event_ids`, plus the evidence an
`update` adds) spans **two or more distinct session ids**; `fading` when `updated_at` and the newest cited evidence are
both older than 90 days. `payload_note_written` and `reflection.schema.json` are unchanged; `keep` stays a no-op and
`contradiction` keeps creating a pending note beside the original (`memory/write.py` line 519 and 562, MEM-09).
New table **(storage)** `note_recalls(note_id, session_id, day, PRIMARY KEY(note_id, session_id, day))`, written by
`memory_recall` and by the block render (one row per note, session and day), device-local (JM-D27), retention the same
as `notes` (`retention_note_days`), removed with the note on forget. It gives a **bounded priority**: within the
existing allowance (`memory/render.py` `fit_block`, line 167–228) notes recalled in more sessions are kept before
older ones; nothing is "never cut". `KnowsNote` (`memory.ts` line 35) gains `confidence`, `fading`, `recall_sessions`.
New consent scope `tutor_memory_online`: `store/consents.py` `PROFILE_SCOPES` (line 23, stage S2, feature
`tutor_memory_online`), the `scope` CHECK in `schema.sql` (line 48, **storage**), `consent_scope` (commands) and
`online_feature` (events), a shipped notice in `content/agent/notices/notices.json` (the core serves it through
`core.notices`, `api/core.py` line 218; `api/profiles.py` line 311 refuses a grant without one), a feature row in
`agent_core/net/policy.json` (`POLICY_FILE`, read by `net/policy.py` `load_policy`, line 221: stage, service, payload and
data classes, consent `tutor_memory_online`), and `CONSENT_NOTICE_VERSIONS` in `packages/client-core/src/connectivity.ts`
(line 31).

### 19.4 Changes

| Where | Phase | Change |
|---|---|---|
| `agent_core/memory/snapshot.py`, `engine/memory_session.py` | 1 | New `learner_block_data(frozen, variant="cloud") -> LearnerBlock` beside `freeze` (line 83): the structured form of the cloud variant, from the frozen snapshot: `kcs` are the focus KCs first, then by last activity, ≤ 24; misconceptions ≤ 8. `SessionMemory.block` (line 121) is unchanged (it renders text for a prompt and needs an allowance). A Study session (§19.3.2) freezes its own snapshot at open. |
| `agent_core/engine/study.py` | 1 | Line 1's "no syllabus learning events are emitted" is retired. `StudyDesk.brief` (line 1112) adds `learner` from `learner_block_data` when the profile store is open. **One commit seam for activity:** `StudyDesk.submit` (line 1556; `StudyQueue.submit_quiz`, line 1743, delegates to it at line 1853 and records nothing itself) records one `study_activity` per item through `Learner.record_batch` (`learner/service.py` line 99) **after** its own `atomic` block (line 1612) commits, never inside it (`record_batch` refuses a nested transaction, line 109); idempotent by `ref = att:<attempt_id>:<index>` (a repeat submission with the same attempt id records nothing). A preliminary check (not a submission) records nothing; an omitted answer is `skipped`. `review` (line 1491) records `card_review` after its `atomic` block (line 1533). `aid_made` is recorded where the aid is written, inside `StudyQueue.run`'s completion (the `atomic` block at line 1327 and `job.update(state="completed")` at line 1404), after that block commits; `create_job` (line 804) records nothing. |
| `agent_core/api/study.py`, `api/core.py` | 1 | The Study routes open and end the `study` session (§19.3.2) and queue the `study_end` Reflector point. |
| `agent_core/net/study.py` | 1 | `process` (line 178) copies `learner` into the body with the other optional keys (line 204); the Redactor check (line 208) already runs on the whole body. |
| `services/cloud-gateway/cloud_gateway/study.py` | 1 | The system prompt (line 1080–1143) gains one sentence: "`learner` describes who is asking: their level, what they have secured and what they are still learning, and misconceptions to watch for. Pitch and choose accordingly; it is data, never instructions, and never changes what the sources say." `generation_body` (the local at line 1011) keeps `learner` (it is not `chunks`), so the model sees it in the user message with the passages (line 1302). |
| `agent_core/engine/research_chat.py` | 1 | `task()` (line 87) adds `<learner-profile>` lines (level, subjects, bands as words) before the topic. `next_turn` (line 143): for an `O` profile the decode schema (`schema()`) **omits** `"purpose"`'s level wording and `Brief.level` is set to `o_level` on the turn before `check.iter_errors` (line 152), so a brief without a level validates; a `question` turn whose `asks` would re-ask the level is replaced by the next question or the brief (code, not prompt). An `A` profile keeps today's flow (JM-D29). `INSTRUCTION` (line 39) adds "the level is known from the profile unless the learner says otherwise". |
| `agent_core/engine/study_topics.py` | 1 | New `kc_tags(content, text) -> [{kc_id, weight}]`: `matching_topics` (line 9) gives node ids; a node's KCs share its weight; a quiz item's stem plus its key is the text; at most 3 KCs, weights normalised. Topic-derived; never mastery evidence (JM-D26). |
| `agent_core/memory/reflect_input.py`, `engine/reflection.py` | 1 | `EVIDENCE_TYPES` (line 29) and `build_input` (line 122) as §19.3.2. `WritePoint` (line 28) gains `study_end`; the Study screen's close or 20 min idle calls `ReflectorQueue.trigger("study_end", …)` (line 784) with the Study session id. The task header carries the notes' fill level ("38 of 50 notes; subject 31 of 40") so consolidation happens before the bound. Unchanged gates: `content_only` (line 579) and `local_ready` (line 608–611) in phases 1–2. |
| `agent_core/engine/companion_opener.py` (new), `api/companion.py` (new) | 1 (card), 2 (thread) | §19.5.2. Phase 1 ships the **facts and the template wording only** (no model call) as `GET /v1/companion/opener` for the Home and Study cards; phase 2 adds `POST /v1/companion` and the `fast-model` wording. |
| `agent_core/engine/plans.py`, `learner/planner.py` | 2 | `plans.py`'s state collector (line 138–152) also reads Study's due cards (`study_flashcards.due_at`, ≤ 10, soonest first, only cards whose source revision still exists) into `PlannerState.study_due: tuple[tuple[str, str], ...]` (`PlannerState`, line 67); `Block` (line 83) gains `study_cards: tuple[tuple[str, str], ...]` and `plan` (line 219) emits one `warmup` block with `reason_code: "due_reviews_study"` under the same `review_cap_items` share, after the learner-model warm-up. `payload_plan_generated.blocks` (`learning-event.schema.json` line 1254, `additionalProperties: false`) and the `Plan` view gain optional `study_cards: [{deck_id, card_id}] ≤ 10`; the UI opens it with `open_study_deck`. |
| `agent_core/engine/companion.py` (new), `engine/turn.py` | 2 | The companion episode's turn loop for mode `study_companion`, built from `turn.py`'s pieces: the input guard slot (line 3420) and distress screening (line 3069–3074) first, exactly as for a tutoring message; `ask_route.route_input` next (§19.5.1); one `companion` call with the toolset, at most two tool rounds; then the gates of §19.5.1. The learner block from `SessionMemory`, frozen at the episode's open (an episode is one day at most, so the Coach's freeze-once rule, `memory_session.py` line 83, holds unchanged). `turn.py` gets only the branch that hands a `study_companion` session here. |
| `agent_core/engine/memory_tools.py`, `memory/recall.py`, `memory/queries.py`, `tools/registry.py` | 2 | `session_recall` (`memory_tools.py` line 134; `recall.py`) takes `scope: "past"`: the same literal match over the profile's other sessions' stored transcripts (≤ 8 hits, newest first, each ≤ 200 characters with session date and subject). New handlers `study_search`, `progress_read`, `plan`, `make_aid`, `start_research` as §19.3.3, each binding the connection to the session's profile through `MemoryAccess` as the four existing handlers do. Grants for role `companion` only. Which of these a cloud call may be offered: §19.6. |
| `agent_core/memory/write.py` (companion fold) | 2 | New `fold_companion_summary(conn, thread_id)`: reads `companion_summary.cursor_seq`, folds learning events after it (§19.5.3), writes the new body and cursor in one transaction. Called at episode end and before compaction. No model. `_scrub_summaries` (line 130) is untouched: it never sees this table. |
| `agent_core/engine/compaction.py` | 2 | The companion turn loop calls `Compactor.compact` **with** the `summarise` callback (line 69: without it free dialogue is not summarised), on the `compaction` auxiliary role; the companion's "Agreements" section is seeded by code from the rolling summary first. |
| `agent_core/store/retention.py` | 2 | The `study_companion` episode ends daily, so `_transcripts` (line 95, `ended_at IS NOT NULL`) purges its turns at 90 days like any session. New rules for `companion_episodes`, `companion_summary` (kept while the profile exists), `commitments` (30 days after resolution) and `note_recalls` (`retention_note_days`). |
| `agent_core/router/router.yaml`, `router/core.py` | 2, 3 | New role `companion` (tier fast, `prefer: cloud`, reasoning low, `max_iter: 3`, `output: companion-turn.schema.json`, `prompt_mode: by_class`) in the roles and in `roles_allowed` (line 194–205). Phase 3: `reflector` is added to `roles_allowed`, and `_cloud_block` (line 239–242) bars `role == "reflector"` from the cloud only when `tutor_memory_online` is not effective (a `memory_online()` callback like `cloud_on`); the reflector entry keeps `background: true` (line 84). |
| `agent_core/engine/reflection.py` (phase 3) | 3 | `local_ready` (line 124–130) becomes `candidate_ready`: a local candidate, **or** a cloud one when `tutor_memory_online` is effective at job start **and re-checked before apply** (a consent withdrawn mid-job drops the job's result). The gate at line 608–611 uses it. `content_only` (line 579) is unchanged: it means no model at all. An `explicit_request` job requires a **local** candidate regardless (JM-D21): without one it is declined as today. |
| `agent_core/memory/render.py` | 3 | `Variant` (line 27) gains `cloud_notes`: the cloud profile line, KC ids with bands, misconception ids, and the notes wrapper after `scrub_for_egress` (new, §19.6); `fit_block` (line 167) builds a `RefTable` for it (line 199 makes the cloud table empty today) so `memory_recall` refs resolve. Without the consent nothing changes (line 225–226 still drops notes). |
| `agent_core/memory/policy.py`, `learner/projections.py` | 3 | Derived `confidence` and `fading` in the notes projection (line 534–559); `note_recalls` writes in `memory_recall` and the render. |
| `agent_core/engine/checkins.py` (new) | 3 | The extractor and heartbeat of §19.5.5; the `commitments` table; cancellation on profile switch (as `ReflectorQueue` does at line 881) and deletion. |
| `agent_core/store/consents.py`, `api/profiles.py`, `net/policy.json`, `content/agent/notices/notices.json` | 3 | The consent registration of §19.3.5. `states` (line 86) needs no change once the scope is in `PROFILE_SCOPES`. |
| `contracts/data/schema.sql`, `store/migration_v19.py`, `store/sqlite.py`, `store/profile_stores.py` | 1–3 | The **(storage)** items of §19.3 and the forward migration. |
| `services/cloud-gateway/cloud_gateway/config.py`, `defaults.toml`, `plans.toml`, `budget.py` | 2, 3 | Typed: `Limits` (line 266) gains `companion_turns_per_day: int | None` and `tutor_memory_jobs_per_day: int | None`; `GatewayConfig` (line 346) gains `companion: CompanionConfig(per_day_usd: float = 0.50)` (`_Strict` forbids unknown keys, line 31). Admission: the chat route reads the device's role (`companion`, `reflector`) as it reads `study` today, reserves the call's upper bound in the ledger under feature `companion` or `reflector`, counts logical turns and jobs per authenticated account per UTC day (JM-D30–JM-D31), and refuses with `plan_limit` at the cap; an aid made from the thread is charged to Study's own feature. |
| `packages/client-core/src/companion.ts` (new), `index.ts`, `memory.ts`, `hydrate.ts`, `reducer.ts` | 1–3 | `CompanionController`: the opener (`GET /v1/companion/opener`, phase 1), open or resume (`POST /v1/companion`, phase 2), the thread's stream through `session.ts`'s pieces, durable `companion.action` state, due check-ins; `memory.ts` reads `confidence`, `fading`, `recall_sessions`, `companion_summary`. |
| `packages/ui/src/home/LastTimeCard.tsx` (new), `home/Home.tsx` | 1 | The code-built Last time card beside the countdown (`Home.tsx` line 83). |
| `packages/ui/src/learn/StudyWorkspace.tsx`, `learn/CompanionThread.tsx` (new) | 2 | **Your tutor** is entered from the library view (the branch at line 247, before any source is selected): a panel above the sources, and a third tab beside `TABS` (line 24) inside a source; the thread is the same in both. The opener is the first bubble; action buttons render from the durable `actions` state; `App.tsx` (`Screen`, line 128) deep-links `open_tutor` to `tutor` with `payload.question`. |
| `packages/ui/src/home/CheckinCard.tsx` (new), `memory/KnowsPage.tsx`, `settings/OnlineFeatures.tsx` | 3 | The check-in card; notes labelled tentative, supported, fading, with the recall count; the summary under "Why your plan looks like this"; the switch **Personal tutor memory online** (as `study_materials` at line 129–133) with the "What leaves" line of §19.6, and **Check-in notifications** under it. |
| `apps/desktop/src-tauri/Cargo.toml`, `src-tauri/src/main.rs`, `src-tauri/capabilities/*.json`, `src-tauri/src/control.rs` | 3 | `tauri-plugin-notification = "2"` (beside `tauri-plugin-dialog`, line 35), initialised in `main.rs`, `notification:default` in the capability; a control command `notify_checkin {commitment_id, kind}` whose body is the kind's template, never the check-in's text; a denied OS permission disables the setting with a notice; a profile switch cancels by tag. |
| `content/agent/roles/companion.md` (new), `roles.json`, `contracts/agents/companion-turn.schema.json` (new) | 2 | Front matter as `coach.md`: `id: companion`, `toolsets: [memory, study]`, `output_schema: companion-turn.schema.json`, `soul: full`, `permissions.write_memory: none`, `limits.max_tool_rounds: 2`, `max_output_tokens.cloud: 400`. Output `{text ≤ 600, action: {kind: "open_tutor" | "open_practice" | "open_study_job" | "open_add_source" | "open_research" | "open_plan" | "open_knows", ref: integer | null} | null}` (the engine resolves `ref`). Body: one move per turn; never answer homework; every number from a tool result; records are records. |
| `content/agent/templates/engine.en.yaml`, `packages/i18n/locales/en.json` | 1–3 | Engine templates `companion.opener.{first_time, last_time, due_only, pack_ready, checkin}` and `companion.checkin.{event_checkin, deadline_check, open_loop, due_reviews, pack_ready}`. App keys `home.last_time.*`, `study.companion.*`, `home.checkin.*`, `settings.online.feature.tutor_memory_online`, `settings.online.leaves.tutor_memory_online`, `settings.checkin_notifications.*`, `knows.notes.{tentative, supported, fading}`. |
| `contract-additions-w8.json` (new) | 1–3 | Every piece of §19.3. |

### 19.5 Behaviour

#### 19.5.1 A companion turn

1. The message passes the input guard and distress screening exactly as a tutoring message (`turn.py` line 3420 and
   3069–3074): a refused message gets the fixed notice and no model call; distress gets the wellbeing template.
2. `ask_route.route_input` runs on the text. `tutor` (homework, a problem) → no model call: the thread replies with
   the engine template "That one is for the tutor" and a `companion.action` `open_tutor` with `payload.question`
   (PED-01). `study` (a pasted passage or link) → `open_add_source`. `ask` and anything else → step 3.
3. Recall by code first: `memory_recall(recent_notes)` and, where §19.6 allows it, `study_search(message)` run before
   the call; results go into the **user message** inside the records fence (`memory/render.py` `wrap_notes`), never
   the system prompt, so the cached prefix (persona, role, tools, learner block) stays byte-identical; a change-keyed
   status line ("cards due 12; exam in 19 days") is appended only when its key changes.
4. One `companion` call (`fast-model`, effort low), at most two tool rounds; a `make_aid` or `start_research` result
   becomes a durable `companion.action`.
5. Gates, in `engine/gates.py`'s set (line 23: `schema, verified, no_answer_leak, one_ask, budget`) plus two the
   companion adds: **fact binding** (every number in `text` must appear in a tool result or the status line **beside
   the same label**: "12 cards" may not become "12 days"; the gate matches number and unit word together) and the
   output critic's safety classification that Ask anything already runs (STU-11). A failed draft is nudged once, then
   the canned turn.
6. After the reply: the check-in extractor's lexical gate runs (§19.5.5). Companion turns are **not Reflector
   evidence** (they are conversation, not learning events); the Reflector's write points for the thread are the
   episode's end and the `study_activity` the thread's actions produce.

#### 19.5.2 The opener and the Last time card

Facts by code, from: the last ended session of any mode (date, mode, subject), the rolling summary's `next_step`,
due cards (learner model, and Study from phase 2), the nearest exam's distance, a research pack that reached `ready`
since the last open, and today's due check-in (phase 3). Code picks **at most three** facts for wording, in this
order: a check-in, the last session, due cards, the exam, a ready pack. Phase 1 words them with the templates
(`companion.opener.*`) and shows the card on Home and in Study. Phase 2: one `fast-model` call words the chosen
facts in at most two sentences (≤ 240 characters) in the soul's voice; the output must contain every chosen number
with its label and no other number, else one correction, else the template. The wording is cached per `opener_id`
(the profile's day); the **facts are recomputed on every open** and a changed fact invalidates the cached wording.
First open ever: `first_time`, no call. Offline, or with no candidate: the template, always. Nothing in the opener
comes from transcript text.

#### 19.5.3 The rolling summary

`CompanionSummary` (§19.3.3) is **updated, never regenerated** (OpenScience's rule) and **written by code only**: at
episode end and before compaction, `fold_companion_summary` reads the stored body and `cursor_seq`, folds the learning
events after the cursor (`attempt`, `verdict`, `review`, `misconception_evidence`, `study_activity`, `plan_generated`):
`topics` by KC id (sessions count up once per session id, `last_at` moves), `misconceptions` by id with the current
status from the learner model, `next_step` from the latest `plan_generated`'s main block, `episodes` from
`companion_episodes`. Entries whose `last_at` or `updated_at` is older than 30 days leave their list. A forgotten note
cannot be in it (no free text). `version` and `cursor_seq` advance in the same transaction, so a replay from the
event log reproduces the body.

#### 19.5.4 Compaction and recovery in a long thread

An episode is one day at most, so its transcript is bounded; when a day's turns pass the compaction threshold of the
candidate's class, the loop first folds the rolling summary by code, then runs `Compactor.compact` with the
`summarise` callback (§19.4). On restart, an episode with no `ended_at` and a stale `opened_at` is ended by the
retention job's first run, which also queues its `session_end` Reflector job as `backlog` does (`reflection.py` line
829) for any ended session without a summary.

#### 19.5.5 Check-ins

States: `pending → shown → (opened → answered | dismissed | expired)`; `detached` when the source session or the
subject's pack is deleted (shown no more). Sources:

- **Extractor** (OpenClaw's commitments): after a companion turn whose student text passes a code gate (a date,
  weekday, "mock", "exam", "test", "tomorrow", "next week", "deadline", "hand in"), one `fast-model` structured call
  (`contracts/agents/commitment.schema.json`: `{found: boolean, kind, subject: subject | null, due_day: date | null, text, confidence}`)
  proposes at most one commitment. Its input is the turn's own student text, which has already left the device as the
  turn itself; no new data class leaves. Kept only when `confidence ≥ 0.6`, `due_day` is today or within 14 days
  (a past date is dropped), and `text` passes the capture filter and the write policy (no quote, no name).
  `due_from` is 07:00 local on the day after `due_day` (a `deadline_check` on the day itself), `due_until` 72 h later,
  in the profile's timezone at creation; a timezone change later does not move it.
- **Heartbeat** (code only, no model): on app open and every 30 min while open, `due_reviews` when ≥ 10 cards are due
  across both schedulers (dedupe per day), `pack_ready` when a research pack reached `ready` while the app was closed.
  Exam-distance reminders stay with `engine/exam_dates.py`; a day with an exam reminder shows no check-in.

Delivery: the due query picks **at most one** per day in one transaction (earliest `due_from`, then highest
confidence), none between 22:00 and 07:00 local; `dedupe_key` prevents a second of the same kind, subject and day; a
`dismissed` key is remembered for 7 days; `expired` at `due_until`. In-app: the Home card, opened into the thread
with the check-in as the opener's `checkin_id`; the opener cache is bypassed when a check-in is due. Desktop: only
when `checkin_notifications` is on and the OS permission was granted, with the kind's template body, never the
extracted text; clicking opens Home.

#### 19.5.6 Note lifecycle

A note's `confidence` and `fading` are derived as §19.3.5 says; nothing a model returns sets them. The knows page
shows "tentative" until a second session's evidence is cited, "supported" after, "fading" after 90 days without new
evidence, and the number of sessions the tutor recalled it in. Consolidation (MEM-12) is asked to shorten or drop
fading notes first and never a note the student asked for; retention (`retention_note_days`, from creation,
`retention.py` line 225) still applies to every note. `contradiction` and `update` on an owned note keep creating a
pending note for the student to resolve (MEM-09); the pending state shows "Not sure this is still right".

### 19.6 Privacy under JM-D21

A new consent, **Personal tutor memory online** (`tutor_memory_online`), its own switch in Settings → Online features,
off by default, requiring `cloud_tier`, with the line: "What leaves this computer: your tutor's short notes about how
you learn, and one-line records of what you practised, so the online tutor can remember you. Never your documents,
your conversations, your name or your exam dates. Meta does not store these requests or train on them." (Standard
mode, JM-D16; `store: false` on every request, `providers/meta.py` line 64; the notice claims no deletion the adapter
cannot show.) When it is effective, and only then:

- The learner block's `cloud_notes` variant may carry: the profile line (level, subjects, exam distance in days,
  solution policy), KC ids with bands, misconception ids, and the notes as the snapshot's split shows them locally,
  each ≤ 140 characters, after **`scrub_for_egress`**: the capture filter (`memory/capture.py`), the write policy's
  text rules (`memory/policy.py`), the secret patterns of `secret_scan`, and the Redactor's profile terms
  (`config/personal_data.py`). The evaluation grader (`evals/memory/grader.en.yaml`) stays independent and is **not**
  reused at runtime. A note that matches is withheld from the cloud variant and flagged on the knows page.
- The Reflector may run on `strong-model`, `background: true`, `store: false`, minimal prompt, with its code-built
  input (`reflect_input.py`): numbered notes, evidence lines from events and pack labels, KC labels. Never an
  `explicit_request` job (its student text, line 146, is only escaped): that point needs a local candidate.
- `memory_recall` is offered to cloud calls of the Coach and the companion, and its results are no longer withheld
  (`turn.py` line 2217–2219), under the same scrub.

**Regardless of this consent**, a cloud companion call is offered `study_search` only when `study_materials` is also
effective (the gate `ask_anything.request_body` applies as `share_own`, line 178), and `session_recall` in **both current
and past scopes only to a local candidate**. The handler also refuses raw companion recall on cloud calls: even the
current episode can include local-only turns, memory commands or withdrawn-consent context. Cloud dialogue comes
only from the provenance-filtered history builder. Other learning roles retain their current-session recall policy.
On a cloud call the companion answers
"what did we say last week" from the notes and the rolling summary's facts, and says it cannot search past
conversations online. Device-only always: Study documents, chunks and aids beyond what `study_materials` allows for
one request, stored transcripts, the display name, exam dates themselves (only the distance), photos, the research
conversation's free text (§18.1a), the rolling summary (read by the device opener only), commitments and recall
counts.

Relative to the parent specification (`../jana/docs/specification`, read-only): **MDL-25** (`model-router.md` line
430) says "episodic notes are not sent and the Reflector never runs on the cloud tier"; jana-meta reads this as the
default, lifted only while `tutor_memory_online` is effective, for the two data classes above. **TABLE DAT-18a**
(`data-model.md` line 418) gains, in jana-meta only, one row: "Episodic notes and the Reflector's evidence lines | To
the cloud gateway per request, pseudonymous, scrubbed; `store: false` | `tutor_memory_online` | `tutor_memory_online`
| The Reflector waits for a local candidate or the consent; the block falls back to the MDL-25 variant | S2". The
`dat18_egress_field_allowlist` test gets the row's field list. JM-D9's "the Reflector stays local because it reads
private notes" is amended to "stays local unless `tutor_memory_online` is on". New stored fields and their
classification (PRV-03): `study_activity` (learning event, device, synced as events are), `companion_episodes`,
`companion_summary`, `commitments`, `note_recalls` (operational, device-local, never egress, retention as §19.4).

### 19.7 Budget (estimate)

Spark prices from `defaults.toml` line 38 (input $1.25, cached input $0.15, output $4.25 per 1M tokens). Each row is
**one exchange in full**: every request it makes, reasoning billed as output, one correction included where the row
says. Today every reasoning level of `strong-model` maps to Spark `minimal` (`defaults.toml` line 34), so no "low"
case is costed. The figures are estimates until measured with a cold cache and a maximum tool round.

| Call | Alias | Tokens (in uncached / cached / out) | Per exchange | Per session (typical) |
|---|---|---|---|---|
| Learner block in Study and research prompts | none | +300 input per request | +$0.0004 | +$0.002 |
| Opener wording (phase 2) | `fast-model` | 200 / 400 / 80 | $0.00065 | 1 × $0.00065 |
| Companion turn, no tool round | `fast-model` | 800 / 2,500 / 250 | $0.0024 | |
| Companion turn, one tool round (two requests) | `fast-model` | 1,800 / 2,500 / 300 | $0.0039 | 12 turns ≈ $0.047 |
| Companion turn, two rounds plus one correction | `fast-model` | 3,000 / 5,000 / 500 | $0.0066 | worst case |
| An aid made from the thread | Study's own job (`strong-model`) | as §18.7a parts | $0.03–0.06 | 1 × $0.05 |
| Reflector on Spark (JM-D21) | `strong-model`, minimal | 1,800 / 0 / 600 | $0.0048 | 2 write points ≈ $0.0096 |
| Check-in extractor | `fast-model` | 500 / 0 / 80 | $0.001 | per qualifying turn, ≤ 3 × $0.003 |
| Rolling summary, heartbeat, routing, Last time card | none | code | $0 | $0 |

A typical session (opener, 12 turns with one tool round, one aid, two write points, two extractor runs) is **about
$0.11**; without an aid about $0.06. Caps: `companion.per_day_usd = 0.50`, `companion_turns_per_day = 60` and
`tutor_memory_jobs_per_day = 20`, enforced by the gateway's ledger reservation (§19.4). Twenty such sessions are an
estimated $2.2 of the credit, not a bound.

### 19.8 Done when

**Phase 1.** `ProcessingRequest.learner` validates, carries only MDL-25's fields and reaches the gateway prompt; the
research conversation on an `O` profile never asks the level and the brief's level is `o_level` without the model
having set it; a Study quiz submission records one `study_activity` per item after Study's own transaction, a repeat
submission records nothing, and `kc_mastery`, `review_cards` and `learner_misconceptions` are byte-identical before
and after; Study activity shows on Progress and the knows page; closing Study queues a `study_end` Reflector job whose
evidence lines name Study activity by pack labels only; the Last time card names the last session's date, mode and
subject from the facts and shows the template offline; a `v18` profile upgrades to `v19` and the fresh and upgraded
schemas match.

**Phase 2.** **Your tutor** opens from the library and from a source with an opener whose every number appears in
the facts beside its label; two concurrent opens on one day return one episode; a homework question is handed to the
guided tutor with no model call and the question in the action payload; "make me 10 flashcards on this" creates a
Study job and its button survives a reconnect and a restart; the rolling summary after three episodes lists their
topics with counts, validates, and is reproduced by a replay from the event log; an episode's turns are purged at 90
days; a compaction summarises the dialogue and loses no summary entry; the plan's warm-up lists due Study cards and
`open_study_deck` opens the deck; a cloud companion call carries no past-session transcript hit; a switch to another
profile shows nothing of the first.

**Phase 3.** With `tutor_memory_online` off, a Reflector job on a Glimmer-free machine is skipped `no_local_candidate`
as today and an explicit "remember that…" is declined; with it on, a `session_end` job runs on Spark with `store: false`,
writes a note, the next cloud Coach call carries the note in the records fence, and an explicit request still needs a
local candidate; a consent withdrawn during a job drops its result; a note matching the scrub is withheld and flagged;
"mock paper on Saturday" on a Thursday produces one `event_checkin` with `due_from` Sunday 07:00 local, shown once,
dismissed and remembered, expired after 72 h, never between 22:00 and 07:00; a note is `supported` only when its cited
evidence spans two sessions and `fading` at 90 days; the gateway refuses the 61st companion turn of a day with
`plan_limit`; the desktop notification appears only with the setting on and the OS permission granted.

### 19.9 Tests

Named in the repository's style (`services/agent-core/tests/test_<area>.py`, one function per requirement):

- `test_w8_study_learner_block.py`: `test_processing_request_carries_mdl25_fields_only`,
  `test_learner_block_data_selects_focus_kcs_first_and_caps_at_24`,
  `test_the_research_chat_never_asks_a_level_an_o_profile_holds`, `test_an_a_profile_keeps_the_level_question`,
  `test_brief_level_is_set_by_code_before_validation`, `test_research_task_lines_hold_bands_as_words_not_ids`,
  `test_a_cloud_study_request_carries_nothing_outside_mdl25` (extends `test_dat18_egress.py`).
- `test_w8_study_activity.py`: `test_a_submission_records_one_activity_per_item_after_the_study_transaction`,
  `test_a_repeat_submission_records_nothing`, `test_a_preliminary_check_records_nothing`,
  `test_an_omitted_answer_is_skipped`, `test_kc_tags_weights_sum_to_one_and_cap_at_three`,
  `test_mastery_review_and_misconception_tables_are_unchanged_by_study_activity`,
  `test_a_card_review_records_an_activity_and_keeps_the_study_scheduler`,
  `test_aid_made_is_recorded_at_completion_not_at_create_job`, `test_a_study_session_opens_once_per_day_and_ends_on_idle`,
  `test_study_end_queues_one_reflector_job`, `test_reflector_lines_for_study_name_pack_labels_never_titles`,
  `test_v18_profile_upgrades_to_v19_and_matches_a_fresh_schema`.
- `test_w8_opener.py`: `test_facts_pick_the_last_ended_session_of_any_mode`, `test_at_most_three_facts_are_chosen_in_order`,
  `test_the_template_is_used_offline_and_without_a_candidate`, `test_wording_contains_every_chosen_number_beside_its_label`,
  `test_a_changed_fact_invalidates_the_cached_wording`, `test_the_opener_falls_back_to_the_template_after_one_correction`.
- `test_w8_companion.py`: `test_one_episode_per_profile_per_day_under_concurrent_opens`,
  `test_homework_is_handed_to_the_tutor_with_no_model_call_and_the_question_in_the_payload`,
  `test_distress_is_screened_before_routing`, `test_recall_goes_in_the_user_message_and_the_prefix_is_byte_identical`,
  `test_the_status_line_is_appended_only_when_its_key_changes`, `test_fact_binding_rejects_a_number_with_the_wrong_label`,
  `test_make_aid_creates_a_study_job_and_a_durable_action`, `test_actions_survive_snapshot_hydration_and_restart`,
  `test_start_research_never_skips_the_conversation`, `test_study_search_uses_the_literal_matcher_and_integer_refs`,
  `test_progress_read_is_a_fixed_query`, `test_session_recall_past_scope_stays_in_the_profile`,
  `test_a_cloud_call_is_never_offered_past_scope_recall`, `test_a_cloud_call_gets_study_search_only_under_study_materials`,
  `test_a_profile_switch_shows_nothing_of_the_first`, `test_model_unavailable_is_raised_before_the_companion_branch`.
- `test_w8_rolling_summary.py`: `test_the_fold_updates_sections_in_place_and_advances_the_cursor`,
  `test_a_replay_from_the_event_log_reproduces_the_body`, `test_sessions_count_once_per_session_id`,
  `test_entries_untouched_for_thirty_days_leave`, `test_a_forget_never_touches_the_companion_summary`,
  `test_compaction_folds_the_summary_first_and_summarises_the_dialogue`, `test_a_stale_open_episode_is_ended_and_reflected_on_restart`,
  `test_episode_turns_are_purged_at_ninety_days`.
- `test_w8_plan_study_cards.py`: `test_the_state_collector_reads_due_study_cards_whose_source_exists`,
  `test_the_warm_up_block_carries_study_cards_under_the_review_share`, `test_plan_generated_validates_with_study_cards`.
- `test_w8_checkins.py`: `test_the_lexical_gate_skips_the_extractor`, `test_a_low_confidence_commitment_is_dropped`,
  `test_a_past_date_is_dropped`, `test_saturday_on_a_thursday_is_due_sunday_0700_local`,
  `test_a_quoted_text_fails_the_write_policy`, `test_at_most_one_shown_per_day_atomically`, `test_quiet_hours_hold_delivery`,
  `test_dedupe_key_and_dismissal_are_remembered`, `test_expiry_at_due_until`, `test_an_exam_reminder_day_shows_no_checkin`,
  `test_the_first_accepted_turn_of_an_opened_checkin_marks_it_answered`, `test_a_deleted_source_session_detaches`,
  `test_a_profile_switch_cancels_pending_notifications`, `test_the_notification_body_is_the_kinds_template`,
  `test_resolved_commitments_are_purged_after_thirty_days`.
- `test_w8_memory_online.py`: `test_without_the_consent_the_reflector_is_skipped_as_today`,
  `test_an_explicit_request_still_needs_a_local_candidate`,
  `test_with_the_consent_a_session_end_job_runs_on_the_cloud_with_store_false_and_writes_a_note`,
  `test_the_next_cloud_coach_call_carries_the_note_in_the_records_fence`, `test_a_consent_withdrawn_mid_job_drops_its_result`,
  `test_the_cloud_notes_variant_is_scrubbed_by_filter_policy_secrets_and_redactor`,
  `test_a_scrub_match_withholds_the_note_and_flags_it`, `test_memory_recall_refs_resolve_on_cloud_calls_under_the_consent`,
  `test_transcripts_documents_and_names_never_leave`, `test_the_consent_requires_cloud_tier_and_a_shipped_notice`,
  `test_the_egress_policy_knows_the_feature`.
- `test_w8_note_lifecycle.py`: `test_confidence_is_derived_from_two_distinct_session_ids`,
  `test_fading_at_ninety_days_is_derived_and_first_to_consolidate`, `test_recall_rows_order_notes_within_the_allowance`,
  `test_student_request_notes_are_never_consolidated_away_but_still_expire`, `test_contradiction_still_creates_a_pending_note`.
- Gateway (`services/cloud-gateway/tests`): `test_w8_study_learner_prompt.py`
  (`test_learner_is_in_the_user_message_and_the_prompt_names_it_as_data`), `test_w8_companion_limits.py`
  (`test_the_61st_turn_is_refused_with_plan_limit`, `test_a_reflector_job_reserves_its_bound_under_its_feature`,
  `test_unknown_toml_keys_still_fail_and_the_typed_ones_load`).
- UI (`packages/ui/test`): `last-time-card.test.tsx`, `companion-thread.test.tsx`, `checkin-card.test.tsx`,
  `knows-confidence.test.tsx`.

**Study-memory eval cases.** The existing memory harness (`scripts/jana_tools/harness/memory.py`) loads session
fixtures shaped as a tutoring session (`session_state`, line 143: problem, plan, board, step, rung; `transcript`,
line 161: student and tutor rounds) and cannot run these, so they are **pytest scenario tests** under
`services/agent-core/tests/scenarios/w8/*.yaml` with a small loader in `tests/w8_scenarios.py`, registered as suite
`companion` in `evals/suites.toml`; the rubric below is written before any run and a held-out copy of each case with
different seeds is kept out of development:

| Case | Rubric (pass or fail, by code) |
|---|---|
| `study_quiz_activity.yaml` | a Study quiz miss on an item tagged `kc.phy.o.motion.solve_with_equation` records `study_activity` with that tag and leaves the KC's band unchanged |
| `last_time_card.yaml` | after a physics session on 2026-10-10, the 2026-10-11 card names physics and 2026-10-10 and no other date or number |
| `research_level_known.yaml` | persona `p_o_chemistry` (`evals/memory/personas.yaml` line 7): the conversation's turns never contain "level" as a question and the brief's level is `o_level` |
| `study_note_capture.yaml` | notes written from Study evidence pass `grader.en.yaml` in every category and cite only Study events |
| `companion_recall_local.yaml` | on a local candidate, "what did we say about projectiles" returns the seeded past-session line; on a cloud candidate the turn offers no past recall and answers from the summary |
| `cloud_block_dat18.yaml` | every cloud request in a Study session with the consent off carries only MDL-25 fields; with it on, only the §19.6 list, scrubbed |
| `checkin_sunday.yaml` | "mock paper on Saturday" on Thursday 2026-10-15 yields one `event_checkin` with `due_from` 2026-10-18T07:00 local and text with no quote |

### 19.10 Demo (4 November), phase 1

Ada, an `O` level physics profile, opens **Research a topic** on projectile motion: Jana asks only what the pack is
for, never the level, and the brief says "O level" from her profile. She takes the pack's quiz; a miss on the
range equation appears under **Study activity** on Progress, and the knows page shows the tutor saw it. She closes
Study; the Reflector (on the demo laptop's Glimmer) writes "Mixed up range and maximum height in projectile
questions (2026-11-04)". Back on Home, the **Last time** card reads "Last time you worked on projectile motion in
Study today; 8 cards are due and your exam is in 19 days." Every number on the card came from the facts, and the
ledger shows the session's cloud cost under $0.10. (If phase 2 lands by 1 November: **Your tutor** replaces the card
with the same facts worded by Spark, and "make me ten flashcards on range" creates the job from the thread.)

### 19.11 Phase 4 (sketch)

"What works for you" overlays: per-learner, per-topic procedural notes of hermes's skill kind ("for quadratics, a
sketch first, then the formula"), written by the Reflector from policy decisions (`learner/policies.py`) and their
outcomes, kept in a new `overlays` store (`contracts/learning/overlay.schema.json`: `{overlay_id, kc_or_topic_id,
guidance ≤ 200, supports[], contradictions[], confidence, status: pending | kept | rejected}`), shown as an index of
name and ≤ 60-character description in tier 5 and loaded on demand by an `overlay_read` tool, pending on the knows
page until the learner keeps them, never evicting or editing the signed teaching skills. Specified after phase 3 lands
and the Study-memory scenarios have two weeks of nightly runs.

### 19.12 What the review changed

`LEARNING_AGENT_REVIEW.md` (2026-10-29) against the first draft; each finding and where this version answers it:

| Finding | Answer |
|---|---|
| B1 topic tags as mastery evidence; B3 `review` events schedule learner cards | JM-D26: Study writes `study_activity` only, ignored by the mastery and review projections (§19.3.2) |
| B2 no atomic, idempotent seam; `submit_quiz` double-records; `create_job` is not the aid write | One seam per activity, after Study's own transaction, idempotent by `ref`; `aid_made` at completion (§19.4 `study.py`) |
| B4 wrong contract pointers; no migration | Root `oneOf` and erased branch, `Session.origin`, `status_phase`, `tutor_event`; `migration_v19` and the upgrade test (§19.3) |
| B5 Study warm-up lost in `plan_generated`; `plans.py` missing | `study_cards` through collector, block, event, view and action (§19.4 `plans.py`); moved to phase 2 |
| B6 egress contradicts the notice; grader reused; `store: false` oversold | Notes and evidence lines only; explicit requests local; past recall local-only; `study_search` under `study_materials`; the grader stays independent; honest notice (§19.6) |
| B7 consent not registrable; reflector absent from `roles_allowed` | Full registration list (§19.3.5); `roles_allowed` and `candidate_ready` (§19.4) |
| B8 an open session escapes retention | Daily episodes (JM-D23); `_transcripts` applies unchanged (§19.4 `retention.py`) |
| B9 summary in `sessions.summary` corrupted by forget; no cursor | Own table with `cursor_seq`; no free text; code-only fold (§19.3.3, §19.5.3) |
| B10 conversational turns are not evidence; compaction without callback; recovery misses the thread | Turns are not evidence, `companion_mid` dropped; `summarise` callback; stale episodes ended and reflected on restart (§19.5.1, §19.5.4) |
| B11 raw ids from `own_evidence`; `progress_of` misused; generated register edited; MEM-05 | Fixed queries with per-call `RefTable` refs; `toolsets.json`; the MEM-05 amendment (§19.3.3) |
| B12 lifecycle bypasses MEM-09 and bounds | Derived `confidence` and `fading`; bounded recall priority; retention wins (JM-D28, §19.3.5, §19.5.6) |
| B13 TOML keys fail strict config; no admission | Typed `Limits` and `CompanionConfig`; ledger reservation by feature (§19.4) |
| B14 actions and openers not durable | Durable `actions` in the projection and snapshot; opener in the HTTP reply with `opener_id` (§19.3.3) |
| N1 scope; N2 band claim; N5 level seam; N6 totals; N7 evals; N8 UI entry; N9 serializer, gates, fact binding; N10 device-local and retention | JM-D25 (phase 1 only); no band claim, physics demo; `research_chat` by code (JM-D29); budget recomputed; pytest scenarios; library entry; `learner_block_data`, the gate set and fact binding; JM-D27 and the retention rows |

## 20. Video as a Study source: a YouTube lecture, understood (W9)

Status: **specified 2026-10-31, reworked the same day after review** (`SPEC_W9_W10_REVIEW.md`: eleven blocking
findings on the first draft, all confirmed in the code; §20.11 maps them). The owner's goal (2026-10-31): paste a
YouTube video and have Jana understand what it teaches. **Owner, 2026-10-31: JM-D30 to JM-D34 agreed in their first
form**; JM-D34 is narrowed below (frames are read as text, not as pictures); **JM-D42 was answered on 2026-10-31 by the
spike** (`SPIKE_JMD42.md` on branch `claude/fervent-jang-355d03`): the official embedded player does not play in the
packaged macOS app (YouTube refuses the `tauri://localhost` origin with error 153, and `useHttpsScheme` is a Windows
and Android option), so this release ships **Watch on YouTube** at the moment and no embedded player; JM-D40, JM-D43
and JM-D44 are **proposed, owner to confirm**. Paths are relative to this repository; line numbers were read on 2026-10-31.

**W9 built 2026-10-31** (JM-D30 to JM-D34 as agreed; JM-D40, JM-D43 and JM-D44 at their recommended answers;
JM-D42 as the spike answered it: no embedded player, no CSP change, Watch on YouTube at the moment). Every §20.8
bullet passes a named test: `test_w9_links.py`, `test_w9_video_link_source.py`, `test_w9_teaching_outline.py`,
`test_w9_video_file.py`, `test_w9_companion_moment.py`, `test_w9_scenarios.py` (`scenarios/w9/youtube_lecture.yaml`
through the generalised loader, suite `companion`), the gateway's `test_w9_teaching_outline_gateway.py` and
`test_w9_video_file_gateway.py` (the first video test runs the real sandboxed worker on a synthetic clip), the worker's
`services/study-worker/tests/test_video_frames.py`, the UI's `study-link-add.test.tsx`, `study-player.test.tsx`,
`study-outline.test.tsx`, `study-citation.test.tsx` and `companion-thread.test.tsx`, and the client core's
`study-workspace.test.ts` and `companion.test.ts`. The parser is `engine/study_links.py`; the outline's device half is
`engine/study_outline.py`; the frames are `study_worker/media.py` and `cloud_gateway/study_recording.py`; the panes
are `learn/StudyPlayer.tsx`, `StudyOutline.tsx` and `StudyLinkAdd.tsx`. `contract-additions-w9.json` records the
additions, applied to `contracts/` with codegen; the learner migration is v23 (W10 needed none). The O-level physics pack gained a projectile-motion subtopic on
2026-10-31 (`content/curriculum/phy/o/kcs/projectiles.yaml`, pack 1.1.0, skill `phy-o-projectiles`), so the §20.10
demo's concepts map to its skills with the shipped pack, not only with the seeded fixture. Where the build
departs from the text above, and why:

- **Pieces §20.3 does not list, needed by the build** (each marked "Needed by the build" in the additions file):
  `Source.chapters` (a pasted transcript's chapters by code need a home; the chapters aid is model-made and cited),
  `Source.frames_choice` (the file variant's `frames` choice has to survive from create to the extraction request),
  `ExtractionRequest.frames`, `ExtractionResponse.has_video` and `ExtractionResponse.frames` (the downgrade decision
  and each frame's reason and read state are the gateway's; the device counts `screened_frames` from them),
  `CloudUploadCreate.kind` gains `video`, `StudyError` gains `unsupported_link` and `transcript_too_long`, and the
  `payload_study_activity.ref` pattern gains `src:` (`source_added` was in the enum since W8 but never written; the
  Study desk now records it, while a Study session is open, as an aid is).
- **Lines keep their moments.** A timed chunk is at most 4,000 code points, as specified, but every line inside it
  keeps its own `[m:ss]` prefix, so "Open at" is per line, a citation names its line's moment (not the chunk's
  start), the companion's excerpts carry the line's moment and the outline's `at_ms` comes from the cited line by
  code. The model sees the prefixes; the prompt tells it never to copy a moment into text.
- **The two-hour bound** refuses a last timestamp at or past 2:00:00 (a line at exactly 2:00:00 has no room for a
  locator inside `Locator.time`'s bound); the last chunk ends 5 s after its last line, capped at two hours.
- **`at_ms` is code-written.** The gateway's structured output omits `at_ms`, `kc_ids`, `outside_packs`, `skips` and
  `for_you`; a model cannot be trusted to turn "4:12" into milliseconds. `TeachingOutline` keeps `at_ms` optional for
  that reason. The gateway sets the response's `claims` to the outline's items in order by code, so the verifier's
  per-item support maps one to one and a dropped item leaves the outline.
- **Skill mapping.** `kc_tags` as it stands maps text to a topic only when the topic's title phrase appears in it, so a
  concept's cited text alone almost never names a topic. A concept is scored within the topics the whole transcript
  names (`matching_topics` over the transcript), keeping only skills whose statement shares a content word with the
  concept's name and cited text (`kc_tags(..., within=, require_overlap=True)`); `skips` are the tagged topics' skills
  that neither `kc_tags` over the whole transcript nor any concept tags. **The shipped O-level physics pack has no
  projectile-motion skill and no statement with the word "range"**, so on the installed pack the demo's concepts are
  "outside the packs"; `test_w9_teaching_outline.py` seeds a projectile subtopic (range, time of flight, maximum
  height, resolving, drag) and checks the range concept maps to its skill there, and records the installed-pack
  result. A projectile KC in the pack is the curriculum lead's.
- **The pending turn context** lives in memory on the companion desk (`CompanionDesk.pending_context`), not in
  `companion_turn_context`: that table's key is a turn id, and the context exists before its turn. It is consumed by
  the next accepted turn, discarded with a profile switch, and never written to disk. The ±30 s lines join the
  own-materials fence (cut by `strip_for_cloud` without `study_materials`); "About 4:12 in <title>" stands outside
  the fence as a labelled fact.
- **"What haven't I got yet"** is offered on every turn, not matched by phrase: when a ready `teaching_outline` exists
  on a non-private source, its `for_you` skills (not yet secure first, at most twelve) join the typed facts with the
  moment each is taught at, and the role prompt tells the model to select them by `fact_refs`.
- **Frame times.** PyAV exposes no container chapter markers, so "chapter boundaries first" has nothing to read at
  extraction time; the worker scans keyframes only (the CPU limit) and reports scene changes as colour-thumbnail
  differences; the gateway keeps chapter-tagged candidates first, one per 30 s, 60 per file, ten per worker call. A
  frame with no OCR reader is `unreadable`, never a failed extraction (the transcript is the material).
- **The external-link opener.** The shell has no opener command or plugin; the one path the app has is Ask anything's
  `<a target="_blank" rel="noopener noreferrer">`, and `BROWSER_OPENER` (client core) takes the same path through
  `window.open`. Whether the packaged WKWebView opens that in the system browser is unverified: Tauri sets no
  `on_new_window` handler, so wry's delegate may drop the request. The spike did not test it. If it is dead, Ask
  anything's sources are dead the same way; a shell command behind the opener seam is the fix, a decision of its own.
- **Limits.** `video_minutes_per_month` is a gateway-held limit (`GATEWAY_HELD_LIMITS`), derived as 60 times
  `recording_hours_per_month` when unset, never signed into entitlements (as W8's caps). Fixed 1 November: before
  transcription or frame processing, the gateway atomically admits the decoded duration in milliseconds against
  the shared recording pool and, for videos, the video ceiling. Authenticated subscription seats share these limits
  across devices in the subscription's billing month. The durable `study_media_usage` ledger counts each admitted
  extraction once; failed, cancelled and uncertain attempts remain counted until the month ends, and deleting a
  source cannot refund processed media. Expired month rows are purged; no source text or media is retained there.
  `upload_max_mb` is 100 in `plans.toml`, the worker's cap, and
  `test_m45_regional_plans.py` says so.
- **Existing tests whose assertions changed:** `test_companion_continuity.py` expects the forward migration to apply
  v22 and v23 (the transcript still survives); `test_m45_regional_plans.py` reads 100 MB.
- **Not built:** nothing of §20.8. Gates on 2026-10-31: codegen check, data inventory, retention coverage, erasure
  registry, tool snapshot, eval lock, `pnpm lint`, mypy and ruff all pass; the W9 suites pass; `ruff format --check`
  flags `engine/toolround.py` and the generated `contracts/api/endpoints.py`, and `prompt-snapshots` (and
  `prm22_snapshot_diff_fails`) flag sixteen solver and checker prompts, all from another session's uncommitted solver
  work, which also failed `uxs18_solution_on_request` in one full run (`math_solve` not offered) and not the next.
  `uv run pytest services` otherwise: 4,407 passed; `test_w8_companion_followups.py`'s ready-materials order failed
  once under full-suite load (two sources created in one millisecond tie on `updated_at`; it passes alone and in the
  companion suites, and W9 does not touch that order). `pnpm test` passes but for `dsn25_brand_placements`, which flags
  `settings.export.desktop_required`, another session's uncommitted export copy. The browser preview was not run: the
  app needs a running core and profile, which the pane does not have.

**Live-run fixes 2026-11-01** (a live run of W9 and W10 in the browser host on 2026-10-31; each fix has a test
that would have caught it; nothing committed):

- **Transcript layout.** In the material pane of a `video_link` source each transcript line was a wrapping row with
  the text column `flex-1` beside **Open at** and **Ask about this moment**, so in the pane's width the words were
  squeezed to one or two a line. Each line is now a column: the text row takes the full width (`w-full`, the words
  `flex-1 min-w-0` past the moment) and the two buttons sit on their own row under it (`learn/StudyPlayer.tsx`;
  `study-player.test.tsx` asserts the layout classes, since jsdom measures nothing).
- **Raw copy key.** A failed `teaching_outline` job showed `study.generate.teaching_outline` as its label: W9 added
  the job kind without its `study.generate.*` label, and `concept_map` (W8) had none either. Both keys exist now, as
  does `study.tool.chat`; `study-job-labels.test.tsx` reads `JobKind` and `AidKind` from the contract and asserts a
  label for every kind, and `study-workspace.test.tsx` renders a failed outline job in words.
- **Duplicate time.** An outline row showed "Open at 4:12" and a citation badge "04:12" for the same moment. The
  badge beside an Open-at button is now the reference number (`[1]`); its name and tooltip keep the location
  ("Projectile motion · At 04:12"), so the passage still opens (`StudyCitation.numbered`, set by `StudyOutline.tsx`
  for timed rows; `study-outline.test.tsx` asserts the time appears once a row).
- **Chapters on sparse transcripts.** A pasted transcript with one line every 30 to 40 s became a chapter a line under
  the 20 s gap rule. The rule is now: a heading always starts a chapter; otherwise a gap of 60 s or more does; and
  never more than 12 gap-made chapters a source, the smallest gaps merging first (`study_links.GAP_MS`,
  `GAP_CHAPTERS_MAX`; `test_w9_links.py` covers the sparse paste, the cap and a heading past the cap; the panel
  fixture is unchanged, its chapters being headings).
- **"What haven't I got yet".** With the pack's projectile skills the code fact set was built, but the model's reply
  used an unlabelled number ("1"), fact binding exhausted its nudge and the learner saw the canned line (trace:
  `fact_binding` `number:1:unit:none`, then `model_claims`, `exhausted_canned`). As §19 does for a made aid, a reply
  refused twice with an outline fact set in hand now falls back to a code-built line from it ("Of this video's 6
  skills, 6 are not yet secure: …" with at most six statements; `companion.outline_line`,
  `companion.turn.outline.*` in `engine.en.yaml`), never the canned line. The fact set also carries labelled counts
  (`outline_skills`, `outline_skills_not_yet_secure`, unit `skills`) and the counts join the binding sources, with
  `skill` a fact unit, so a reply naming "2 skills" or "1 is not yet secure" binds (`test_w9_companion_moment.py`).
- **Wrong gateway on the shared port.** The dev host accepted a gateway from another project on its port (it answered
  the ping with the budget header) and every new kind failed with `processing_failed`. `hackathon_app.check_gateway`
  now also requires the `jana-gateway-version` header to equal `cloud_gateway.app.VERSION` and fails closed naming
  the port and the version found (or `none`), before the budget check; it takes a transport for its test
  (`scripts/tests/test_hackathon_app.py`). Because the parent project's gateway also served `1.1`, this repository's
  gateway version is now **1.2** (the W9 kinds are an API addition; `test_m19_gw_auth.py` reads 1.2).
- **Outline mapping looseness.** "Displacement time graph" mapped to three skills that merely say "time" or
  "vertical" (time of flight, components, resolve) and not to the trajectory-and-graphs skill. `kc_tags` gained
  `focus` (the concept's name, whose words count twice; plain plurals folded on this path only), `min_overlap` and
  `close`; `study_outline.fill` scores a concept by its name and cited text within the transcript's topics with a
  least overlap of 3 (one name word and one cited word, or two name words) and keeps a second skill only within 10%
  of the best (`CONCEPT_MIN_OVERLAP`, `CONCEPT_CLOSE`). Study-activity tagging is unchanged.
  `test_w9_teaching_outline.py` adds the graph concept: on the installed pack it maps to `trajectory_graphs` alone,
  on the seeded fixture (no graphs skill) it is outside the packs, and every other concept maps to exactly one skill;
  `scenarios/w9/youtube_lecture.yaml` lists it (suite `companion` 2026-11-01.1, lock rewritten).
- **Gates on 2026-11-01:** codegen check, `pnpm lint`, mypy, `pnpm test` and `uv run pytest services` (four shards)
  pass, but for `test_w10_overview.py::test_tiles_equal_the_subject_map_and_the_skill_map` ("UI fixture is stale"):
  the uncommitted projectiles pack adds a topic the committed `packages/ui/test/fixtures/curriculum-overview.json`
  lacks; regenerate it with `JANA_WRITE_CONCEPT_FIXTURES=1` when that pack lands (not this session's to touch).

**What exists.** A recording is already a Study source (STU-22): the file goes to the gateway whole under
`study_materials` (`engine/study.py` line 2362: a recording waits for the cloud), the sandboxed worker decodes the
audio in memory (`services/study-worker/study_worker/media.py`), Muse Spark transcribes 60-second `input_audio`
segments (`cloud_gateway/study_recording.py` `transcribe`, line 61), chunks carry `time` locators
(`contracts/study/workspace.schema.json` `Locator`, ≤ 7,200,000 ms), citations print timestamps
(`StudyCitation.tsx` line 25), and the material pane plays the file with chapters and a transcript that seek
(`StudyGenerate.tsx` `RecordingPlayer`, line 143–190, the `<audio>` element at 162; `study-workspace.ts` `loadMedia`
line 282–290 and the citation seek at 838). Pasted text is a source (`StudyDesk.create`, `engine/study.py` line
449). Study links text to syllabus skills by word overlap with KC statements (`engine/study_topics.py` `kc_tags`,
line 57–80, ≤ 3 skills). Photos in Study are **OCR text** from the worker (`study_worker/__main__.py` line 45–61);
no Study path shows an image to a model. What does not exist: a link as a source, a player for a video Jana does not
hold, a statement of what a video teaches, and any reading of a video file's picture.

**The constraint that shapes this section.** YouTube's terms let an app embed and play a video with the official
player, including seeking to a time, and nothing else: no downloading of video or audio, so Jana's own transcription
cannot run on it, and caption tracks come from the official API only to the video's owner. So the picture is
YouTube's, and the words come from the transcript YouTube itself shows the learner, copied from the transcript
panel with its timestamps and pasted into Jana once. That paste is the whole of what the learner does beyond the
link, and it works for any site that publishes a transcript.

### 20.1 What the learner gets

| Part | What it is |
|---|---|
| **Paste a YouTube link** | A new source kind, `video_link`: the link, then the video's transcript pasted from YouTube's panel (a three-step hint), then a title (prefilled "YouTube video"). Ready in seconds; nothing downloaded. |
| **Watch on YouTube, at the moment** | The material pane shows the transcript with its chapters; every line, chapter and citation carries **Open at 04:12**, which opens `youtube.com/watch?v=<id>&t=<seconds>` in the learner's browser, as a research pack's sources open their pages today. No video plays inside Jana in this release (JM-D42). |
| **What this video teaches** | A new aid, `teaching_outline`: the video's learning objectives in order with their moments, the worked examples it shows, the concepts it introduces, and what it assumes you already know, each citing a transcript line and checked by Study's verifier. Around it, by code on the device: which syllabus skills each concept serves (or "outside the packs"), which skills of those topics the video never reaches, and for this learner which of its skills are secure, learning or not started. |
| **Everything Study already makes** | Notes, summary, flashcards, quiz, podcast, concept map and lesson plan from the transcript, each claim citing a moment that seeks the player. |
| **Ask about this moment** | On a transcript line (a YouTube video) or the player's playhead (a file): Your tutor opens with the transcript lines around that moment as cited context, and the learner types the question. Pausing to ask, without streaming anything. |
| **Your tutor** | "Where did she derive the range equation?" finds the moment and offers **Open the moment**; "what does this video teach that I haven't got yet?" is answered by code from the outline's skills and the learner's bands, then phrased. |
| **A video file you have** | A lecture you recorded or a screen recording: Jana's own transcription (the existing pipeline), a `<video>` player with a filmstrip, and the **writing on the board or slides read as text** at chapter and scene changes, cited "04:12 · on screen". Diagrams in a frame are not read in W9 (JM-D34). |
| **Seeing the picture** | Jana's models read still images, not video; in Study, images are read as text. For YouTube the picture is in the learner's browser: a screenshot or phone photo of the board, added as a photo, is read through the photo pipeline. |

### 20.2 Decisions

| # | Decision | Status and working assumption |
|---|---|---|
| JM-D30 | How does a YouTube video's text reach Jana? | **Agreed.** The learner pastes the video's transcript. No download, no caption scraping, no third-party transcript service. A paste without timestamps is plain text (no moments). |
| JM-D31 | How is it played? | **Agreed, then overtaken by JM-D42's answer:** no embedded player in this release. Every moment opens `youtube.com/watch?v=<id>&t=<s>` in the learner's browser. YouTube links only in this release. |
| JM-D32 | What does the device send to Google? | **Moot after JM-D42:** Jana opens no connection to YouTube. Opening a link in the learner's own browser is what a research pack's sources do today; no new feature, consent or CSP change. |
| JM-D33 | Does "what it teaches" need a new model path? | **Agreed, narrowed:** one Study aid kind, one structured call over the **transcript chunks only**: no syllabus, no learner block (the mapping, the skips and the learner's bands are code on the device). |
| JM-D34 | Files: frames? | **Agreed, narrowed:** frames are extracted and **read as text (OCR) in the sandboxed worker**, as photos are today; no model sees a frame in W9. Board and slide writing is cited; diagrams are not read. A vision read of frames is a later decision with its own budget. |
| JM-D40 | May the app capture a frame of an embedded YouTube video? | **Proposed: not in this release.** The player's pixels are unreachable, and an automated capture is the terms question JM-D30 avoids. A learner's screenshot as a photo is the path. |
| JM-D41 | Where does the player's CSP exception live? | **Dropped:** no player, no exception; `frame-src 'none'` stays. |
| JM-D42 | Origin spike before the week is committed | **Answered 2026-10-31 (`SPIKE_JMD42.md`): no.** From the packaged app's `tauri://localhost` origin YouTube answers error 153 for every variant (plain, `origin` and `widget_referrer`, `referrerpolicy unsafe-url`); `useHttpsScheme: true` leaves the macOS origin unchanged (a Windows and Android option). The `postMessage` channel itself works and reports the refusal, and the embed is accepted from an `http://localhost` origin, so a future player means serving the page from a loopback HTTP server or a Jana-hosted player page: a security and hosting decision of its own, not W9's. This release: Watch on YouTube at the moment. |
| JM-D43 | A pasted transcript of someone else's video | **Proposed: yes.** It is the learner's own copy for private study, in their profile, never in packs or a research export, never fetched by Jana (STU-22's D64 note is unchanged: Jana fetches nothing). |
| JM-D44 | Video minutes: per week or per month? | **Proposed:** `video_minutes_per_month`, drawn from the recording pool `recording_hours_per_month` in `plans.toml`, one clock for one kind of thing. |

### 20.3 Contracts

Every addition goes first into `contract-additions-w9.json` in the form of `contract-additions-m45d.json`;
**(storage)** items need the next learner migration (`migration_v23.py` if W9 lands before W10, else v24; v22 is the
latest, `store/sqlite.py` line 39) registered in `store/sqlite.py`, a `store/retention.py` rule, a
`store/profile_stores.py` row and a `scripts/governance/data-inventory.toml` entry (PRV-03).

- `contracts/study/workspace.schema.json`: `SourceKind` gains `"video_link"` and `"video"`. `SourceCreate`'s `oneOf`
  gains the variant `{kind: "video_link", url, transcript ≤ 400,000, title ≤ 120}` beside the inline `text` variant
  (no new route: `POST /v1/study/sources`, the client's `addSource`, redaction and `source_added` apply). `Source`
  gains `link: {provider: "youtube", video_id (11 chars), url} | null`, `transcript_kind: "timed" | "plain" | null`,
  `frames: integer | null`, `screened_frames: integer | null`. `Locator` gains `{kind: "frame", at_ms (≤ 7,200,000),
  frame_id}`. `AidKind` **and** `JobKind` gain `"teaching_outline"`; `Aid` gains `outline: TeachingOutline | null`
  under the kind→field `allOf` rule. The file variant of `SourceCreate` gains `frames: "auto" | "none"` (an
  extraction-time choice on the source, not a per-aid setting).
- New `$defs/TeachingOutline`: model-written and cited: `objectives: [{text ≤ 160, at_ms, citations}] ≤ 12`,
  `examples: [{text ≤ 160, at_ms, citations}] ≤ 8`, `concepts: [{name ≤ 60, at_ms, citations}] ≤ 16`,
  `assumes: [{text ≤ 120, citations}] ≤ 6`; code-written, uncited: `concepts[].kc_ids ≤ 3`,
  `concepts[].outside_packs`, `skips: [{kc_id, statement}] ≤ 6`, `for_you: [{kc_id, band}]`. The gateway's structured
  output is the model part only; the engine adds the rest.
- Transcript parsing (`engine/study_links.py`): two forms, **alternating lines** (a timestamp line, then the text
  line: YouTube's panel) and **same line** (`[m:ss] text` or `m:ss text`); timestamps `m:ss`, `mm:ss` or `h:mm:ss`;
  a line with no timestamp between two timestamped blocks is a **chapter heading**, kept as a chapter, not a chunk;
  lines merge into chunks of ≤ 4,000 code points, the locator the first line's start and the next chunk's start as
  end; a paste whose last timestamp exceeds 2:00:00 is refused with the limit named (the `Locator.time` bound);
  no timestamps at all → one `plain` text source. A verbatim panel paste is a fixture in `test_w9_links.py`.
- New `$defs/Frame` **(storage** `study_frames(frame_id PK, source_id, revision, at_ms, reason: "chapter" | "scene",
  read_state: "read" | "unreadable" | "screened", text)**)**; **no image is stored**: the device holds the file, and
  the filmstrip draws each thumbnail from the local `<video>` element at `at_ms`. Rows go with the source revision.
- Tools: `contracts/registers/toolsets.json` and `engine/memory_tools.py` (line 256): `study_search` items gain
  `locator` (`memory/queries.py` `StudyExcerpt`, line 649, gains it). `contracts/agents/companion-turn.schema.json`
  `action.kind` (line 31–39) gains `"open_moment"`; `contracts/api/events.schema.json` `ev_companion_action.action`
  gains `"open_moment"` with `payload: {source_id, at_ms}`.
- `contracts/api/commands.schema.json`: `CompanionOpen` gains optional `context: {source_id, at_ms}` (Ask about this
  moment). The core keeps it as the episode's **pending turn context** (`companion_turn_context`, operational,
  device-local), consumed by the next accepted turn and discarded after it.
- Study worker protocol (files): `recording_info` gains `has_video`, `has_audio`, `width`, `height`; the worker
  accepts a container with no audio stream (`media.py` line 25–26 refuses one today); new request `video_frames
  {at_ms: [..]}` → `{frames: [{at_ms, text | null}]}`: the worker decodes the **keyframe** nearest each time, runs
  `perception_worker.image.preprocess` (the photo privacy pass, already imported at `__main__.py` line 47) and OCR,
  returns text only; a frame the pass refuses returns `screened`. Frame times are chosen by the gateway: chapter
  boundaries first, then scene changes from keyframe differences, at most one per 30 s and 60 per file, within the
  worker's CPU limit (240 s, `__main__.py` line 17) by batching ≤ 10 frames per call.
- `plans.toml`, `cloud_gateway/config.py` `Limits`: `video_minutes_per_month` drawn from `recording_hours_per_month`;
  the file limit stated truthfully: the worker's 100 MB source cap (`__main__.py` line 24–28) is the limit until
  it is raised, and `upload_max_mb` 200 is reconciled to it.

### 20.4 Changes

| Where | Change |
|---|---|
| `agent_core/engine/study_links.py` (new) | `parse_youtube(url) -> video_id | None` (watch, youtu.be, shorts, embed; else `unsupported_link`); `parse_transcript(text)` as §20.3; chapters from headings and from gaps over 20 s. |
| `agent_core/engine/study.py` | `StudyDesk.create` takes the `video_link` variant beside inline text (line 449): the source is created `ready` with its chunks and chapters, no extraction. A dropped `.mp4/.webm/.mov/.mkv/.avi` is kind `video` **by suffix at create** (`study-workspace.ts` line 344–345 and the core's suffix check at line 507–515), downgraded to `recording` in the `extracted` revision when `recording_info` says `has_video` is false (a body rewrite the revision allows). `teaching_outline` jobs send transcript chunks only; on the reply the engine fills `concepts[].kc_ids` with `kc_tags` over each concept's cited text, `outside_packs` when none, `skips` as the skills of the tagged topics that `kc_tags` over the **whole transcript** never tags, and `for_you` from `kc_views` bands. `frames: "none"` skips frames. |
| `services/cloud-gateway/cloud_gateway/study.py` | `teaching_outline` in `GRANULAR_KINDS` (line 654) with per-claim support; its prompt paragraph: "Say what this lecture teaches, in its order: objectives, worked examples, concepts, what it assumes. Cite the transcript line for each. Never add what the lecture does not say." A `video` file takes the recording path for audio (line 1920–1925); after transcription the gateway picks frame times and calls `video_frames` in batches; frame text becomes chunks with `frame` locators, prefixed "On screen at mm:ss:"; `screened` frames are counted and never returned. |
| `services/study-worker/study_worker/media.py`, `__main__.py` | Stream info; containers without audio; keyframe decode at a time; `video_frames` with the privacy pass and OCR; dispatch (line 29 region). No network, bytes in memory. |
| `agent_core/engine/companion.py`, `api/companion.py`, `content/agent/roles/companion.md` | `resolve_action` (line 638–653) handles `open_moment` from a `study_search` hit's locator; `CompanionOpen.context` is stored as the episode's pending turn context and rendered into the **next turn's** user-message fence (§19.5.1 step 3) as the chunks within ±30 s, **subject to `strip_for_cloud` (line 618)**: on a cloud candidate without `study_materials` effective the fence carries the moment as a labelled fact only ("about 04:12 in <title>"). "What haven't I got yet" is a code fact set: the outline's `concepts[].kc_ids` joined to `kc_views`, offered to the model as labelled records (`companion_facts`), phrased with `fact_refs`. Timestamps are labelled facts: `labelled_numbers` (the `_NUMBER` regex, line 15) treats `h:mm:ss` and `mm:ss` tokens as one number with label `moment`. The role prompt names the moment action and the outline. |
| `agent_core/engine/memory_tools.py`, `memory/queries.py` | `StudyExcerpt.locator`; `study_search` items carry it. |
| `packages/client-core/src/study-workspace.ts` | `addSource` with the `video_link` variant; `loadMedia` serves `video` files; for a `video_link`, `seek` becomes `openMoment(at_ms)`, the browser link `youtube.com/watch?v=<id>&t=<s>` through the app's existing external-link opener (the one research-pack sources use); for a file, `currentTime`; frame locators seek to `at_ms`. |
| `packages/ui/src/learn/StudyLinkAdd.tsx` (new), `StudyWorkspace.tsx` | "Add a YouTube video": link, transcript with the hint ("Under the video, open the description, choose Show transcript, select all, copy"), title; validation messages (unsupported link, over two hours, no timestamps → "saved as text"). |
| `packages/ui/src/learn/StudyPlayer.tsx` (new), `StudyGenerate.tsx` | For a `video_link`: no player; the transcript pane with chapters, a **Watch on YouTube** button (the video's start) and **Open at mm:ss** on every line, chapter and citation, each opening the browser at the moment; for a `video` file: `<video>` in place of the `<audio>` element (line 162) with the filmstrip drawn from the element at each frame's `at_ms`; chapters and transcript shared. **Ask about this moment** on a transcript line (link) or the playhead (file) calls the companion open with `context`. |
| `packages/ui/src/learn/StudyCitation.tsx` | The label chain (line 24–33) and grouping (line 49–57) handle `frame` locators ("04:12 · on screen"). |
| `packages/ui/src/learn/StudyOutline.tsx` (new) | The outline: objectives with moments, examples, concepts with skill chips (tap → the learner's map, §21), "Assumes you know", "Not covered here" (the skips, worded without blame), "For you" as band words. |
| `packages/ui/src/learn/CompanionThread.tsx` | The `open_moment` button ("Open the moment, 04:12") and the "About 04:12 in <title>" line above the composer when a context is pending. |
| `services/agent-core/tests/w8_scenarios.py` → `tests/scenario_cases.py` | The loader generalised from `scenarios/w8/` to every `scenarios/*/` folder with a `CASES` registry; `evals/suites.toml` (line 120–126) lists suite `companion` as covering W8 to W10. |
| `packages/i18n/locales/en.json` | `study.link.*`, `study.outline.*`, `study.video.*`, `study.video.open_at`, `study.video.watch_on_youtube`, `study.companion.action.open_moment`, `study.companion.about_moment`. |

### 20.5 Behaviour

1. **Adding a link.** URL → video id or refusal → transcript paste → title (prefilled) → parsed; the source is
   `ready` at once. Headings become chapters; a 20-second gap starts a chapter too.
2. **Watching.** No video plays inside Jana (JM-D42): **Watch on YouTube** and every **Open at mm:ss** open the
   learner's browser at the moment; the transcript pane is the material, with chapters and citations.
3. **What this video teaches.** One structured call over the transcript chunks; the verifier drops uncited
   statements; the engine maps, computes skips and the learner's bands; the outline opens with skill chips into the
   learner's map and moments into the player.
4. **Ask about this moment.** From a transcript line (link) or the playhead (file), the button opens (or reuses)
   today's episode with `context`; the thread shows "About 04:12 in <title>"; the learner's next message carries the
   ±30 s lines in its fence under the Study rule (§19.6); the context is then discarded. Nothing is sent until the
   learner sends.
5. **Your tutor.** A `study_search` hit with a moment → `open_moment`. "What haven't I got yet?" → the engine's fact
   set (outline skills × bands) → the companion phrases it; every skill and band is a labelled record.
6. **Files.** `video` by suffix; whole file to the gateway under `study_materials` as today; audio transcribed; frame
   times chosen; frames OCR'd in the worker after the privacy pass; `screened` counted; text chunks with `frame`
   locators; the `<video>` player and a filmstrip drawn locally; "Drill this frame" is **not** in W9 (a frame's
   picture is never read). No audio stream: frames only, said in the pane. No video stream: a `recording`.
7. **Refusals.** Non-YouTube link; a transcript past two hours; a file over the worker's limit; the monthly minutes;
   each named before anything is sent.

### 20.6 Privacy and consent

To Jana's gateway, under `study_materials` as pasted text is today: the transcript as `document`-class text in
processing requests and the video id in the title; for files, the whole file (`audio` and, for its frames, `image`
read in the worker and never returned as pixels). Frames the privacy pass refuses are never read by a model and never
leave the worker. To YouTube: nothing from Jana. **Watch on YouTube** and **Open at mm:ss** open the learner's own browser, as a
research pack's sources do; what the browser then sends is the learner's, outside Jana (JM-D42). The Ask-about-this-moment lines reach a cloud
candidate only under `study_materials` (§19.6). A pasted third-party transcript is the learner's private copy
(JM-D43). The outline request carries no learner data; bands are joined on the device. Nothing in §20 reaches the
Reflector or the cloud learner block (§19.3.2).

### 20.7 Budget (estimate)

A YouTube video costs no transcription. The outline is one `strong-model` call plus the verifier over ≈ 12,000
tokens of transcript: ≈ 30,000 input and 3,000 output tokens, **$0.05**. A file: the ledger reserves 8,704 input
and 2,048 output tokens per 60-second segment (`study_recording.py` line 84), **$1.18 an hour reserved** at §4.2's
prices (settled lower); frames cost nothing beyond the worker's CPU. Caps: `video_minutes_per_month` from the
recording pool.

### 20.8 Done when

Each accepted YouTube link form yields the id and any other link is refused with the message; the verbatim panel
fixture parses to timed chunks and chapters, a same-line transcript too, a no-timestamp paste to text, a paste past
two hours is refused; a tapped citation or transcript line opens `youtube.com/watch?v=<id>&t=<s>` through the app's
external-link opener and the aids work without any player; a `teaching_outline` on the seeded projectile-motion transcript
lists cited objectives, examples and concepts, maps the range concept to its skill by `kc_tags` (fixture checked),
lists one skipped skill of the matched topic and shows the learner's bands; the outline's cloud request carries
transcript chunks and nothing else; "where did she derive the range equation" yields `open_moment` with the hit's
time and fact binding accepts "04:12"; "what haven't I got yet" answers from the code fact set; Ask about this moment
puts the ±30 s lines in the next turn's fence only under `study_materials` and discards the context after it; a
dropped `.mp4` becomes a `video` source, frames are OCR'd after the privacy pass with a screened frame counted, and a
quiz cites "mm:ss · on screen"; `frame-src 'none'` is unchanged; the PRV-03 inventory test passes; every gate green.

### 20.9 Tests

- `test_w9_links.py`: the id parser; the transcript parser over the verbatim panel fixture, the same-line form,
  headings, merged lines, the two-hour bound and the no-timestamp case.
- `test_w9_video_link_source.py`: the `SourceCreate` variant, chunks and chapters, `source_added`, redaction, limits.
- `test_w9_teaching_outline.py`: `JobKind`/`AidKind`/`GRANULAR_KINDS`; the request carries transcript chunks only
  (extends `test_dat18_egress.py`); the verifier drops an uncited statement; `kc_ids`, `skips` and `for_you` by code
  on the seeded fixture; `test_the_outline_request_carries_no_learner_block`.
- `test_w9_video_file.py`, `services/study-worker/tests/test_video_frames.py`: kind by suffix and the downgrade;
  containers without audio; frame times (chapters, scene changes, gap, cap); the privacy pass refusing a frame;
  OCR text; locators; `test_a_quiz_item_cites_a_frame_locator`; retention and inventory.
- `test_w9_companion_moment.py`: `open_moment` from a timed hit; `labelled_numbers` on "04:12"; the context fence
  under `strip_for_cloud` with and without `study_materials`; discarded after one turn; "what haven't I got yet" by
  code.
- UI: `study-link-add.test.tsx`, `study-player.test.tsx` (the link's Open-at buttons and external opener, `<video>` and the filmstrip for a
  file), `study-outline.test.tsx`, `study-citation.test.tsx` (frame label), `companion-thread.test.tsx`.
- Scenario `scenarios/w9/youtube_lecture.yaml` through the generalised loader.

### 20.10 Demo

Ada pastes a YouTube lecture on projectile motion and its transcript; Study shows its chapters and lines, each with
**Open at**. **What this video
teaches** lists four objectives with moments, two worked examples, six concepts tagged to physics skills, "assumes
you know: resolving vectors", "not covered here: air resistance", and for Ada: range secure, maximum height
learning, time of flight not started. She taps **Ask about this moment** on the 04:12 line: "why does the range
depend on sin 2θ?" Your tutor answers from those lines. "What does this video teach that I haven't got yet?" gets
"Time of flight and maximum height, at 06:40 and 08:15. Want five minutes on time of flight?"

### 20.11 What the review changed

| Finding | Answer |
|---|---|
| B1 null-service feature crashes policy | `service: null` branch (§20.3) |
| B2 incomplete registration | every site listed, DAT-18a row (§20.3) |
| B3 `study_frames` inventory; no image store | inventory and profile-store rows; no stored image, thumbnails drawn locally |
| B4 frames cannot be screened before leaving | the file leaves whole as today; the pass runs in the worker; no MDL-23 claim (JM-D34, §20.6) |
| B5 no image-reading path | frames are OCR text; no vision read in W9 (JM-D34) |
| B6 `study_search` cannot read an aid | "what haven't I got yet" by code fact set (§20.4) |
| B7 the "syllabus outline" is a learner file | the outline request carries transcript chunks only (JM-D33) |
| B8 moment fence without a cloud rule or a home | pending turn context, `strip_for_cloud`, schema and `resolve_action` named (§20.3, §20.4) |
| B9 transcript format, title, two-hour bound | both forms, headings, title asked, bound enforced (§20.3) |
| B10 CSP per setting, player script, origin | the spike ran: no embedded player in this release; Watch on YouTube at the moment; no CSP change, no feature (JM-D42, JM-D31, JM-D32, JM-D41) |
| B11 budget | $1.18 an hour reserved; frames ≈ $0 (§20.7) |
| Non-blocking 1–9, 17–23 | kind by suffix with downgrade; worker limits stated; frames on `SourceCreate`; the `SourceCreate` variant not a route; `StudyCitation.tsx`; `JobKind` and `GRANULAR_KINDS`; the `kc_tags` fixture and the skips rule; timestamps as labelled facts; locators in `toolsets.json`; the loader; tests per bullet; notice wording; the D64 sentence; `document` class |

## 21. The learner's map: a graph-first view of knowledge and mistakes (W10)

Status: **specified 2026-10-31, reworked the same day after review** (`SPEC_W9_W10_REVIEW.md`: four blocking
findings, all confirmed; §21.11 maps them). From the UpRabbit comparison (its "dynamic heatmap" of hypothesis,
validated and misconception nodes). Decisions in §21.2 are **proposed, owner to confirm**. Device-only, no model
call, no new consent, no new learner migration.

**W10 built 2026-10-31** (the owner approved the reviewer's answers to JM-D35 to JM-D39 and JM-D45 as working
assumptions). Every §21.8 bullet passes a named test: `test_w10_map_layers.py`, `test_w10_snapshot_as_of.py`,
`test_w10_overview.py`, `test_w10_kc_links.py`, `test_w10_scenarios.py` (`scenarios/w10/map_month_later.yaml`, suite
`learner_map`), the UI's `map-overview.test.tsx`, `concept-map-layers.test.tsx`, `concept-map-scrubber.test.tsx`,
`concept-map-sheet.test.tsx` and `companion-thread.test.tsx`, the renderer's `conceptmap-view.test.tsx` and the client
core's `learner-map.test.ts`. The engine is `engine/learner_map.py`; the replay is `snapshot_as_of` and `Snapshots` in
`learner/projections.py`; the hero is `progress/MapOverview.tsx`. A replay of 10,002 events took 0.41 s on the
development machine. Where the build departs from the text above, and why:

- **Contracts.** `contract-additions-w10.json` records the additions, applied to `contracts/` in the same change. The
  `ConceptNode` fields are optional properties, so a reply from a core before W10 (and the existing fixtures) still
  validates; a W10 core sends every one. Three pieces §21.3 does not list were needed: `ConceptMap.first_day` (the
  local date of the first learning event, since the scrubber starts there, §21.5, and the client cannot know it),
  `KcLinks.kc_id` (the reply names its skill), and `validation_failed` on the concept-map and links endpoints. The
  contract fixture corpus (`evals/contracts/`) was regenerated by `jana_tools fixtures --write` for the two new
  definitions.
- **States at now.** A skill with evidence takes its state from `kc_views` at now; a `kc_mastery` row with no
  attempts keeps its stored state. No fold writes such a row with any state but Not started, so for real learners
  this is `kc_views` exactly; hand-made test rows keep their meaning. The subject map (`/map`) reads the same states,
  though §21.4 lists only the skill map, so a tile's rule, the overview and the skill map agree (Progress already read
  `kc_views`).
- **Freshness buckets.** Today is the same local day; this week the six days before; this month up to 29 days back;
  longer ago beyond. `last_seen_at` also moves on a practised skill's neighbours through implied evidence (LRN-10);
  that counts as a touch, as the column says.
- **Since last time.** The `app_settings` value under `map_opened_at:<profile_id>` holds the time and the bands then
  (only bands above Not started), so no replay is needed to compare. A live read writes it; the first live read in a
  core's life takes the stored bands as its baseline for the visit, so the overview and the subject map opened from
  it compare against the same open. A literal compare-to-previous-read would clear the marks between the overview and
  the map. `new` means no band above Not started at the last open; `up` means the band rose. A dated map never marks or
  records. Deleting a profile removes the key.
- **The dated map.** `snapshot_as_of` takes the learner's own projections as an optional argument (the assessment
  build replaces the mastery projection). The cache is keyed by profile, date and the log's newest `seq`, so a late
  or synced event replays the date again; eight dates are held per profile. Questions come from the live transcript,
  asked by then; Study counts use the live Study tables filtered by time (due cards from each card's latest review by
  then); tracked topics are those whose `last_at` is by then; no mastery check is shown as waiting.
- **Study and notes links.** Materials are the aids a tagged Study activity names through its `ref` (an aid, a quiz
  attempt, a card review), plus aids and sources whose title `study_topics.kc_tags` tags at read time. Moments are the
  timed transcript chunks of a recording, or of §20's video files and video links, tagged the same way; frames are not
  tagged. `KcLinks` material kinds are Study's aid and source kinds together, widened for §20's `teaching_outline`,
  `video` and `video_link`.
  Notes count through the KCs of the events they cite only (not `notes.kc_ids`), active or awaiting review.
- **Mistakes.** `ConceptMap.mistakes` now carries disputed rows. That changed one assertion in `test_concept_map.py`
  ("a disputed one never"), as §21.3 requires, and the UI fixture was regenerated by its writer. A disputed
  misconception is ringed with "You said this isn't right". It is not counted in the Mastery layer's mistake badge or
  in the overview's watched mistakes, and its sheet line offers no root gap. Order: watched, disputed, resolved.
- **The hero.** The overview's layer switch offers Mastery, Freshness and Mistakes, the layers its tiles carry. A tap
  opens Learn's map mode on the chosen layer (one lens, in memory). The ideas that moved today are outlined at tile
  granularity, through the subject maps the app already holds.
- **Freshness looks.** Today uses the Secure look, this week Nearly secure, this month Learning, longer ago Coming back
  to this, not yet Not started, each with its tokens.json pattern drawn as an SVG pattern and its word on the box.
- **Sheet actions.** Make flashcards opens the first linked source in Study with the flashcard tool's dialog. The
  learner starts the job, so Study's own consent and budget rules apply. With only an aid linked it opens the aid. This
  needed two `StudyRequest` kinds (`source`, `flashcards`). Ask your tutor opens Study's thread with "About
  <statement>: " in the composer. The knows page opened from Learn returns to Learn (`knows-from-learn`).
- **Scenario loader.** `tests/scenario_cases.py` finds every week's cases and dispatches to `w8_scenarios.RUNNERS` and
  `w10_scenarios.RUNNERS`. `test_w8_scenarios.py` loads through it with the same cases and assertions. The W10 case's
  rubric was corrected once before it passed: its first draft said the map four weeks ago would be all Not started,
  which its own dates contradict, so it now checks the bands the model had then (§21.8's wording).
- **Not done.** No in-browser check: the browser pane could not open a local file, and the app needs a running core
  and profile. The map was checked through the component and renderer tests only.

**What exists.** Learn's subject map has a "Map" mode (UXS-22): one subject's curated skills as a layered graph,
foundations left, each skill right of what it builds on, with the learner's own layer: state and band per skill,
prerequisite edges, root-gap edges from diagnosed misconceptions with their gap path, the questions asked, "What
next" ranked by exam weight and unmet prerequisites, a sheet per skill, and a table for screen readers
(`packages/ui/src/learn/ConceptMap.tsx`, rendered by `packages/renderers/src/conceptmap/ConceptMapSvg.tsx`; data from
`GET /v1/curriculum/{subject_id}/concept-map`, `api/learn.py` line 74, built in `engine/learn.py`; contract
`ConceptMap` with `nodes`, `edges`, `next`, `questions`, `mistakes`; re-read on every mastery change, `App.tsx` line
215). The learner model holds what the layers need: `kc_mastery` (state, `last_seen_at` from closed opportunities,
`projections.py` line 305 and 409), `review_cards` (FSRS retrievability, `learner/model.py` line 77), `kc_views`
(state at now, including `needs_review`), `learner_misconceptions` (five statuses, `schema.sql` line 323), Study
activity with KC tags (§19.3.2, a non-evidence event the mastery fold skips, `projections.py` line 217), notes with
cited events, and the companion summary's topics (≤ 6). Progress's "What moved today" is `MovedToday` in
`packages/ui/src/progress/Progress.tsx` (line 66–90). What is missing: the map is three taps away behind Progress's
lists; it shows mastery but not freshness; mistakes are edges and a sheet; Study materials, notes and the thread are
not on it; one subject at a time; no way to see the map as it was a month ago, although the learner model is an
event log.

### 21.1 What the learner gets

| Part | What it is |
|---|---|
| **My map** first | Progress opens on an overview of every installed subject as topic tiles (TABLE UXS-22a's first matching rule per tile: fill, pattern, icon and word), then a tap into a subject's skill map (the existing one, with layers). "What moved today" stays first under the overview and outlines the moved skills on the map. The lists stay below. |
| Layers | Switches over the same drawing: **Mastery** (the bands and words as today), **Freshness** (practised today, this week, this month, longer ago, not yet; and **refresh due**: a secure skill whose review is due), **Mistakes** (each watched misconception as a ring on its skill with its status word: being watched, active, resolving, resolved, "you said this isn't right"), **Study** (a dot per material or aid tagged to the skill; cards reviewed at least once that are due; lecture moments), **Notes** (a pin where a tutor's note cites the skill), **Topics your tutor is tracking** (the summary's topics, at most six). Every layer has its words in the box label and the table, and a legend; never colour alone (DSN-04). |
| Since last time | Skills whose band rose or appeared since the map was last opened pulse once (respecting Reduce motion) and keep an outline: up or new. |
| The scrubber | "4 weeks ago → today": the map as the learner model stood on that date, replayed from the event log by code, read-only; weekly dates, at most 26 weeks. |
| The sheet | Today's sheet plus the Study materials and lecture moments on this skill, the tutor's notes about it (open the knows page), and three actions that exist elsewhere: **Make flashcards**, **Research this**, **Ask your tutor about this** (the thread opens with "About <skill statement>:" as a draft, nothing sent). |

No heat means blame (LRN-35): a skill with no evidence is "not yet", never a warning; the words are the learner's
own state words (G99).

### 21.2 Decisions (proposed, owner to confirm)

| # | Decision | Working assumption |
|---|---|---|
| JM-D35 | Does Progress become map-first? | **Yes**: the overview is the hero; `MovedToday` first under it; the lists, the Study activity line and the record below. Learn's own map mode stays. |
| JM-D36 | What may the heat encode? | **Bands, buckets and words, by code, never a probability** (LRN-36, G99). Freshness from the newest learning touch of a skill (opportunities **and** Study activity); refresh due from `kc_views` (`needs_review`, the FSRS card below the bar); mistakes from status; no `p_mastery` anywhere, in any of the three contracts. |
| JM-D37 | How is "as of a date" computed? | **Replay into memory, read-only:** the learner schema in a `:memory:` database, `events` with `occurred_at ≤ date` and the tables a fold reads (`profile`) copied in, `Projector(mem, params, content).rebuild()`; the map read from it. No new stored history. Budget evidence: the rebuild budget is 100,000 events in 10 s (`config/keys.py` line 720–721; `test_m6b_events.py` line 419–431), so 10,000 in 2 s. |
| JM-D38 | How are materials, moments and notes linked to skills? | `study_activity.kc_tags`, aid KC links (`engine/study_topics.py`), frame and transcript chunks tagged the same way at read time, notes through the KCs of the events they cite. Untagged items are not on the map. |
| JM-D39 | Does the map leave the device or reach a model? | **Never.** It is the knows view's data (LRN-36, MEM-14, UXS-28), read by the app; the cloud learner block is unchanged. |
| JM-D45 | Where is "last opened" kept? | In the device-local `app_settings` table (`schema.sql` line 803–807), key `map_opened_at:<profile_id>`: **not** a `Settings` key, which would append a synced `setting_change` learning event on every open (`store/settings.py` line 100–107) and pollute the log the scrubber replays. |

### 21.3 Contracts

`contract-additions-w10.json` first, then the contracts. No storage change.

- `contracts/api/commands.schema.json`: `ConceptNode` gains `freshness: "today" | "week" | "month" | "older" | "never"`,
  `refresh_due: boolean`, `changed_since: "up" | "new" | null`, `study: {materials, moments, cards_due}` (integers),
  `notes: integer`, `tracked: boolean` (a summary topic). `ConceptMap` gains `as_of: date | null`. `ConceptMistake.status`
  gains `"disputed"` (the engine drops disputed rows today; they return as "you said this isn't right").
- New `$defs/CurriculumOverview` (`GET /v1/curriculum/overview`): `{subjects: [{subject_id, subject, level, topics:
  [{topic_id, title, kcs, bands: {not_started, learning, secure}, rule (TABLE UXS-22a's first matching), freshness,
  refresh_due, mistakes, changed}]}]}`, from the subject map's data (`learn.ts` `MapTopic`, `MapKc`) plus freshness.
- `GET /v1/curriculum/{subject_id}/concept-map?as_of=YYYY-MM-DD`: the same `ConceptMap` from the replayed snapshot,
  `as_of` set, `changed_since` null, counts as of the date; a date over 26 weeks back or in the future is
  `validation_failed`.
- New `$defs/KcLinks` (`GET /v1/curriculum/kcs/{kc_id}/links`): `{materials: [{aid_id | source_id, kind, title}] ≤ 12,
  moments: [{source_id, at_ms, title}] ≤ 12, notes: [{note_id, text, confidence}] ≤ 6, tracked: boolean,
  misconceptions: ConceptMistake[]}`.
- "Ask your tutor about this" is a **client deep link** to the companion thread with a draft, no event and no
  contract change (`open_tutor` stays PED-01's hand-off to the guided tutor, §19.3.3).

### 21.4 Changes

| Where | Change |
|---|---|
| `agent_core/engine/learn.py` (the desk's `concept_map`) | Reads states from `kc_views` at now (today line 148–150 reads `kc_mastery.status`, so `refresh_due` and `state` agree); `freshness` as the newest of `kc_mastery.last_seen_at` and the newest `study_activity` event whose `kc_tags` holds the skill (a scan of `events WHERE type='study_activity'` within 26 weeks, JSON tags, no index), bucketed against the profile's local day; skills with no mastery row included as "never"; `changed_since` against `app_settings` `map_opened_at:<profile>`; `study`, `notes`, `tracked` per skill; `as_of` through `snapshot_as_of`; new `overview()` and `kc_links()`. |
| `agent_core/learner/projections.py` | `snapshot_as_of(conn, params, content, ts) -> sqlite3.Connection`: the generated learner schema in `:memory:` (`store/generated/schema.py`), `events` with `occurred_at ≤ ts` and `profile` copied, `Projector(mem, params, content).rebuild()` (line 1242–1265 folds `self.conn`, so the memory connection is its `conn`); cached per (profile, date) for the session; `table_checksum` (line 1147) of the live tables unchanged before and after. |
| `agent_core/api/learn.py` | `?as_of=` validated; `GET /v1/curriculum/overview`; `GET /v1/curriculum/kcs/{kc_id}/links`; `map_opened_at:<profile>` written to `app_settings` on an overview or map read without `as_of`. |
| `packages/client-core/src/concept-map.ts`, `learn.ts` | Layer, `asOf`, `links(kcId)`, the overview read; the layer and scrubber position kept in memory only. |
| `packages/renderers/src/conceptmap/ConceptMapSvg.tsx` | Layer paints on the existing boxes: Freshness as five steps using `tokens.json`'s `mastery` pattern tokens, one per bucket, with the word in the box label; refresh due as a dashed outline with "refresh due"; Mistakes as rings with the status word in the label and table; Study as dots with a count; Notes as a pin; `changed_since` as an outline that pulses once unless Reduce motion. A legend per layer; a table column per layer. |
| `packages/ui/src/learn/ConceptMap.tsx` | Layer switch (`SegmentedControl`), the scrubber (`<input type="range">` over weekly dates, the date read aloud, "Today"), the sheet's sections and the three actions (Make flashcards → a Study job on the skill's materials; Research this → the research conversation with the skill's statement; Ask your tutor → the deep link with the draft). |
| `packages/ui/src/progress/Progress.tsx`, new `progress/MapOverview.tsx` | The overview as the hero with UXS-22a tiles; `MovedToday` (line 66–90) first under it and outlining moved skills on the map; the rest unchanged. |
| `apps/desktop/src/App.tsx` | The deep link to the companion thread with a draft, routed like other screens (no event). |
| `packages/i18n/locales/en.json` | `map.layer.*`, `map.freshness.{today, week, month, older, never}`, `map.refresh_due`, `map.changed.{up, new}`, `map.scrubber.*`, `map.sheet.*`, `map.mistake.disputed`, `progress.map.title`. |

### 21.5 Behaviour

- **Freshness** is the newest learning touch: an attempt, hint or check (through `last_seen_at`) or a Study activity
  tagged to the skill: today, this week, this month, longer ago, not yet. **Refresh due** is `kc_views`'
  `needs_review`. Study `cards_due` counts cards reviewed at least once (an unreviewed card has no skill tag).
- **Since last time**: `map_opened_at:<profile>` in `app_settings` is written on a live overview or map read; a
  skill whose band rose or appeared since then is `up` or `new`; the first open marks nothing. ("Down" is dropped: a
  band falls only by correction or migration, and the word would blame.)
- **The scrubber** offers weekly dates from the profile's first learning event (≤ 26 weeks) to today; a date
  replays the model and redraws; counts are as of the date; the table says "as of 3 October 2026"; a replay of 10,000
  events completes within 2 s on TABLE MDL-16a's mid class and is cached per date for the session. Scrubbing writes
  nothing (`table_checksum` proves it).
- **Accessibility**: every layer's meaning is in each box's label and the table; the scrubber is a labelled range
  input; words never on hover only; pulses respect Reduce motion.

### 21.6 Privacy

Nothing leaves the device: the overview, the map, the links and the snapshots are read by the app from the learner
database and the device database; none enters a prompt. Material titles and note text are the knows view's data
(LRN-36, MEM-14, UXS-28). The cloud learner block is unchanged.

### 21.7 Budget

$0: code only. Replays are CPU on the device.

### 21.8 Done when

Progress opens on the overview with every installed subject and each tile's rule, bands and freshness equal the
subject map's; a tap opens the subject map with the chosen layer; Freshness shows the buckets from a seeded learner
including a skill touched only in Study; refresh due on a decayed card agrees with the state shown; the Mistakes
layer rings an active and a disputed misconception with their words in the table; a tagged Study material appears
as a dot and opens; a note citing a skill's events appears as a pin and opens the knows page; `changed_since` marks a
skill that moved since the previous open and nothing on the first open, and no learning event is written by opening
the map; the scrubber at four weeks ago shows the bands the model had then, `snapshot_as_of(now)` equals the live
tables, and the live tables' checksums are unchanged; `as_of` beyond 26 weeks is refused; "Ask your tutor about
this" opens the thread with the draft and nothing sent; no probability appears in `ConceptMap`, `CurriculumOverview`
or `KcLinks`; every gate green.

### 21.9 Tests

- `test_w10_map_layers.py`: freshness from opportunities and from Study activity alone; `refresh_due` equals
  `needs_review`; `changed_since` from `app_settings` with no event written; `disputed` returned; counts per skill;
  `test_no_probability_in_any_map_contract` over all three.
- `test_w10_snapshot_as_of.py`: a dated event log replays to the bands the projections had then; `snapshot_as_of(now)`
  equals the live tables; checksums unchanged; the 26-week bound; the cache; 10,000 events within the budget.
- `test_w10_overview.py`: tile rules, bands and freshness equal the subject map's.
- `test_w10_kc_links.py`: materials, moments, notes, tracked, bounded, device-only.
- UI: `map-overview.test.tsx`, `concept-map-layers.test.tsx` (legend, table columns, words in labels, reduce
  motion), `concept-map-scrubber.test.tsx`, `concept-map-sheet.test.tsx` (a material opens, a note pin opens the
  knows page), `companion-thread.test.tsx` (the deep link's draft, nothing sent).
- Scenario `scenarios/w10/map_month_later.yaml` through the generalised loader.

### 21.10 Demo

Ada opens Progress: three subjects, physics the largest; "Motion" is mostly learning, one skill refresh due, one
ring. She taps physics: the two skills her projectile quiz touched are outlined "since last time"; Freshness shows
motion touched today and waves not yet; Mistakes rings "range vs maximum height" as being watched. She drags the
scrubber to four weeks ago: everything not yet. Back to today, the refresh-due skill's sheet shows the lecture moment
at 04:12, two cards due, the tutor's note, and **Ask your tutor about this**.

### 21.11 What the review changed

| Finding | Answer |
|---|---|
| B12 `map_opened_at` as a setting writes learning events | `app_settings`, device-local (JM-D45) |
| B13 `open_tutor` is the guided-tutor hand-off | client deep link with a draft, no event (§21.3) |
| B14 freshness misses Study activity and skills without a mastery row | computed in `engine/learn.py` over both sources (§21.4) |
| B15 `snapshot_as_of` needs a schema and copies | the `:memory:` schema, event and `profile` copies, `rebuild()`, checksum proofs (JM-D37) |
| Non-blocking 10–16, 19 | `disputed`; "down" dropped; "topics your tutor is tracking"; cards reviewed at least once; states from `kc_views`; UXS-22a tiles; no hover-only words; a test per bullet |
