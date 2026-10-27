"""Spoken-turn latency on Meta (SPEC §6, §12): recorded questions through cloud voice, answered by the shipped engine.

    uv run python -m jana_tools.voice_latency [--only phys-car] [--repeat 2] [--max-usd 0.5] [--wavs DIR] [--out DIR]

The gateway side is the real one, in process: a `VoiceConnection` of the gateway's voice service with the stack
`voice_meta` builds (Muse Voice Transcribe over its realtime socket, Kokoro in its worker), the deployment's ledger
and budget, and a credential bound for this harness. The device side is this script: it streams a recorded question
(24 kHz PCM16 WAV) in real time as the bridge would, keeps the microphone open with silence afterwards, and answers
the tunnelled chat-completions request the way the core's voice adapter does (VOC-12, VOC-33): the keyed filler once
`voice_cloud_filler_after_ms` passes with nothing accepted, then the accepted turn's spoken form, sentence by sentence.
That turn is a real engine turn on Muse Spark (`turn_latency`'s engine and in-process gateway, its quality checks),
run on the transcript Voice Transcribe returned. Every spoken word is the filler or the accepted spoken form.

Measured from the end of speech in the recording (its last loud 20 ms window, played at real time): the
recognizer's end of speech, the final transcript, the filler's first audio and the first audio of the answer, plus the
engine turn and the time from accepted words to their first audio. Without `--wavs`, the questions are spoken by
Kokoro (`af_heart`) first. The report keeps timings, the synthetic questions' transcripts and spoken replies only.
"""

from __future__ import annotations

import argparse
import array
import asyncio
import base64
import hashlib
import json
import re
import statistics
import sys
import tempfile
import time
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jana_tools.turn_latency import CASES, CONFIG, Case, InProcessGateway, open_engine, quality

FILLER = "Let me work that out."  # the adapter's keyed filler (agent_core.api.voice_adapter.FILLERS)
BINDING = "jana-voice-binding: vb_" + "0" * 26
CHUNK = 4800  # 100 ms of 24 kHz PCM16 per append (6,400 base64 characters, the wire subset's bound)


@dataclass(frozen=True)
class Spoken:
    """A seeded turn (`turn_latency.CASES`) as a learner would say it."""

    case: str
    words: str


QUESTIONS = (
    Spoken("phys-car", "A car speeds up from rest to 20 metres per second in 5 seconds. What's its acceleration?"),
    Spoken(
        "phys-force", "A 2 kilogram mass accelerates at 3 metres per second squared. What resultant force acts on it?"
    ),
    Spoken("phys-ohm", "A 12 volt battery drives a current of 0.5 amps through a resistor. What is its resistance?"),
    Spoken("maths-linear", "Solve 7 x minus 3 equals 18."),
    Spoken("maths-percent", "What is 15 percent of 240?"),
)


class Pipe:
    """The voice connection's socket, in memory: what the gateway sends is stamped as it arrives."""

    def __init__(self) -> None:
        self.inbound: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self.outbound: asyncio.Queue[tuple[float, dict[str, Any]]] = asyncio.Queue()
        self.headers: dict[str, str] = {}

    async def send_text(self, text: str) -> None:
        self.outbound.put_nowait((time.monotonic(), json.loads(text)))

    async def receive(self) -> dict[str, Any]:
        return await self.inbound.get()

    def send(self, event: dict[str, Any]) -> None:
        self.inbound.put_nowait({"type": "websocket.receive", "text": json.dumps(event)})

    async def accept(self) -> None:
        return None

    async def close(self, code: int = 1000) -> None:
        self.inbound.put_nowait({"type": "websocket.disconnect", "code": code})


def read_wav(path: Path) -> bytes:
    with wave.open(str(path), "rb") as source:
        if (source.getnchannels(), source.getsampwidth(), source.getframerate()) != (1, 2, 24_000):
            raise SystemExit(f"{path}: 24 kHz mono PCM16 expected")
        return source.readframes(source.getnframes())


def speech_end_s(pcm: bytes, floor: int = 600) -> float:
    """Where speech ends: after the last 20 ms window louder than `floor`."""
    samples, window, end = array.array("h", pcm), 480, 0
    for at in range(0, len(samples) - window + 1, window):
        if max(abs(s) for s in samples[at : at + window]) > floor:
            end = at + window
    return end / 24_000


async def make_wavs(config: Any, out: Path) -> None:
    """The questions spoken by Kokoro, with 300 ms of quiet before them, as a learner's recording would start."""
    from cloud_gateway.providers.kokoro_speech import KokoroSynthesizer

    out.mkdir(parents=True, exist_ok=True)
    missing = [q for q in QUESTIONS if not (out / f"{q.case}.wav").exists()]
    if not missing:
        return
    tts = KokoroSynthesizer(config.voice_meta)
    try:
        for question in missing:
            pcm = b"\0" * (48 * 300) + b"".join([chunk async for chunk in tts.synthesize(question.words)])
            with wave.open(str(out / f"{question.case}.wav"), "wb") as target:
                target.setnchannels(1)
                target.setsampwidth(2)
                target.setframerate(24_000)
                target.writeframes(pcm)
    finally:
        await tts.aclose()


def spoken_form(engine: Any, result: Any, before: set[str]) -> str:
    """The accepted turn's spoken form, as `ProvisionalVoiceTurn.evaluate` derives it (engine-owned templates
    included)."""
    from agent_core.engine.pointing import Targets, resolve
    from agent_core.engine.verbaliser import verbalise

    accepted = result.tutor_turn
    if accepted is not None and accepted.get("say_spoken"):
        new_steps = frozenset(
            s.step_id for s in engine.state.board.steps if s.step_id not in before and s.owner == "tutor"
        )
        return str(resolve(str(accepted["say_spoken"]), Targets.of(engine.state, new_steps)).text)
    text = (
        accepted["say"]
        if accepted is not None
        else next(
            (
                row.get("spoken_form") or row["content"]
                for row in reversed(engine.state.transcript)
                if row.get("role") == "assistant"
            ),
            "",
        )
    )
    return str(verbalise(text).text)


class Device:
    """The device's side of one voice connection: microphone in, the engine adapter's answers out."""

    def __init__(self, pipe: Pipe, engine: Any, gateway: InProcessGateway, case: Case, filler_ms: int) -> None:
        self.pipe, self.engine, self.gateway, self.case, self.filler_ms = pipe, engine, gateway, case, filler_ms
        self.marks: dict[str, float] = {}
        self.transcript = ""
        self.spoken = ""
        self.heard = ""  # transcript deltas of the reply
        self.last_audio: float | None = None
        self.latency: dict[str, Any] = {}
        self.turn: dict[str, Any] = {}
        self.done = asyncio.Event()
        self.microphone_on = True
        self.answering: asyncio.Task[None] | None = None

    def mark(self, name: str, at: float | None = None) -> None:
        self.marks.setdefault(name, at if at is not None else time.monotonic())

    async def listen(self) -> None:
        while not self.done.is_set():
            at, event = await self.pipe.outbound.get()
            kind = event["type"]
            if kind == "session.created":
                self.mark("session_created", at)
                self.pipe.send(
                    {
                        "type": "session.update",
                        "session": {
                            "type": "realtime",
                            "instructions": BINDING,
                            "tools": [],
                            "audio": {
                                "input": {
                                    "format": {"type": "audio/pcm", "rate": 24000},
                                    "transcription": {"language": "en"},
                                    "turn_detection": {
                                        "type": "server_vad",
                                        "silence_duration_ms": 500,
                                        "interrupt_response": True,
                                    },
                                }
                            },
                        },
                    }
                )
            elif kind == "input_audio_buffer.speech_started":
                self.mark("speech_started", at)
            elif kind == "input_audio_buffer.speech_stopped":
                self.mark("speech_stopped", at)
            elif kind == "conversation.item.input_audio_transcription.completed":
                self.mark("transcribed", at)
                self.transcript = event["transcript"]
            elif kind == "jana.voice_llm.request":
                self.mark("asked", at)
                self.answering = asyncio.create_task(
                    self.answer(event["request_id"], event["body"]["messages"][-1]["content"])
                )
            elif kind == "response.output_audio.delta":
                self.mark("first_audio", at)
                self.last_audio = at
            elif kind == "response.output_audio_transcript.delta":
                self.heard += event["delta"]
                if len(self.heard.strip()) > len(FILLER) and "answer_audio" not in self.marks:
                    # The answer's first audio is the delta its first words follow (VOC-09: words follow audio).
                    self.mark("answer_audio", self.last_audio)
            elif kind == "response.done":
                metadata = event["response"].get("metadata") or {}
                if "speech_to_speech.turn_latency" in metadata:
                    self.latency = json.loads(metadata["speech_to_speech.turn_latency"])
                if event["response"]["status"] != "cancelled":
                    self.mark("done", at)
                    self.done.set()
            elif kind == "error":
                self.marks["error"] = at
                self.turn["error"] = event["error"].get("code")
                self.done.set()

    def chunk(self, request_id: str, words: str) -> None:
        data = {
            "id": "chatcmpl-voice-latency",
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": "jana-tutor-voice",
            "choices": [{"index": 0, "delta": {"content": words}, "finish_reason": None}],
        }
        self.pipe.send({"type": "jana.voice_llm.chunk", "request_id": request_id, "data": json.dumps(data)})

    async def answer(self, request_id: str, text: str) -> None:
        """The voice adapter's reply (VOC-12, VOC-33): the filler at `filler_ms` if nothing is accepted yet, then the
        accepted spoken form, one sentence per chunk."""
        from jana_tools.turn_latency import Clock

        engine, case = self.engine, Case(self.case.name, self.case.subject, text, self.case.leaks, self.case.computes)
        withheld = list(engine.state.withheld())
        before = {s.step_id for s in engine.state.board.steps}
        self.gateway.clock = Clock()
        work = asyncio.create_task(engine.start_problem(text))
        done, _ = await asyncio.wait({work}, timeout=self.filler_ms / 1000)
        if not done:
            self.mark("filler_sent")
            self.chunk(request_id, FILLER + " ")
        result = await work
        self.mark("accepted")
        self.spoken = spoken_form(engine, result, before)
        for sentence in re.split(r"(?<=[.!?])(?=\s)", self.spoken):
            self.chunk(request_id, sentence)
        self.pipe.send({"type": "jana.voice_llm.done", "request_id": request_id, "status": "ok"})
        shown = engine.events.student_text(result.turn_id)
        self.turn = {
            "status": result.status,
            "calls": len(self.gateway.clock.calls),
            "quality": quality(case, engine, result.turn_id, shown, result, withheld),
            "shown": shown,
            "say_spoken": (result.tutor_turn or {}).get("say_spoken"),
        }

    async def speak(self, pcm: bytes, end_s: float) -> None:
        start = time.monotonic()
        self.marks["speech_end"] = start + end_s
        sent = 0
        while self.microphone_on:  # the recording, then the open microphone's quiet, in real time
            piece = pcm[sent : sent + CHUNK] if sent < len(pcm) else b""
            piece = piece + b"\0" * (CHUNK - len(piece))
            await asyncio.sleep(max(0.0, start + sent / 48_000 - time.monotonic()))
            self.pipe.send({"type": "input_audio_buffer.append", "audio": base64.b64encode(piece).decode()})
            sent += CHUNK
            if time.monotonic() - start > 90:
                break


def credential(gw: Any) -> tuple[Any, str]:
    """A credential for this harness under its own development subscription (as the browser host binds its own), and an
    access token for it: the voice connection re-checks the token at every turn, as each request is checked."""
    import secrets

    from cloud_gateway.auth import Session

    public = hashlib.sha256(b"jana-meta voice latency harness").digest()
    expires = gw.config.quotas.deployment_budget_expires_at.timestamp()
    state, credential_id = gw.store.bind_credential(
        "dcr_voicelatency" + public.hex()[:16],
        public,
        "lic_hackathon",
        "sub_voice_latency",
        expires,
        time.time(),
        gw.config.devices_per_subscription,
    )
    if state not in ("added", "renewed"):
        raise SystemExit(f"could not bind the harness credential: {state}")
    token = "vlt_" + secrets.token_urlsafe(24)
    gw.store.add_token(token, credential_id, time.time() + 3600)
    return Session(credential_id, "lic_hackathon", "sub_voice_latency"), token


async def run_one(
    question: Spoken,
    pcm: bytes,
    service: Any,
    gateway: InProcessGateway,
    session: tuple[Any, str],
    out: Path,
    supervisor: Any,
    filler_ms: int,
) -> dict[str, Any]:
    from cloud_gateway.voice import VoiceConnection

    case = next(c for c in CASES if c.name == question.case)
    engine = await open_engine(gateway, case.subject, out, supervisor)
    pipe = Pipe()
    pipe.headers["authorization"] = "Bearer " + session[1]
    connection = VoiceConnection(service, pipe, session[0])
    device = Device(pipe, engine, gateway, case, filler_ms)
    opened = time.monotonic()
    served = asyncio.create_task(connection.run())
    listening = asyncio.create_task(device.listen())
    await asyncio.sleep(0)
    while "session_created" not in device.marks:
        await asyncio.sleep(0.01)
    await asyncio.sleep(0.2)  # the session.update round trip
    end = speech_end_s(pcm)
    speaking = asyncio.create_task(device.speak(pcm, end))
    try:
        await asyncio.wait_for(device.done.wait(), 120)
    finally:
        device.microphone_on = False
        await speaking
        listening.cancel()
        await connection.close()
        served.cancel()
        await asyncio.gather(served, listening, return_exceptions=True)
    marks, zero = device.marks, device.marks["speech_end"]

    def since(name: str, origin: float | None = None) -> float | None:
        base = zero if origin is None else origin
        return round(marks[name] - base, 3) if name in marks else None

    return {
        "case": question.case,
        "said": question.words,
        "transcript": device.transcript,
        "spoken": device.spoken,
        "speech_s": round(end, 2),
        "prewarm_s": round(marks["session_created"] - opened, 3),
        "speech_stopped_s": since("speech_stopped"),
        "final_transcript_s": since("transcribed"),
        "filler_audio_s": since("first_audio") if "filler_sent" in marks else None,
        "answer_audio_s": since("answer_audio") if "filler_sent" in marks else since("first_audio"),
        "engine_s": since("accepted", marks.get("asked")),
        "tts_first_s": since("answer_audio", marks.get("accepted"))
        if "filler_sent" in marks
        else since("first_audio", marks.get("accepted")),
        "gateway_latency": device.latency,
        **device.turn,
    }


def median(values: list[float | None]) -> float | None:
    present = [v for v in values if v is not None]
    return round(statistics.median(present), 2) if present else None


async def main_async(args: argparse.Namespace) -> int:
    from agent_core.config import Settings
    from agent_core.tools.worker import WorkerSupervisor
    from agent_core.tools.worker.launch import process_factory
    from cloud_gateway.app import Gateway, log_alert
    from cloud_gateway.config import load_config
    from cloud_gateway.providers import default_client
    from cloud_gateway.providers.meta_speech import meta_stack
    from cloud_gateway.voice import VoiceService

    config = load_config(Path(args.config))
    out = Path(args.out or tempfile.mkdtemp(prefix="jana-voice-latency-"))
    out.mkdir(parents=True, exist_ok=True)
    wavs = Path(args.wavs) if args.wavs else out / "wavs"
    await make_wavs(config, wavs)
    gw = Gateway(config, _secrets(config), time.time, default_client, log_alert)
    stack = meta_stack(config, gw.secrets)
    if stack.recognizer is None:
        raise SystemExit("No Meta API key found (keychain jana-meta.cloud-gateway / meta_api_key); nothing was sent.")
    print("loading Kokoro…", flush=True)
    await stack.warm()
    service = VoiceService(gw, stack)
    session = credential(gw)
    gateway = InProcessGateway(config, args.max_usd)
    settings = Settings(worker_pool_size=2, worker_respawn_backoff_s=(0.0,))
    supervisor = WorkerSupervisor(process_factory(settings, scratch_root=out / "scratch"), settings)
    await supervisor.start()
    wanted = set(args.only.split(",")) if args.only else None
    before = gw.inference_budget.snapshot() if gw.inference_budget is not None else None
    results: list[dict[str, Any]] = []
    try:
        for _ in range(args.repeat):
            for question in QUESTIONS:
                if wanted is not None and question.case not in wanted:
                    continue
                if gateway.run_usd() >= args.max_usd:
                    print(f"stopped: spent {gateway.run_usd():.3f} USD", flush=True)
                    break
                result = await run_one(
                    question,
                    read_wav(wavs / f"{question.case}.wav"),
                    service,
                    gateway,
                    session,
                    out,
                    supervisor,
                    Settings().voice_cloud_filler_after_ms,
                )
                results.append(result)
                print(
                    json.dumps(
                        {
                            k: result.get(k)
                            for k in (
                                "case",
                                "speech_stopped_s",
                                "final_transcript_s",
                                "filler_audio_s",
                                "answer_audio_s",
                                "engine_s",
                                "tts_first_s",
                                "transcript",
                            )
                        }
                    ),
                    flush=True,
                )
    finally:
        spark_usd = gateway.run_usd()
        after = gw.inference_budget.snapshot() if gw.inference_budget is not None else None
        await supervisor.close()
        await gateway.close()
        await stack.aclose()
    summary = {
        "turns": len(results),
        "quality_passed": sum(1 for r in results if (r.get("quality") or {}).get("passed")),
        **{
            f"median_{key}": median([r.get(key) for r in results])
            for key in (
                "speech_stopped_s",
                "final_transcript_s",
                "filler_audio_s",
                "answer_audio_s",
                "engine_s",
                "tts_first_s",
            )
        },
        "spark_usd": round(spark_usd, 4),
        "ledger_delta_usd": round(
            (after["spent_usd"] + after["held_usd"]) - (before["spent_usd"] + before["held_usd"]), 4
        )
        if before and after
        else None,
    }
    (out / "report.json").write_text(json.dumps({"summary": summary, "results": results}, indent=1, ensure_ascii=False))
    print(json.dumps(summary, indent=1))
    print(f"report: {out / 'report.json'}")
    return 0 if results and summary["quality_passed"] == len(results) else 1


def _secrets(config: Any) -> Any:
    from cloud_gateway.custody import secret_source

    return secret_source(config)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", default=str(CONFIG))
    parser.add_argument("--only", help="comma-separated case names (phys-car, phys-force, phys-ohm, maths-linear, …)")
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--max-usd", type=float, default=0.5, help="stop starting turns once Spark has spent this")
    parser.add_argument("--wavs", help="a folder of <case>.wav recordings (24 kHz mono PCM16); default: Kokoro's")
    parser.add_argument("--out")
    return asyncio.run(main_async(parser.parse_args()))


if __name__ == "__main__":
    sys.exit(main())
