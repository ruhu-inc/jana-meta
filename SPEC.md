# jana-meta — specification for moving the fork onto Meta models

Status: **approved to build** (owner, 2026-10-26). This replaces the spec-only version of 2026-10-20 (kept in commit
7cf6c6e and in `../jana-meta-spec-backup`). The codebase is a history-free copy of jana-nebius at c4354de. This spec
says what changes, in which files, and what "done" means. It changes nothing in Jana's product (`../jana`).

Sources: the research brief `../jana-hackathon-research/meta-hackathon-brief.md` (models, prices, limits as of
2026-10-20), the event page and Official Rules (read 2026-10-25), and a file-level map of this repository.
Every Meta API detail marked **(verify)** must be confirmed with a real key on day 1 before code depends on it.

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

| # | Decision |
|---|---|
| JM-D9 | **Online reasoning is Muse Spark** for every engine role (Coach, Diagnoser, Solver, Checker, Reflector, auxiliary roles) and for Study and Ask generation. No other cloud language model is configured. |
| JM-D10 | **Online vision is Muse Spark + SAM 3.1.** Muse Spark reads the photo (what the question is, which regions matter); SAM 3.1 turns those regions into exact masks so Jana can crop for a second, sharper read and point at the exact place on the learner's own photo. |
| JM-D11 | **Local inference is Muse Glimmer 30B** (Apache-2.0, official GGUF Q4_K_M, ~16.8 GB) under the existing llama-server supervisor, on 32 GB+ machines. Smaller machines run online only. No non-Meta local model ships in the entry. |
| JM-D12 | **Speech to text is Meta.** Online: Muse Voice Transcribe (realtime). Offline: Meta **Omnilingual ASR** (Apache-2.0) if it passes the latency gate in §6.3; otherwise faster-whisper stays as the offline fallback. |
| JM-D13 | **Text to speech is not Meta**, because Meta has no commercially usable TTS (MMS-TTS is CC-BY-NC and not streaming). Online: **NVIDIA Magpie TTS** (self-hosted open weights for anything judges see; §6.4). Offline: **Kokoro-82M** (Apache-2.0, already in the speech pack). |
| JM-D14 | **Removed:** Nebius Token Factory, all Nemotron models, Tavily web search, and the Google/Gemini cloud stack (Gemini models, Gemini Live, Chirp STT/TTS) from configuration and from the submission. |
| JM-D15 | **Adult product:** every profile is `18_plus`; guardian consent, parent summaries, family plan and under-18 Ask policies are hidden or removed. Sign-up asks for date of birth and blocks under-18s. |
| JM-D16 | **Muse Spark Standard mode only**, never Contributor mode (Meta trains on Contributor data). Request zero data retention for the project account. Muse Code, if used, must not run in Contributor mode on this repository. |
| JM-D17 | **Submission scope:** the organisers receive a perpetual licence to whatever is submitted (Official Rules, "Hackathon Submission"). Only what the entry needs is submitted (§9). The owner signs off on the scope before submission. |

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
| `fast-model` | `muse-spark-1.2` **(verify; prefer 1.3 if it passes §4.4)** | coach, diagnoser, title, input_guard, ask | low |
| `strong-model` | same model id | solver, checker, reflector, study | solver high, checker medium |
| `small-model` | removed | — | — |

One model serves both aliases; the aliases stay so the router's tiers and `router.yaml` keep working. Muse Wonder is
not used (preview, about 5× the output price).

### 4.2 Changes

| File | Change |
|---|---|
| `services/cloud-gateway/cloud_gateway/providers/meta.py` (new) | `MetaAdapter(OpenAICompatAdapter)`: base `https://api.meta.ai/v1`, Bearer `meta_api_key`. `prepare_body`: `tool_choice` `"required"` → `"auto"` (Spark accepts only `auto`; the engine's existing tool nudge stays), a named-function `tool_choice` → `"auto"`, `"none"` → send no `tools`; keep `response_format: json_schema` as is (Spark does constrained decoding, so no schema-in-prompt copy like Nebius needed); drop `chat_template_kwargs`; map `reasoning_effort` none → low. Usage: read `reasoning_tokens` and bill them as output. |
| `cloud_gateway/providers/__init__.py`, `config.py` (`AdapterKind`) | Register `meta`; remove `nebius`. |
| `cloud_gateway/defaults.toml` | `[slots] primary="meta"`; `[providers.meta]` with the aliases above; prices $1.25 input / $0.15 cached / $4.25 output per 1M tokens **(verify)**. |
| `cloud_gateway/custody.py`, `secret_scan.py` | `META_API_KEY` environment secret and keychain account `meta_api_key` under service `jana-meta.cloud-gateway`; remove Nebius and Tavily sources and the `tvly-` pattern; add a Meta key pattern. |
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
  them (Spark image tokens **(verify)**; SAM per image).

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
3. **SAM 3.1 sharpens** (new): for each region Spark returns, call SAM 3.1 with a box prompt (and, for diagrams, a
   text concept prompt such as "force arrow", "angle label", "handwritten line") **(verify the API's prompt types)**.
   Result: a mask and tight box per region.
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
| `cloud_gateway/providers/sam.py` (new) + route `POST /v1/vision/segment` | SAM 3.1 client: image + box/point/text prompts → masks (RLE or polygon) and boxes; price $2.50 per 1,000 images **(verify)**; budgeted like chat. |
| `agent_core/engine/vision.py` | After `read()`, call the segment route for returned regions; attach masks; optional crop re-read. Offline fallback: Glimmer's own read with boxes only (no SAM offline). |
| `agent_core/engine/pointing.py`, `packages/client-core/src/pointer.ts`, `packages/ui/src/composer/CaptureDiagrams.tsx` | New pointer target kind `photo_region` (mask outline drawn over the learner's photo). |
| `cloud_models.json`, `router.yaml`, `inference_budget.py` | Enable cloud vision (§4.2, §4.3). |

**Done when:** a photo of three lines of handwritten working with one sign error is read, the wrong line is
highlighted on the photo, and the tutor asks about that line, within ~6 s of upload.

## 6. Speech (JM-D12, JM-D13)

### 6.1 Online speech to text: Muse Voice Transcribe

`wss://api.meta.ai/v1/asr/realtime`, PCM16 mono 24 kHz, `ENDPOINTING` mode, `languageBias: en`, `keywords` from the
curriculum glossary (physics and maths terms) **(verify the message format)**. Server events `speechStart`,
`speechEnd`, `speechComplete` map to the gateway's `Heard(begin/end/partial/final)`; barge-in stays ours (cancel TTS
on `speechStart`). Price $0.18 per audio hour. Sessions are capped at 60 minutes, so the gateway reconnects between
turns.

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
default and Omnilingual is shown only as the Yoruba/Hausa/Igbo/Pidgin input option (a demo line, not the default).

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
| `agent_core/router/recommended_models.json` | Replace the Qwen/Gemma entries with `muse-glimmer-30b` (Q4_K_M), class `high` only (32 GB+), `context_for_agents` 16384, `max_output` 4096, `thinking.available: true`, `default: on` (reasoning cannot be turned off), per-role sampling. |
| `agent_core/router/router.yaml` (`local:`) | `thinking_budget` > 0 for Glimmer (it always reasons; budget it rather than disable it); tiers list only `local:muse-glimmer-30b`. |
| `agent_core/providers/llama.py` | Confirm thinking detection and `chat_template_kwargs` against Glimmer's template; keep reasoning out of the released text. |
| `scripts/jana_tools/hackathon_dev.py` | `--local-model` downloads and pins the official Glimmer GGUF (SHA-256 recorded on first download) instead of Nemotron Nano 4B; `hackathon_app.connect()` keeps the `local` provider so offline works. |
| Model pack | If Glimmer ships a vision projector (mmproj) **(verify)**, include it as `vision_projector` so offline photos work; otherwise offline photos use OCR text only. |

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

1. Final Official Rules (published by kickoff): confirm nothing changes existing-code use or scope.
2. Meta API key and credit claim; request zero data retention.
3. NVIDIA: is trial audio allowed in the video? If not, approve the self-hosted Magpie spend (Modal/Baseten credits).
4. Submission scope in §9 (which subjects; whether Study stays).
5. Hosting: GCP project `jana-meta` (JM-D7) or partner credits only.
