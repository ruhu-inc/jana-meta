# jana-meta — stack specification (Meta Global AI Developer Hackathon)

Status: **spec only** (2026-10-20). No code is written until Jana's product is finished on its own stack (owner's rule)
and the hackathon's Official Rules are read on Oct 26. Source research:
`../jana-hackathon-research/meta-hackathon-brief.md`. This spec is separate from Jana's product specification
(`../jana/docs`) and changes nothing in it.

## 1. What it is

**Jana for adult learners, on Meta.** A voice-first AI tutor for learners **aged 18 and over** preparing for O level
exams: WAEC and NECO private candidates (GCE series), JAMB/UTME re-takers, NABTEB and adult-education students, and
university first-years revising maths and physics. It keeps Jana's teaching rules: it never simply gives homework
answers, it checks every number with tools before saying it, and it labels anything it could not check.

Event: Meta Global AI Developer Hackathon (remote, Oct 26 – Nov 4, 2026), **Startup track**, theme **"Build for Your
World"**. The owner's application named Jana and was approved.

## 2. Decisions (owner, 2026-10-20)

| # | Decision |
|---|---|
| JM-D1 | Audience is **18+ only**, because the Meta Model API terms (§10.1) forbid end users and products aimed at under-18s. Jana's under-18 product stays on its own stack (Gemini, D7). |
| JM-D2 | **Thinking stays on Meta**: every tutoring reply is produced by Meta's **Muse Spark** inside Jana's engine. |
| JM-D3 | **Hearing on Meta**: speech to text is Meta's **Muse Voice Transcribe** (realtime). |
| JM-D4 | **Speaking on NVIDIA**: text to speech is **NVIDIA Magpie TTS** (`nvidia/magpie-tts-multilingual`, voice `Magpie-Multilingual.EN-US.Aria.Neutral`). Development uses the API catalog's hosted trial (gRPC to `grpc.nvcf.nvidia.com:443`, `SynthesizeOnline`, one call per accepted sentence). Because the trial terms are evaluation-only and forbid distributing generated audio, the **judged demo and video use self-hosted open weights** (`nvidia/magpie_tts_multilingual_357m`, NVIDIA Open Model License, commercial use) on a Baseten or Modal GPU, unless NVIDIA confirms hackathon use is covered (owner decides on Oct 26). Meta has no text to speech; a third-party voice is acceptable because the thinking stays on Meta. |
| JM-D5 | **Offline on Meta open weights: Muse Glimmer 30B** (Apache-2.0, official GGUF `Muse-Glimmer-30B-KQuant-17GB-Q4_K_M.gguf`, 16.8 GB) through llama-server, on a **32 GB-or-larger laptop** for the demo (owner, 2026-10-21). In the research benchmark it had the best structured output and tool use. Llama 3.1 8B is **not** used in the demo: it fits 8 GB laptops, but in the engine it verified few plans (15/80 numeric WAEC items correct). It appears only as a "runs on 8 GB, lower quality" note. Kokoro remains the offline voice (CPU). |
| JM-D6 | **Cascaded voice, not speech-to-speech**: no Meta model does realtime speech in and out, and a model that answers for itself would bypass the engine's checks. Every spoken word comes from an accepted engine turn. |
| JM-D7 | Hosted in a **separate GCP project, `jana-meta`** (proposed id `jana-meta-512005`; to be created with the owner's OK and billing account). |
| JM-D8 | **Separate from the product**: a `jana-meta` fork/branch of Jana if the rules allow existing code, otherwise a fresh repo built from Jana's engine design. Nothing with a non-commercial licence (Meta MMS, Seamless) is merged back into Jana. |

## 3. Architecture

```
                         ┌──────────────── GCP project jana-meta ────────────────┐
 Browser / desktop app   │                                                       │
 ┌───────────────────┐   │  voice gateway (Cloud Run, WebSocket)                 │
 │ mic → Silero VAD  │──►│   ├─► Meta Muse Voice Transcribe (realtime WS) ──┐    │
 │ (barge-in)        │   │   │                                              ▼    │
 │ speaker ◄─────────│◄──│   │   Jana engine (agent-core, Cloud Run)             │
 └───────────────────┘   │   │     input guard → Diagnoser → Solver + tools      │
                         │   │     → Checker → Coach → gates → Finalise          │
                         │   │     model: Meta Muse Spark (api.meta.ai/v1)       │
                         │   │                     │ accepted say_spoken only    │
                         │   └─◄ NVIDIA Magpie TTS (API catalog, streaming) ◄────┘
                         │  Secret Manager: Meta key, NVIDIA key · Firestore: users │
                         └───────────────────────────────────────────────────────┘
 Offline (laptop, 32 GB+): Jana desktop + llama-server (Muse Glimmer 30B) + faster-whisper + Kokoro
```

### 3.1 Components

| Stage | Online (hackathon) | Offline (laptop) | Licence |
|---|---|---|---|
| Voice activity / barge-in | Silero VAD in the client; Voice Transcribe server endpointing (`speechStart`, `speechEnd`, `speechComplete`) | Silero VAD + Smart Turn v3 | MIT / BSD-2 |
| Speech to text | **Muse Voice Transcribe 1.0**, `wss://api.meta.ai/v1/asr/realtime`, PCM16 mono 24 or 16 kHz, `ENDPOINTING`, `languageBias: en`, `keywords`: WAEC physics/maths terms | faster-whisper small.en | Meta API ToS / MIT |
| Tutor engine | Jana agent-core (unchanged design: guards, tools, gates) | same | Jana |
| Reasoning model | **Muse Spark 1.2** (`muse-spark-1.2`), `json_schema` structured output, `reasoning_effort: low`, Standard mode (never Contributor mode) | Muse Glimmer 30B Q4_K_M (`Reasoning strength: low`; reasoning cannot be turned off) | Meta API ToS / Apache-2.0 |
| Text to speech | **NVIDIA Magpie TTS**: API-catalog trial in development, self-hosted 357M open weights for the demo; streaming LINEAR_PCM at 22.05 kHz (resampled to the bridge's 24 kHz); sentence by sentence from the accepted `say_spoken`; US English voices only (a Nigerian English voice is future work) | Kokoro-82M (`af_heart`) with Jana's spelling-to-sound fallback | NVIDIA API catalog terms (development use) / Apache-2.0 |
| Orchestration | Jana's voice bridge (provisional turns, filler, barge-in, heard text) | same, through the local sidecar | Jana |

### 3.2 Adapters jana-meta adds to Jana's engine

1. **Meta provider** (`providers/meta.py`): OpenAI-compatible Chat Completions to `https://api.meta.ai/v1`.
   - Muse Spark accepts only `tool_choice: "auto"`. The adapter maps `required` to `auto` plus the engine's existing
     tool nudge, and `none` to *no tools sent* (the cloud path of D123), never `tool_choice: "none"`.
   - Structured output uses `json_schema` mode (constrained decoding); the router's `tool` structured mode is not
     offered for this provider.
   - Reasoning tokens count against `max_tokens`: budgets are raised accordingly and `reasoning_effort: low` is the
     default for the Coach.
2. **Voice Transcribe STT stage** in place of the sidecar's faster-whisper, emitting the same Realtime events the
   bridge already understands (transcript deltas, speech start and stop).
3. **Magpie TTS stage**: a streaming client to NVIDIA's API catalog that returns 24 kHz PCM16 to the bridge, so the
   bridge's playback tracking, heard-text and barge-in rules work unchanged.

## 4. Safety, age and data

- **Age gate (JM-D1)**: sign-up asks for date of birth and states the service is for 18+; an under-18 date blocks
  sign-up with a pointer to Jana's free offline app. No "I am 18" checkbox alone. The demo never shows an under-18 user.
- **Same safeguards as Jana**: input guard and safety screen on every transcript, the engine's gates on every reply
  (schema, safety, checked numbers, no answer leak), distress templates, honest "not checked" labels.
- **No training on learner data**: Muse Spark **Standard** mode only (Contributor mode trains on data, ToS §6.2).
  Request **zero data retention** from Meta for the project account.
- **Audio**: streamed only, never stored; transcripts kept per learner like typed messages; NVIDIA and Meta keys in
  Secret Manager, never in the client.
- **Region**: GCP europe-west2 (London) or europe-west1 (Belgium); confirm Meta API availability for Nigerian users
  (not on the restricted list; supported list unpublished).

## 5. GCP project `jana-meta`

| Item | Setting |
|---|---|
| Project | `jana-meta-512005` (pending the owner's OK and billing account) |
| Region | europe-west1 (GPU availability) or europe-west2 |
| Services | Cloud Run (engine, voice gateway, web), Artifact Registry, Secret Manager, Cloud Build, Firestore (users, sessions), Cloud Logging (no payload logging) |
| Secrets | `META_API_KEY`, `NVIDIA_API_KEY` |
| Cost guard | Budget alert; Cloud Run min instances 0 outside demo windows |

## 6. Latency budget (to measure on day 1–3; nothing measured yet)

| Step | Target |
|---|---|
| Speech end → final transcript (Voice Transcribe endpointing) | ≤ 0.7 s |
| Filler spoken if no reply yet | at 1.5 s |
| Engine with Muse Spark (guard + tools + Coach + gates) | ≤ 3 s typical |
| Magpie first audio after accepted sentence | ≤ 0.4 s |
| **Speech end → first answer audio** | **≤ 4 s typical, filler at 1.5 s** |

Lever if slow: a single Muse Spark call for simple turns; the conceptual path (D122) for definitions.

## 7. Demo (about 3 minutes)

1. An adult WAEC private candidate signs up (18+ gate), opens Jana and asks by voice: "A car speeds up from rest to
   20 m/s in 5 s. What's its acceleration?"
2. Jana answers in real time (Voice Transcribe → Muse Spark in the engine → Magpie): guides instead of telling,
   checks the student's spoken answer with tools, and refuses to just give the final number.
3. A definition question ("What is the formula for kinetic energy?") is explained directly with a check question.
4. **Power cut**: the network drops; Jana continues offline on Muse Glimmer 30B (32 GB+ laptop) with Kokoro on the laptop.
5. Close: every number checked, never the answer handed over, works with no internet; Meta for hearing and thinking.

## 8. Open items to settle on Oct 26

1. Official Rules: is existing code allowed (fork) or fresh code only (new repo)? IP and submission format.
2. Meta Model API access and credits ($150 reported, unconfirmed); request zero data retention.
3. NVIDIA Magpie: confirm the NVCF function id (`877104f7-e885-42b9-8de8-f6e4c6303969`, from pipecat), the trial's
   rate limit (~40 RPM reported), and whether demo use is covered; otherwise stand up the self-hosted 357M weights.
4. Benchmarks: done (research brief §2.4 format/tool tests, §2.5 subject eval). Glimmer 30B chosen for the offline demo; a Glimmer run of the 100-question subject eval is optional, when the machine is free.
5. GCP project creation and billing account.

## 9. Plan (Oct 26 – Nov 4)

| Day | Work |
|---|---|
| Oct 26 | Read rules; create the repo/fork and GCP project; keys in Secret Manager |
| Oct 27–28 | Meta provider adapter; engine on Muse Spark passes Jana's engine tests; measure latency |
| Oct 29–30 | Voice Transcribe STT stage and Magpie TTS stage in the bridge; spoken round trip end to end |
| Oct 31 | 18+ sign-up, web client, deploy to Cloud Run |
| Nov 1 | Offline tier on Muse Glimmer 30B (32 GB+ laptop); the power-cut switch |
| Nov 2–3 | Polish, safety checks, eval run, demo recording |
| Nov 4 | Submit by 9:00 PM ET |
