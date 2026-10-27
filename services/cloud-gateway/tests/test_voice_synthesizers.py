"""Cloud voice's verbatim voice (SPEC §6.4): Kokoro through its worker process (a scripted stand-in here; the real
worker runs only with `JANA_LIVE_KOKORO=1`)."""

from __future__ import annotations

import asyncio
import contextlib
import os
import sys
from pathlib import Path

import pytest
from cloud_gateway.config import VoiceTts
from cloud_gateway.providers.base import UpstreamError
from cloud_gateway.providers.kokoro_speech import KokoroSynthesizer, worker_command, worker_env

# A worker speaking the real one's frames: ready, then for each request the text's bytes as two even "PCM" chunks.
WORKER = r"""
import json, struct, sys
out = sys.stdout.buffer
def frame(i, n, b=b""):
    out.write(struct.pack(">Ii", i, n) + b); out.flush()
frame(0, -1)
for line in sys.stdin:
    request = json.loads(line)
    text = request["text"].encode()
    if b"FAIL" in text:
        frame(request["id"], -2); continue
    if b"DIE" in text:
        sys.exit(3)
    pcm = text + (b"\0" if len(text) % 2 else b"")
    for _ in range(int(request["text"].count("LONG")) * 20 + 2):
        frame(request["id"], len(pcm), pcm)
    frame(request["id"], -1)
"""


def kokoro() -> KokoroSynthesizer:
    return KokoroSynthesizer(VoiceTts(), command=[sys.executable, "-c", WORKER], env={"PATH": os.environ["PATH"]})


async def read(tts: KokoroSynthesizer, text: str) -> list[bytes]:
    return [chunk async for chunk in tts.synthesize(text)]


def test_kokoro_reads_exactly_the_text_and_meters_nothing():
    tts = kokoro()

    async def run() -> list[list[bytes]]:
        await tts.warm()
        try:
            return [await read(tts, "Good start."), await read(tts, "What is its starting speed?")]
        finally:
            await tts.aclose()

    first, second = asyncio.run(run())
    assert first == [b"Good start.\0"] * 2 and second == [b"What is its starting speed?\0"] * 2
    assert tts.voice == "kokoro-82m/af_heart" and tts.million_chars_usd() == 0.0


def test_kokoro_reads_the_keyed_filler_once_at_warm_up():
    tts = kokoro()

    async def run() -> tuple[list[bytes], int]:
        await tts.warm()
        asked = tts._next
        try:
            return await read(tts, "Let me work that out."), tts._next - asked
        finally:
            await tts.aclose()

    audio, requests = asyncio.run(run())
    assert audio == [b"Let me work that out.\0"] * 2 and requests == 0  # replayed: no synthesis on the turn


def test_kokoro_skips_the_rest_of_a_reply_a_barge_in_abandoned():
    tts = kokoro()

    async def run() -> list[bytes]:
        try:
            async with contextlib.aclosing(tts.synthesize("LONG LONG reply")) as stream:  # type: ignore[type-var]
                async for _ in stream:
                    break  # the student spoke: the reply is cancelled after its first audio
            return await read(tts, "Next.")
        finally:
            await tts.aclose()

    assert asyncio.run(run()) == [b"Next.\0"] * 2  # never a frame of the abandoned reply


def test_kokoro_failures_are_reason_codes_and_the_worker_restarts():
    tts = kokoro()

    async def run() -> list[bytes]:
        try:
            with pytest.raises(UpstreamError) as failed:
                await read(tts, "FAIL")
            assert failed.value.reason == "server_error"
            with pytest.raises(UpstreamError) as died:
                await read(tts, "DIE")
            assert died.value.reason == "server_error"
            with pytest.raises(UpstreamError):
                await read(tts, "")
            return await read(tts, "Back.")  # a fresh worker
        finally:
            await tts.aclose()

    assert asyncio.run(run()) == [b"Back.\0"] * 2


def test_kokoro_worker_runs_the_speech_runtime_without_secrets(monkeypatch):
    monkeypatch.setenv("META_API_KEY", "LLM_1_secret-not-real")
    command, env = worker_command(VoiceTts()), worker_env()
    assert command[1] == "-P" and command[2].endswith("cloud_gateway/kokoro_worker.py")
    assert command[3:] == [str(Path("~/.cache/jana-speech/packs/sp.en.0_1/models/kokoro-82m").expanduser()),
                           "af_heart", "0", "4"]  # fmt: skip
    assert "META_API_KEY" not in env and not any("secret" in value for value in env.values())
    assert env["HF_HUB_OFFLINE"] == "1"


@pytest.mark.skipif(os.environ.get("JANA_LIVE_KOKORO") != "1", reason="loads the real Kokoro (JANA_LIVE_KOKORO=1)")
def test_kokoro_live_worker_speaks_24khz_pcm():
    tts = KokoroSynthesizer(VoiceTts())

    async def run() -> list[bytes]:
        try:
            await tts.warm()
            return await read(tts, "Good start, the car begins at rest. What is its starting speed?")
        finally:
            await tts.aclose()

    audio = b"".join(asyncio.run(run()))
    assert len(audio) % 2 == 0 and 48_000 * 2 < len(audio) < 48_000 * 10  # 2 to 10 s of 24 kHz PCM16
