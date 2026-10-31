# Jana: an exam-prep tutor for adult learners, built on Meta's models

Jana helps adults (18 and over) prepare for O level Mathematics, Physics and Chemistry, or refresh those foundations
before university entry and first-year study. The content packs follow the Cambridge O level topic structure
(5054, 5070), written in our own words, and cover the core O level topics that WAEC, NECO and GCE syllabuses share.

Jana is a tutor, not a chatbot. It never just hands over an answer: it asks where the learner is stuck, works from
their own steps and gives the next hint. Every number it says is checked by code first (a sandboxed maths and units
worker), and anything it could not check is labelled as such. It reads photos of handwritten working and points at
the exact line that went wrong, listens and speaks, researches a topic into a cited study pack, and keeps teaching
when the internet goes away.

## Hackathon contribution

Jana existed before this event. Its tutoring engine, curriculum packs, desktop shell and deterministic checking
foundation are prior work. The October 26–November 4, 2026 entry continues the Meta model integration and adds
the personal Study companion: durable conversations, explicit remember/correct/forget commands,
profile isolation, inspectable learning evidence and source-backed progress claims. The companion work is recorded
in commits `7a92235d` and `aed35cbf` (October 29–30). These are implementation claims, not measured learning gains.
The demo should distinguish this new work from the existing product and identify every human contributor.

## The Meta models and what each does

| Model | Where it runs | What it does in Jana |
| --- | --- | --- |
| **Muse Spark** (`muse-spark-1.3`, Standard mode) | Meta Model API, through Jana's gateway | The tutor's reasoning: the input guard, the Diagnoser (what the learner is stuck on), the Solver and Checker (which call the maths tools) and the Coach (the next hint). Also reads photos of working and diagrams, writes and verifies Study aids, and runs the research agent: web search on the Responses API, every statement checked against the page it cites. |
| **SAM 3.1** | Meta Model API, through the gateway | Turns the regions Muse Spark finds on a photo into exact outlines, so Jana can highlight the line of working where a sign changed on the learner's own photo, and drill the parts of a labelled diagram ("tap the condenser"), marking each tap against the outline. |
| **Muse Voice Transcribe** | Meta Model API (realtime), through the gateway | Hears the learner in cloud voice conversation: endpointing, live partial transcripts and the curriculum's keywords as hints. Every spoken reply still comes from an accepted, checked tutor turn. |
| **Muse Glimmer 30B** | On the laptop (open weights, Apache-2.0), with llama.cpp | The tutor offline: when the network drops, the same engine falls back to Glimmer within seconds, with its vision projector for photos and its DFlash draft model for faster generation. Machines with 32 GB of memory or more. |

Muse Spark is used in Standard mode only; Contributor mode is never configured. Meta's Model API terms require every
end user to be 18 or over, so Jana asks for a date of birth at sign-up and creates adult profiles only.

Meta offers no text-to-speech model licensed for commercial use, so spoken replies and study-pack podcasts are read by
Kokoro-82M (Apache-2.0).

## How it fits together

```
 Learner (browser host or desktop app)
   │ typed question, photo, voice
   ▼
 Jana engine (services/agent-core, on the device)
   input guard → Diagnoser → Solver + tools → Checker → Coach → release gates
   tool worker (sandboxed maths, units, marking) · perception worker (local privacy pass on every photo)
   │                                                   │ network gone
   ▼                                                   ▼
 Jana gateway (services/cloud-gateway)               Muse Glimmer 30B on llama.cpp
   holds the Meta key, enforces the spending budget,
   minimises what leaves the device, logs no payloads
   ├─ chat and tools     → Muse Spark (api.meta.ai/v1)
   ├─ photos             → Muse Spark reads ⇄ SAM 3.1 outlines (/v1/vision/segment)
   ├─ voice              → Muse Voice Transcribe hears · Kokoro reads accepted replies
   └─ research agent     → Muse Spark on the Responses API with web search, then verification
```

Offline on any laptop, the signed content packs keep working: lessons, practice with code-checked marking and
authored hints, mock papers and saved study packs.

## Run it

Requirements (tested on macOS on Apple silicon): Node 24 (`.nvmrc`) with pnpm 10, uv 0.10 (it installs Python
3.12), Rust (`rust-toolchain.toml`) for the desktop shell, and Tesseract for the photo privacy pass
(`brew install tesseract`).

```bash
pnpm install --frozen-lockfile
```

```bash
uv sync --locked --all-packages
```

### 1. Put your Meta Model API key in the keychain

The gateway is the only process that reads the key; the app, its engine and the local model never see it. On macOS,
add a generic password to the login keychain with service `jana-meta.cloud-gateway` and account `meta_api_key`:

```bash
security add-generic-password -s jana-meta.cloud-gateway -a meta_api_key -w
```

(It prompts for the key, so the key never appears in your shell history.) On Linux the gateway reads the Secret
Service entry with the same service and account. A gateway-only `META_API_KEY` environment variable also works.

### 2. Start the gateway

```bash
uv run python -m cloud_gateway --config services/cloud-gateway/deploy/meta-dev.toml --port 8081
```

`meta-dev.toml` is a local development configuration: a hard spending budget (per day, in total and an expiry date),
a ledger kept in `~/.jana-meta/gateway` across restarts, and cloud voice switched on. Set its `[quotas]` to your own
limits and dates before you use it with your own key; the ledger reserves each call's full cost before sending it and
refuses once a limit is reached.

### 3. Start the app

```bash
uv run python -m jana_tools.hackathon_dev
```

Open **http://127.0.0.1:5187/**. The first launch builds and verifies the Mathematics, Physics and Chemistry packs from
`content/curriculum` and signs them with the published development key (a few minutes; later launches reuse them).
Create a profile, then in Settings → Online features give your consent to the cloud tutor.

For a rehearsal without development reloads, use a stable build and a separate synthetic profile directory:

```bash
uv run python -m jana_tools.hackathon_dev --stable --port 5197 --data-dir /tmp/jana-demo
```

Open **http://127.0.0.1:5197/**. Keep the same directory when restarting to verify continuity. With cloud tutoring
off and no local model, saved history, explicit memory commands and authored practice remain available; ordinary
AI conversation requires a configured model. Exported profiles include saved learning state by default; raw
conversation inclusion requires separate authorization.
The browser preview has no native folder picker: use the desktop app for profile archive export and restoration.

To keep tutoring offline on a machine with 32 GB or more, download Muse Glimmer 30B's GGUF files from
[meta-models/Muse-Glimmer-30B-GGUF](https://huggingface.co/meta-models/Muse-Glimmer-30B-GGUF)
(`Muse-Glimmer-30B-KQuant-17GB-Q4_K_M.gguf`, and beside it `mmproj-Muse-Glimmer-30B-Q4_K_M.gguf` for photos and
`dflash-Muse-Glimmer-30B-Q4_K_M.gguf` for speed), install llama.cpp, and pass the model:

```bash
uv run python -m jana_tools.hackathon_dev --local-model /path/to/Muse-Glimmer-30B-KQuant-17GB-Q4_K_M.gguf
```

The launcher checks each file against a pinned SHA-256, never downloads weights itself, and keeps the Meta key out of
the model runtime's environment.

Cloud voice reads replies with Kokoro-82M from a local speech pack (`apps/desktop/dev/speech_pack.py` assembles one;
the gateway's `[voice_tts]` settings say where it is). Without it, typed tutoring, photos, Study and research all
work.

### The desktop app

`apps/desktop` is the same interface in a Tauri shell, which supervises the engine and the local model and keeps the
device's secrets in the OS keychain (service `app.jana-meta.desktop`). `pnpm --filter @jana/desktop dev` starts its
interface in scripted development mode; scripted replies are never presented as Muse Spark or Glimmer output.

## Tests

```bash
uv run pytest services
```

```bash
pnpm test
```

```bash
cargo test --locked --workspace
```

The tests need no network and no Meta key, so they spend no credit; the few live checks skip themselves unless asked
for.

## Repository layout

| Path | Holds |
| --- | --- |
| `apps/desktop/` | The app: `src/` (React), `src-tauri/` (Rust shell), `dev/` (the browser host's engine and pack seeding) |
| `packages/` | `ui`, `client-core`, `renderers` (interactive science visuals), `i18n`, `contracts-ts` (generated) |
| `services/agent-core/` | The tutoring engine: roles, release gates, learner model, Study, research and vision on the device |
| `services/cloud-gateway/` | The gateway: Meta adapters (`providers/meta.py`, `meta_responses.py`, `sam.py`, `meta_speech.py`), budget, research agent |
| `services/tool-worker/` | Sandboxed maths, units and marking that every number is checked with |
| `services/perception-worker/`, `services/study-worker/` | Sandboxed photo privacy pass, and document extraction for Study |
| `services/pack-builder/`, `services/signing-service/` | Build, verify and development-sign the content packs |
| `content/`, `skills/` | The tutor's authored rules and prompts, and the curriculum sources of the packs |
| `contracts/` | Public wire contracts; the TypeScript and Python bindings are generated from them |
| `evals/` | Synthetic scenarios, recorded model fixtures and contract corpora the tests use |

## Licences

- Code: [Apache License 2.0](LICENSE). See [NOTICE](NOTICE).
- Content packs (`content/curriculum`): the owner's own licence (`LicenseRef-Own` in each record); not Apache-2.0.
- Third-party components keep their own licences: [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES).

## Built with

- **Muse Spark**, **SAM 3.1** and **Muse Voice Transcribe** through the Meta Model API, under the
  [Meta Model API Terms of Service](https://dev.meta.ai/legal/terms-of-service). No Meta model weights are part of
  this repository.
- **Muse Glimmer 30B**, open weights under the Apache License 2.0, downloaded by the user from Meta's release.
- **meta-sam-parser** (Meta's decoder for SAM 3.1's masks), installed from PyPI under the SAM License; a copy of the
  licence comes with the package.
- **Kokoro-82M** (Apache-2.0) for speech, and **llama.cpp** (MIT) to run Glimmer.
