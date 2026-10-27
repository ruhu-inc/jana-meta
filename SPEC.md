# jana-meta — specification for moving the fork onto Meta models

Status: **approved to build** (owner, 2026-10-26). This replaces the spec-only version of 2026-10-20 (kept in commit
7cf6c6e and in `../jana-meta-spec-backup`). The codebase is a history-free copy of jana-nebius at c4354de. This spec
says what changes, in which files, and what "done" means. It changes nothing in Jana's product (`../jana`).

Sources: the research brief `../jana-hackathon-research/meta-hackathon-brief.md` (models, prices, limits as of
2026-10-20), the event page and Official Rules (read 2026-10-25), and a file-level map of this repository.
Every Meta API detail marked **(verify)** must be confirmed with a real key on day 1 before code depends on it. On
2026-10-26 the Meta docs (dev.meta.ai/docs) confirmed or corrected most of them; §16 records what they say, and items
still marked (verify) are not documented and need a real call.

## Status (updated 2026-10-26, evening)

Work landed on `main` today, from this session and from parallel sessions merged at 17:33–17:41:

| W | State | Remaining |
|---|---|---|
| W1 Muse Spark | **Done**: Meta adapter, Nebius and Tavily removed, live typed maths and physics turns, latency halved (12.8–15 s), effort per alias, schemas self-contained, input guard on Spark, budget holds released for unbilled refusals | Dropped-stream accounting (§4.3), health probes spending credit, the Google stack still registered (§8.1), turn latency (§12: speculative Solver done, ~4 s off a new question) |
| W2 Vision | **Done**: SAM 3.1 at `/v1/vision/segment`, photos of working read in the cloud, outlines while the student confirms, `photo_region` pointing on the photo, photographed sketches checked, base64 false positive fixed (parallel session); the diagram drill (§5.2, 2026-10-26) | Read time of a diagram (~15–20 s) |
| W3 Glimmer | **Built 2026-10-27** (§7): launcher with projector and DFlash, router and recommendations entries, reasoning strength per request, lean offline turns, authored hints offline, power-cut fallback in seconds and return to the cloud; practice and mock papers measured offline | A typed question's first words in ≤ 8 s (now 30–48 s on a loaded machine; needs the owner's call on streaming before the gates, §7); the Wi-Fi-off run on the demo laptop |
| W4 Speech | **Online done**: Muse Voice Transcribe in the gateway (paced, silence between turns, budgeted, per-turn re-checks; branch `claude/bold-bardeen-60a405`), Kokoro served by the gateway (Magpie development only), a 600 ms end-of-speech hold, subject-first keywords, the voice bar in the tutor (JM-D20), a spoken checked turn in the browser host (§12) | The engine turn (the 4 s target), the browser's filler at 2.6 s, offline (§6.3), self-hosted Magpie (§15 item 3), spoken unit names |
| W5 Adult | Sign-up with date of birth, adult copy, parent sections removed, safety wording | Engine-side band check, remaining guardian copy (§17) |
| W6 Bugs | #1, #4, #6 done; #5 partly (parallel session) | #2, #3, #7 |
| W7 Research agent | **Built 2026-10-27, end-to-end check next**: the conversation and plan on the device (§18.1a), the gateway job (search, safe fetch, checkpoints, source steering; 4 questions → 16 s, 22 pages, $0.04), import into Study as one cited material with Study's verified parts, the Study UI and "Make a study pack" from the diagram drill | A full pack from the browser, timed; the podcast read by Kokoro on the device |
| Standout features (parallel session) | Checked figures, gap tracing, explain-back, predict-before-you-see sims merged | — |
| Glimmer-free check | `phys_circuit`'s recursive schema unrolled for Spark (§16) | — |

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
| JM-D12 | **Speech to text is Meta.** Online: Muse Voice Transcribe (realtime). Offline: Meta **Omnilingual ASR** (Apache-2.0) if it passes the latency gate in §6.3; otherwise faster-whisper stays as the offline fallback. English only (JM-D18). |
| JM-D13 | **Text to speech is not Meta**, because Meta has no commercially usable TTS (MMS-TTS is CC-BY-NC and not streaming). Online: **NVIDIA Magpie TTS** (self-hosted open weights for anything judges see; §6.4). Offline, and for every podcast (study packs, §18): **Kokoro-82M** (Apache-2.0, already in the speech pack), read on the device. |
| JM-D14 | **Removed:** Nebius Token Factory, all Nemotron models, Tavily web search, and the Google/Gemini cloud stack (Gemini models, Gemini Live, Chirp STT/TTS) from configuration and from the submission. |
| JM-D15 | **Adult product:** every profile is `18_plus`; guardian consent, parent summaries, family plan and under-18 Ask policies are hidden or removed. Sign-up asks for date of birth and blocks under-18s. |
| JM-D16 | **Muse Spark Standard mode only**, never Contributor mode (Meta trains on Contributor data). Contributor mode is a separate model id (`muse-spark-1.3-contributor`), so the gateway configures only Standard ids. Zero data retention for the project account is requested only if the owner chooses it over the research agent (§15 item 2): it disables search grounding, background and stored requests, and file uploads. Muse Code, if used, must not run in Contributor mode on this repository: **Muse Code subscriptions default to Contributor mode**, so run it with `--contributor-mode off` or `MUSE_CONTRIBUTOR_MODE=0`. |
| JM-D17 | **Submission scope:** the organisers receive a perpetual licence to whatever is submitted (Official Rules, "Hackathon Submission"). Only what the entry needs is submitted (§9). The owner signs off on the scope before submission. |
| JM-D18 | **English only** (owner, 2026-10-26). No Yoruba, Hausa, Igbo or Pidgin input in the entry; Voice Transcribe does not support the first three anyway. |
| JM-D19 | **Meta-native presentation** (owner, 2026-10-26). The code, configuration names, interface copy and documentation read as a project built for Meta's models from the start: no Nebius, Nemotron, Tavily or earlier-hackathon framing remains (for example the keychain service is `jana-meta.cloud-gateway`, and the README is about Meta). |
| JM-D20 | **Voice conversation in the tutor** (owner, 2026-10-27; replaces D130 on the tutor screen for this entry). With Cloud voice switched on, the tutor screen offers the voice bar ("Start a conversation", push to talk, hands-free): every spoken question is a full tutor turn, with the filler at 1.5 s and the accepted spoken form read sentence by sentence by Kokoro; every spoken word still comes from an accepted engine turn (JM-D6). Without Cloud voice the tutor keeps dictation and read-aloud only; Ask anything and Study keep their own conversations. |

## 3. Architecture

```
 Learner (browser demo host or desktop app)
   mic ─► voice bridge (barge-in is a server `flush`) ┐        photo ─► perception worker (local, sandboxed):
   speaker ◄──────────────────────────────────┐       │        orientation, face/person screen, crop, deskew,
                                              │       ▼        privacy mask, ≤1600 px JPEG
 ┌──────────── cloud gateway (jana-meta) ─────┴──────────────────┐        │
 │ voice WS: Muse Voice Transcribe (STT) ─► transcript ──────────┼──► Jana engine (agent-core, on device)
 │           Magpie or Kokoro ◄── accepted say_spoken only ◄─────┼─── input guard → Diagnoser → Solver + tools
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
| `cloud_gateway/custody.py`, `secret_scan.py` | `META_API_KEY` environment secret (Meta's docs call it `MODEL_API_KEY`; ours is a gateway-only name) and keychain account `meta_api_key` under service `jana-meta.cloud-gateway`; remove the Nebius and Tavily sources; add a Meta key pattern (keys look like `LLM_<digits>_<secret>`; the secret's alphabet is **(verify)**). The `tvly-` pattern stays in the scanner (done 2026-10-26): an old Tavily key may still be on the machine, and catching it costs nothing. |
| `services/agent-core/agent_core/router/cloud_models.json` | Two aliases with Spark's context (1M advertised; cap the engine at 131072 to bound cost), max output 16384 (reasoning tokens share the budget), `vision: true`, prices. |
| `agent_core/router/router.yaml` | Comments and tier lists name Spark; `cloud.send_photos: true` (still gated by the photo notice, §5). |
| `cloud_gateway/study.py` | Remove the Nebius branches (~507, ~542, `structured_math = provider == "nebius"` ~1048, malformed-verifier retry ~1643); use the generic path. |
| `scripts/jana_tools/hackathon_app.py` | Expect `slots.primary == "meta"`; `GatewayHop` forwards the device's request unchanged (adding provider fields there broke the gateway's device contract); env vars `JANA_META_*`. Done. |
| `apps/desktop/dev/sidecar.ts`, `scripts/jana_tools/hackathon_dev.py` | Same renames; default data dir `jana-meta-browser` in the system temporary folder; provider keys scrubbed from child processes. Done. |
| `services/cloud-gateway/deploy/meta-dev.toml` (rename of `nebius-dev.toml`) | Meta slot; $10 a day, $120 in total, valid until 2026-11-09 (judging); ledger in `~/.jana-meta/gateway`, outside `/tmp`; `[tavily]` removed. Done. |

### 4.3 Budget fixes that matter with $150 of credit

From the 2026-10-25 review; both protect the credit (images: done; dropped streams: open):
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
| `cloud_gateway/voice.py`, `config.py` | Build `SpeechStack(MetaRecognizer, live=None, <synthesizer>)`; replace `config.voice_google` with `config.voice_meta`; `voice_enabled=true` in the dev config. With `live=None` the TTS-only reader path is used (it already exists as the drift fallback). Done: the synthesizer is Kokoro by default (§6.4), `MagpieSynthesizer` with `voice_meta.tts = "magpie"` in dev only. |
| `cloud_gateway/voice.py` (~1054–1067) | Re-check quota and credential every turn (review finding: sessions currently run past caps). Done (branch `claude/bold-bardeen-60a405`): credential, operations and quotas before each turn. |

### 6.2 Online text to speech: NVIDIA Magpie

`cloud_gateway/podcast_speech.py` already calls Magpie (NVCF HTTP, LINEAR_PCM 22.05 kHz). Generalise it into a
`MagpieSynthesizer` implementing `Synthesizer`: one request per accepted sentence, resample 22.05 → 24 kHz for the
bridge, voice `Magpie-Multilingual.EN-US.Aria.Calm` (Neutral as fallback). Podcasts move to Kokoro on the device
(§18): the trial's audio cannot be shown, and Kokoro plays offline.

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
- The NVIDIA API-catalog trial forbids distributing generated audio. **Anything judges hear (live demo, video) uses
  self-hosted Magpie open weights** (`nvidia/magpie_tts_multilingual_357m`, NVIDIA Open Model License) on a Modal or
  Baseten GPU from the partner credits, unless NVIDIA confirms trial use is fine. Development may use the trial.
  If self-hosting is not ready by Nov 2, the demo uses Kokoro served from the gateway (Apache-2.0).

**Done when:** a spoken physics question gets a spoken, checked answer online in ≤ 4 s typical from end of speech
(filler at 1.5 s), barge-in stops playback, and the same works offline after the network is pulled.

## 7. Local inference: Muse Glimmer 30B (JM-D11)

| File | Change |
|---|---|
| `agent_core/router/recommended_models.json` | Replace the Qwen/Gemma entries with `muse-glimmer-30b` (dense 30B; GGUF `meta-models/Muse-Glimmer-30B-GGUF`, file `Muse-Glimmer-30B-KQuant-17GB-Q4_K_M.gguf`, 16.8 GB), class `high` only (32 GB+), `context_for_agents` 16384 (native 131,072), `max_output` at least 8192 (long reasoning can use up 4096 and return empty content with `finish_reason: "length"`), `thinking.available: true`, `default: on` (reasoning cannot be turned off), sampling temperature 1.0, top_p 0.95, top_k 64. One tool call per turn (no parallel calls). |
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
| Google/Gemini cloud stack | `providers/gemini.py`, `vertex.py`, `gemini_live.py`, `google_speech.py` out of configuration (deleted before submission if time allows); `config.voice_google` |

**Ask anything after Tavily:** out of the demo (§14). Without a search backend `/v1/ask` returns "unavailable"; web
research lives in the research agent (§18). **Study:** file and paste import stay; web-page import is removed (done).
Tavily removal: done. Google stack: still registered as adapters (not configured); delete before submission.

### 8.2 Adult product

| Area | Change |
|---|---|
| Sign-up | Date of birth field; under 18 → blocked with a short explanation. Store `age_band = "18_plus"` (`store/profiles.py` `ADULT_BAND`). Done in the app; the engine-side check is still open (§17 W5). |
| Ask policy | `engine/ask_anything.py` `policy_for()` and `cloud_gateway/ask.py` audience: adult only; the `under_18` branch is removed from the UI. |
| Consent | Keep per-feature consent (the learner's own consent now). Remove guardian flows: `store/subscription.py` guardian consent, `plans.toml` `jana_family`, UI `ParentSummary.tsx`, `FamilyControls.tsx`, guardian parts of `OnlineFeatures.tsx`, `Studies.tsx`, `StudyWorkspace.tsx`; `engine/parents.py` not wired. |
| Copy | Rewrite `parents.*`, `settings.study.needs_guardian`, `study.access.guardian`, `error.guardian_consent_required` and related keys for an adult managing their own settings; the study banner "A parent or guardian needs to approve" becomes the learner's own consent prompt. |
| Safety | Keep the input guard, distress templates and all release gates. "Trusted adult" wording in `study.safety.tpl.*` becomes adult-appropriate support wording. |

### 8.3 Credit budget

$150 of Meta credit for 10 days. Dev config: $10/day cap and $120 total, leaving $30 for judging. Output tokens
dominate (reasoning is billed as output), so Coach `reasoning_effort` stays low and `max_tokens` is clamped per role.
SAM: ≤ 300 images over the event (~$0.75).

## 9. Submission scope (JM-D17, owner signs off)

The Official Rules grant the organisers a perpetual, irrevocable, royalty-free licence to the Submission. Submit only:

- the engine (`services/agent-core`, `services/tool-worker`, `services/perception-worker`), the cloud gateway (with
  the research agent, §18), the desktop app and shared packages, and `services/study-worker` (Study stays: study packs
  are saved into it);
- **Mathematics and Physics** content packs (proposal); **Chemistry** only if the demo shows a chemistry moment (owner
  decision); Accounting stays out;
- not: Studio and authoring tools (`apps/studio`, `services/pack-builder`), `services/signing-service`,
  `services/ingest`, private specs, evals with licensed material, and the files listed in §17 (§9 does not install).

The submission repository is built from this one at the end with only the parts above (same `git archive` method,
no history). Licence: Apache-2.0 for code; content packs under the owner's licence (`LicenseRef-Own`).

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

- Gateway: `test_nebius.py` → `test_meta.py`; `test_m19_gw_conformance.py`, `test_m19_gw_gemini.py`,
  `test_m19_gw_keys.py`, `test_inference_budget.py` (images allowed), `test_m42_study.py`,
  `test_study_math_format.py`, `test_podcast_speech.py`, `gateway_stubs.py`; remove `test_tavily.py`. New:
  `test_meta_speech.py` (Recognizer against a fake socket), `test_sam.py` (segment route, budget).
- Agent core: remove `test_study_web.py`; update `test_a1_input_routes.py`, `test_study_podcast_speech.py`; new tests
  for `photo_region` pointing and the Glimmer model entry.
- Scripts: `test_hackathon_app.py`, `test_m42_release_preparation.py`.
- TypeScript: `client-core` `ask-anything.test.ts`, `study-workspace.test.ts`; `ui` `ask-anything.test.tsx`,
  `study-workspace.test.tsx`; `i18n` catalogue checks; `apps/desktop/test/podcast-audio.test.ts`.

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
| Magpie first audio after an accepted sentence | ≤ 0.4 s |
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
  runs and the browser turns; the ledger rose about $1.20 meanwhile, parallel sessions included). Kokoro and the Magpie trial cost nothing.

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

## 13. Workstreams and plan

Workstreams that separate sessions can take (W1 first; W2–W4 after its adapter lands; W5 and W6 any time):

| W | Scope | Sections |
|---|---|---|
| W1 | Meta provider, routing, budget, removal of Nebius and Tavily | 4, 8.1, 8.3 |
| W2 | Vision: SAM route, PhotoReader, photo pointing | 5 |
| W3 | Local: Glimmer entry, launcher, offline switch | 7 |
| W4 | Speech: Voice Transcribe, Magpie synthesizer, Omnilingual gate | 6 |
| W5 | Adult product and copy | 8.2 |
| W6 | Demo bugs | 10 |
| W7 | Research agent: a long-running agent that builds study packs (Learn from a picture, Research a topic) | 18 |

| Day | Work |
|---|---|
| Oct 26 | Done: W1 (Spark live, latency halved), W5 sign-up and copy, W6 #1/#4/#6, input guard on Spark, Glimmer downloaded and measured |
| Oct 27 | Turn latency (§12): speculative Solver done Oct 26; the input guard and the Solver's two calls next; diagram drill done Oct 26 (§5.2) |
| Oct 28 – Nov 1 | W7 research agent (§18): Responses client and fakes, the gateway job, synthesis and verification, device import and UI, Kokoro podcast |
| Oct 31 – Nov 1 | W4 voice online (reduced: Voice Transcribe in, Magpie or Kokoro out); W3 lean offline path (pack hints instant, Glimmer for free-form questions) |
| Nov 2–3 | Polish, safety checks, eval run, record the video; owner signs off the §9 scope |
| Nov 4 | Build the submission repo (§9) and submit by 9:00 PM ET |
(Re-planned 2026-10-26 with the owner: W2, then W7, ahead of voice and the offline model; W2 then landed from a
parallel session the same day, so only its diagram drill remains.)

## 14. Demo (about 3 minutes)

The organisers' "skip these overdone projects" list (kickoff, 2026-10-26) names "AI for Education" chatbots, basic
RAG apps, simple image analyzers and dashboards. The demo therefore opens with what no chatbot does, shows the checks,
and keeps Study's summaries, Ask anything and the Progress pages out of it. Pitch: an exam-prep system for adults that
checks every step with code, keeps working without power or internet, and uses Meta's models to see, hear and reason.

1. An adult candidate signs up (date of birth, 18+) and photographs three lines of their own handwritten working.
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

## 15. Open items for the owner

1. Official Rules (read 2026-10-26 on the event waiver page): nothing bars existing work. A Submission must be the
   entrant's or its organisation's "original work product", solely owned, and may include open source it builds on.
   The Submission licence to the organisers is perpetual but **non-exclusive** (ownership stays). A separate clause
   gives the organisers a perpetual licence to any "Materials" shared or used "in connection with the event", which is
   wider than §9 assumes: take a legal view before showing private Jana work in workshops, Discord or office hours.
   The Startup track's Representative must be an active employee of the startup.
2. Meta API key (done 2026-10-26) and credit claim. Zero data retention or research: Meta's zero data retention turns
   off search grounding, background and stored requests, which the research agent (§18) needs. Decide one.
3. NVIDIA: is trial audio allowed in the video? If not, approve the self-hosted Magpie spend (Modal/Baseten credits).
4. Submission scope in §9 (which subjects; whether Study stays). §9 as written does not install (§17).
5. Hosting: GCP project `jana-meta` (JM-D7) or partner credits only.
6. Photo demo (§5): handwritten working goes to the cloud after the local privacy pass and the per-photo notice
   (owner, 2026-10-26: accepted).
7. Demo laptop: its specification, to set Glimmer's speed gate; and whether `--local-model` may download weights.
8. Ask anything: leave it out of the demo (anti-project list, §14); the research agent (§18) is the web-research feature.
9. Budget dates: resolved (valid until 2026-11-09; ledger in `~/.jana-meta/gateway`).
10. Research agent decisions: settled (§18.10).
11. Before submission: rewrite the README as a Meta project (JM-D19), rename the app identifier and keychain prefix
    (§17 Identity), and a trial `git archive` install and test of the §9 scope by Nov 1.

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
- **W5 (done in part 2026-10-26)**: `client-core/src/setup.ts` made every profile `13_15`. The app now asks for a date
  of birth on every create form, checks it on the device without storing or sending it, and creates `18_plus` only.
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
  project ids and an email address).
- **Identity**: the desktop app shares Jana's identifier `app.jana.desktop` and keychain prefix `jana.`; rename both
  (JM-D7, JM-D19).
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
