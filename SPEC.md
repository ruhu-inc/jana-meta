# jana-meta — specification for moving the fork onto Meta models

Status: **approved to build** (owner, 2026-10-26). This replaces the spec-only version of 2026-10-20 (kept in commit
7cf6c6e and in `../jana-meta-spec-backup`). The codebase is a history-free copy of jana-nebius at c4354de. This spec
says what changes, in which files, and what "done" means. It changes nothing in Jana's product (`../jana`).

Sources: the research brief `../jana-hackathon-research/meta-hackathon-brief.md` (models, prices, limits as of
2026-10-20), the event page and Official Rules (read 2026-10-25), and a file-level map of this repository.
Every Meta API detail marked **(verify)** must be confirmed with a real key on day 1 before code depends on it. On
2026-10-26 the Meta docs (dev.meta.ai/docs) confirmed or corrected most of them; §16 records what they say, and items
still marked (verify) are not documented and need a real call.

## 1. What we are building

**Jana for adult learners, on Meta.** A voice-first AI tutor for learners **aged 18 and over** preparing for O level
exams (WAEC/NECO private candidates, JAMB re-takers, adult-education students, first-year university revision). It
keeps Jana's teaching rules: it never just hands over an answer, every number is checked by tools before it is said,
and anything it could not check is labelled.

Event: Meta Global AI Developer Hackathon, remote, **Oct 26 12:00 PM – Nov 4 9:00 PM ET**, Startup track, theme
"Build for Your World". Judging: Impact 30%, Use of Meta AI tooling 25% (beyond a basic integration), Technical
depth 20%, Demo 25% (works live, holds up, video quality).

## 2. Decisions

Kept from 2026-10-20: JM-D1 (18+ only), JM-D6 (cascaded voice; every spoken word comes from an accepted engine
turn), JM-D7 (separate hosting project), JM-D8 (nothing with a non-commercial licence goes back into Jana).
JM-D1 rests on the Meta Model API Terms of Service (dev.meta.ai/legal/terms-of-service, checked 2026-10-26): "You and
your End Users must be at least 18 years of age to use the Services and Integrated Products, and you will not create
Integrated Products targeted at individuals under the age of 18." A parent signing in for a child, or a shared
parent-and-child account, does not change who the end user is, so it is out of scope for this entry (owner asked,
2026-10-26). Under-18 learners stay on Jana's own stack.

| # | Decision |
|---|---|
| JM-D9 | **Online reasoning is Muse Spark** for every engine role (Coach, Diagnoser, Solver, Checker, Reflector, auxiliary roles) and for Study and Ask generation. No other cloud language model is configured. |
| JM-D10 | **Online vision is Muse Spark + SAM 3.1.** Muse Spark reads the photo (what the question is, which regions matter); SAM 3.1 turns those regions into exact masks so Jana can crop for a second, sharper read and point at the exact place on the learner's own photo. |
| JM-D11 | **Local inference is Muse Glimmer 30B** (Apache-2.0, official GGUF Q4_K_M, ~16.8 GB) under the existing llama-server supervisor, on 32 GB+ machines. Smaller machines run online only. No non-Meta local language model ships in the entry (offline speech models are covered by JM-D12 and JM-D13). |
| JM-D12 | **Speech to text is Meta.** Online: Muse Voice Transcribe (realtime). Offline: Meta **Omnilingual ASR** (Apache-2.0) if it passes the latency gate in §6.3; otherwise faster-whisper stays as the offline fallback. English only (JM-D18). |
| JM-D13 | **Text to speech is not Meta**, because Meta has no commercially usable TTS (MMS-TTS is CC-BY-NC and not streaming). Online: **NVIDIA Magpie TTS** (self-hosted open weights for anything judges see; §6.4). Offline: **Kokoro-82M** (Apache-2.0, already in the speech pack). |
| JM-D14 | **Removed:** Nebius Token Factory, all Nemotron models, Tavily web search, and the Google/Gemini cloud stack (Gemini models, Gemini Live, Chirp STT/TTS) from configuration and from the submission. |
| JM-D15 | **Adult product:** every profile is `18_plus`; guardian consent, parent summaries, family plan and under-18 Ask policies are hidden or removed. Sign-up asks for date of birth and blocks under-18s. |
| JM-D16 | **Muse Spark Standard mode only**, never Contributor mode (Meta trains on Contributor data). Contributor mode is a separate model id (`muse-spark-1.3-contributor`), so the gateway configures only Standard ids. Request zero data retention for the project account (through Meta's contact-sales form; it disables search grounding and file uploads). Muse Code, if used, must not run in Contributor mode on this repository: **Muse Code subscriptions default to Contributor mode**, so run it with `--contributor-mode off` or `MUSE_CONTRIBUTOR_MODE=0`. |
| JM-D17 | **Submission scope:** the organisers receive a perpetual licence to whatever is submitted (Official Rules, "Hackathon Submission"). Only what the entry needs is submitted (§9). The owner signs off on the scope before submission. |
| JM-D18 | **English only** (owner, 2026-10-26). No Yoruba, Hausa, Igbo or Pidgin input in the entry; Voice Transcribe does not support the first three anyway. |
| JM-D19 | **Meta-native presentation** (owner, 2026-10-26). The code, configuration names, interface copy and documentation read as a project built for Meta's models from the start: no Nebius, Nemotron, Tavily or earlier-hackathon framing remains (for example the keychain service is `jana-meta.cloud-gateway`, and the README is about Meta). |

## 3. Architecture

```
 Learner (browser demo host or desktop app)
   mic ─► client VAD (barge-in) ─────────────┐                 photo ─► perception worker (local, sandboxed):
   speaker ◄─────────────────────────────┐   │                 orientation, face/person screen, crop, deskew,
                                         │   ▼                 privacy mask, ≤1600 px JPEG
 ┌──────────── cloud gateway (jana-meta) ┴──────────────────────┐        │
 │ voice WS: Muse Voice Transcribe (STT) ─► transcript ─────────┼──► Jana engine (agent-core, on device)
 │           NVIDIA Magpie TTS ◄── accepted say_spoken only ◄───┼─── input guard → Diagnoser → Solver + tools
 │ chat:     Muse Spark (api.meta.ai/v1) ◄──────────────────────┼─── → Checker → Coach → release gates
 │ vision:   Muse Spark (read) ⇄ SAM 3.1 (masks) ◄──────────────┼─── PhotoReader (engine/vision.py)
 │ budget ledger (credits cap) · secrets · no payload logging   │
 └──────────────────────────────────────────────────────────────┘
 Offline (32 GB+): llama-server + Muse Glimmer 30B · Omnilingual ASR or faster-whisper · Kokoro · same engine
```

The engine, tools, gates and voice bridge do not change design. Only providers, configuration, speech stages and
the vision step change.

## 4. Online reasoning: Muse Spark (JM-D9)

### 4.1 Model and routing

| Alias (device sends `primary/<alias>`) | Model | Used by | Reasoning |
|---|---|---|---|
| `fast-model` | `muse-spark-1.3` (confirmed; Meta recommends it for new work; 1.2 has the same price and limits, so pick by §4.4) | coach, diagnoser, title, input_guard, ask | low |
| `strong-model` | same model id | solver, checker, reflector, study | solver high, checker medium |
| `small-model` | removed | — | — |

One model serves both aliases; the aliases stay so the router's tiers and `router.yaml` keep working. Muse Wonder is
not used (preview, about 5× the output price).

### 4.2 Changes

| File | Change |
|---|---|
| `services/cloud-gateway/cloud_gateway/providers/meta.py` (new) | `MetaAdapter(OpenAICompatAdapter)`: base `https://api.meta.ai/v1`, Bearer `meta_api_key`. `prepare_body` (a module function, as `nebius.py` had, called from `_body`): `tool_choice` `"required"` → `"auto"` (Spark accepts only `auto`; anything else is a 400; the engine's existing tool nudge stays), a named-function `tool_choice` → `"auto"`, `"none"` → send no `tools` and no `tool_choice` (whether earlier tool calls in the history are accepted then is **(verify)**); keep `response_format: json_schema` as is (constrained decoding; strict schemas need `additionalProperties:false`, every property required, no `allOf`/`oneOf`, no root `anyOf`); drop `chat_template_kwargs`, `stop`, `logprobs`, `n` and other fields Spark rejects (§16); map `reasoning_effort` none → `minimal` (Spark always reasons; `none` is a 400). Usage: `completion_tokens` already includes reasoning tokens, so bill `completion_tokens` only (adding `reasoning_tokens` would double-count). Streams: drop any reasoning delta before it reaches the device. |
| `cloud_gateway/providers/__init__.py`, `config.py` (`AdapterKind`) | Register `meta`; remove `nebius`. |
| `cloud_gateway/defaults.toml` | `[slots] primary="meta"`; `[providers.meta]` with the aliases above; prices $1.25 input / $0.15 cached / $4.25 output per 1M tokens (confirmed for 1.3, 1.2 and 1.1). |
| `cloud_gateway/custody.py`, `secret_scan.py` | `META_API_KEY` environment secret (Meta's docs call it `MODEL_API_KEY`; ours is a gateway-only name) and keychain account `meta_api_key` under service `jana-meta.cloud-gateway`; remove the Nebius and Tavily sources; add a Meta key pattern (keys look like `LLM_<digits>_<secret>`; the secret's alphabet is **(verify)**). The `tvly-` pattern stays in the scanner (done 2026-10-26): an old Tavily key may still be on the machine, and catching it costs nothing. |
| `services/agent-core/agent_core/router/cloud_models.json` | Two aliases with Spark's context (1M advertised; cap the engine at 131072 to bound cost), max output 16384 (reasoning tokens share the budget), `vision: true`, prices. |
| `agent_core/router/router.yaml` | Comments and tier lists name Spark; `cloud.send_photos: true` (still gated by the photo notice, §5). |
| `cloud_gateway/study.py` | Remove the Nebius branches (~507, ~542, `structured_math = provider == "nebius"` ~1048, malformed-verifier retry ~1643); use the generic path. |
| `scripts/jana_tools/hackathon_app.py` | Expect `slots.primary == "meta"`; use `meta.prepare_body` in `GatewayHop`; rename env vars `JANA_NEBIUS_*` → `JANA_META_*`. |
| `apps/desktop/dev/sidecar.ts`, `scripts/jana_tools/hackathon_dev.py` | Same renames; default data dir `/tmp/jana-meta-browser`. |
| `services/cloud-gateway/deploy/meta-dev.toml` (rename of `nebius-dev.toml`) | Meta slot; quotas sized to the $150 credit (§8.3); `[tavily]` removed. |

### 4.3 Budget fixes that matter with $150 of credit

From the 2026-10-25 review; both protect the credit:
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

**Done when:** `test_m19_gw_conformance.py` runs with the `meta` provider, and a typed maths and a typed physics
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
| `cloud_gateway/providers/meta_speech.py` (new) | `MetaRecognizer` / `MetaRecognition` implementing `Recognizer` and `Recognition` from `providers/speech.py`. |
| `cloud_gateway/voice.py`, `config.py` | Build `SpeechStack(MetaRecognizer, live=None, MagpieSynthesizer)`; replace `config.voice_google` with `config.voice_meta`; `voice_enabled=true` in the dev config. With `live=None` the TTS-only reader path is used (it already exists as the drift fallback). |
| `cloud_gateway/voice.py` (~1054–1067) | Re-check quota and credential every turn (review finding: sessions currently run past caps). |

### 6.2 Online text to speech: NVIDIA Magpie

`cloud_gateway/podcast_speech.py` already calls Magpie (NVCF HTTP, LINEAR_PCM 22.05 kHz). Generalise it into a
`MagpieSynthesizer` implementing `Synthesizer`: one request per accepted sentence, resample 22.05 → 24 kHz for the
bridge, voice `Magpie-Multilingual.EN-US.Aria.Calm` (Neutral as fallback). Podcast narration keeps using it.

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

Power cut: when the gateway is unreachable the router falls to `local:muse-glimmer-30b` and the offline speech pack
(§6.3, §6.4); the UI shows "Working offline".

**Done when:** with Wi-Fi off on the 32 GB demo laptop, a typed and a spoken maths question each complete a checked
tutoring turn on Glimmer.

## 8. Removals and the adult product (JM-D14, JM-D15)

### 8.1 Remove

| What | Where |
|---|---|
| Nebius adapter, Nemotron ids and prices | `providers/nebius.py`, `providers/__init__.py`, `config.py`, `defaults.toml`, `custody.py`, `cloud_models.json`, `deploy/nebius-dev.toml`, `test_nebius.py` |
| Tavily | `cloud_gateway/tavily.py`; `app.py` (~126–128, routes ~434–440); `ask.py` (branches ~213–249, ~316); `config.py` (`TavilySettings`, validator ~377–387); `custody.py`; `secret_scan.py`; `agent_core/api/study.py` (`/v1/study/web` ~593–656); `client-core/src/study-workspace.ts` (~291); `client-core/src/ask-anything.ts` (`web_confirmed`); UI `StudyWorkspace.tsx` (~243); i18n `ask.web_permission`, `ask.search_web`, `study.web_consent`, `study.import_web`; tests `test_tavily.py`, `test_study_web.py` |
| Google/Gemini cloud stack | `providers/gemini.py`, `vertex.py`, `gemini_live.py`, `google_speech.py` out of configuration (deleted before submission if time allows); `config.voice_google` |

**Ask anything after Tavily:** answers from the curriculum packs and Muse Spark only, labelled "from your course".
Web search is out of scope for the entry. **Study:** file and paste import stay; web-page import is removed.

### 8.2 Adult product

| Area | Change |
|---|---|
| Sign-up | Date of birth field; under 18 → blocked with a short explanation. Store `age_band = "18_plus"` (`store/profiles.py` `ADULT_BAND`). |
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

- the engine (`services/agent-core`, `services/tool-worker`, `services/perception-worker`), the cloud gateway, the
  desktop app and shared packages;
- **Mathematics and Physics** content packs only (proposal; Chemistry and Accounting stay out);
- not: Studio and authoring tools (`apps/studio`, `services/pack-builder`), `services/signing-service`,
  `services/ingest`, `services/study-worker` if Study is cut, private specs, evals with licensed material.

The submission repository is built from this one at the end with only the parts above (same `git archive` method,
no history). Licence: Apache-2.0 for code; content packs under the owner's licence (`LicenseRef-Own`).

## 10. Demo-visible bugs to fix (from the 2026-10-25 review)

1. Maths starting with a digit shows as raw LaTeX (fixed in Jana main, uncommitted:
   `packages/ui/src/learn/PackText.tsx` and `agent_core/engine/assessment/items.py`; port it).
2. The subject switches from Mathematics to Physics mid-question; "Next up" and Practice recommend Physics after a
   Mathematics placement.
3. The composer accepts questions with no model available and never says so.
4. A message the core refused is re-sent on every reconnect (`packages/client-core/src/session.ts` ~393, ~472).
5. The learning-journey route skips input screening (`test_a1_input_routes.py`), if not already fixed upstream.
6. Tutor picker: radios announced as raw keys (`avatar.*`); "Choose this tutor" disabled when the default is picked.
7. Unit field and °C/Ω chips on unitless numeric answers.

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

| Day | Work |
|---|---|
| Oct 26 | Kickoff; read the final Official Rules; claim credits; Meta key in the keychain; §4.4 checks; start W1, W5, W6 |
| Oct 27–28 | W1 done; start W2, W3, W4 |
| Oct 29–30 | Voice round trip online; Omnilingual gate; Glimmer offline |
| Oct 31 | SAM photo marking; adult sign-up; deploy the demo host |
| Nov 1 | Power-cut switch end to end; self-hosted Magpie |
| Nov 2–3 | Polish, safety checks, eval run, record the video; owner signs off the §9 scope |
| Nov 4 | Build the submission repo (§9) and submit by 9:00 PM ET |

## 14. Demo (about 3 minutes)

1. An adult WAEC private candidate signs up (date of birth, 18+) and asks by voice: "A car speeds up from rest to
   20 m/s in 5 s. What's its acceleration?" Jana guides rather than telling, and checks the spoken answer with tools.
2. The learner photographs three lines of their own working. Jana highlights the line with the sign error **on their
   photo** (Muse Spark reads, SAM 3.1 outlines) and asks about that line.
3. A definition question is answered directly, with a check question.
4. **Power cut:** the network drops; Jana carries on with Muse Glimmer 30B and offline speech on the laptop.
5. Close: Meta for hearing, thinking, seeing and offline; every number checked; never the answer handed over.

## 15. Open items for the owner

1. Official Rules (read 2026-10-26 on the event waiver page): nothing bars existing work. A Submission must be the
   entrant's or its organisation's "original work product", solely owned, and may include open source it builds on.
   The Submission licence to the organisers is perpetual but **non-exclusive** (ownership stays). A separate clause
   gives the organisers a perpetual licence to any "Materials" shared or used "in connection with the event", which is
   wider than §9 assumes: take a legal view before showing private Jana work in workshops, Discord or office hours.
   The Startup track's Representative must be an active employee of the startup.
2. Meta API key and credit claim; request zero data retention (contact-sales form; it turns off search grounding).
3. NVIDIA: is trial audio allowed in the video? If not, approve the self-hosted Magpie spend (Modal/Baseten credits).
4. Submission scope in §9 (which subjects; whether Study stays). §9 as written does not install (§17).
5. Hosting: GCP project `jana-meta` (JM-D7) or partner credits only.
6. Photo demo (§5): may handwritten working go to the cloud, and what replaces the printed-text privacy check for it?
7. Demo laptop: its specification, to set Glimmer's speed gate; and whether `--local-model` may download weights.
8. Ask anything: build a "from your course" path (§8.1), use Spark's search grounding (Responses API only,
   $2.50 per 1,000 searches, off under zero data retention), or leave Ask out of the demo.
9. Budget dates: the copied dev config expires on 2026-11-02 00:46 UTC, before the deadline and judging, and keeps
   its ledger under `/tmp`; move both.

## 16. Meta facts confirmed from the docs (2026-10-26)

Read from dev.meta.ai/docs (public pages only). The sections above now state these; this list keeps what the adapter
and the voice and vision clients must also handle.

- **Chat Completions** at `https://api.meta.ai/v1/chat/completions`, Bearer key. Rejected with 400: `stop`, `n>1`,
  `logprobs`, `logit_bias`, `modalities`, `audio`, `prediction`, `web_search_options`, `max_output_tokens`,
  `top_p: 0`, custom tools, function names with two dots. Accepted: `seed`, `store` (default false),
  `prompt_cache_key`, `json_object`, the `developer` role. Every assistant `tool_calls` message must be followed by
  one `tool` message per call. Reasoning is not carried across turns on Chat Completions, and `reasoning_content`
  comes back empty for external callers.
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
- **Not documented, still (verify) with a real key**: the latency targets in §12; SAM image size limits and latency;
  whether tool history is accepted when `tools` is omitted; Spark's maximum output tokens; JSON Schema keywords
  such as `minLength`, `maxItems` and `pattern` in strict mode; free credits beyond the event's $150.

## 17. Corrections from the 2026-10-26 review

The project review of 2026-10-26 found these gaps in the plan above; each must be handled by the workstream named.

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
  of birth on every create form, checks it on the device without storing or sending it, and creates `18_plus` only;
  `POST`/`PATCH /v1/profiles` refuse other bands. Profiles an older build made keep their band and their guardian
  rules. The parent summary and alerts sections are gone. Still to do: `parent_remote_view`, the other guardian copy
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
  judging is not protected by any date.
