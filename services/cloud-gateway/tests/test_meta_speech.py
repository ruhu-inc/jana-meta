"""Muse Voice Transcribe as cloud voice's speech to text (SPEC §6.1, JM-D12), against a scripted server: never the
network.

`FakeServer` stands in for `wss://api.meta.ai/v1/asr/realtime` as dev.meta.ai/docs describes it (read 2026-10-27):
the handshake is the first text frame, the acknowledgement is `{"sessionId": …}` with no `type`, audio arrives as
binary PCM16 frames, and a turn is `speechStart`, cumulative `transcript` partials, `speechEnd` and `speechComplete`,
each with `audioProcessedMs`. It hears tone and silence by energy, like `speech_fakes.FakeRecognizer`.

To regenerate the packaged keywords after a glossary change:
    uv run --offline python -c "from test_meta_speech import glossary_terms; print(*glossary_terms(), sep='\\n')"
from `services/cloud-gateway/tests`, below the header of `cloud_gateway/voice_keywords.txt`."""

from __future__ import annotations

import asyncio
import json
import math
import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
import yaml
from cloud_gateway.app import create_app
from cloud_gateway.config import MetaVoice
from cloud_gateway.custody import Secret
from cloud_gateway.providers.base import UpstreamError
from cloud_gateway.providers.meta_speech import MetaRecognizer, glossary_keywords
from cloud_gateway.providers.speech import Heard, SpeechStack
from cloud_gateway.speech_fakes import FakeTts, tone
from gateway_stubs import FakeSecrets, gateway_config
from starlette.websockets import WebSocketDisconnect
from test_gateway_voc28_cloud_voice import HEARD, SAID, answer, connect, opened, scripted_turn, setup, speak, until

GLOSSARY = Path(__file__).resolve().parents[3] / "content" / "agent" / "glossary" / "en.yaml"
KEY = "LLM_1234_test-not-a-key"
WINDOW = 960  # 20 ms


def glossary_terms() -> list[str]:
    terms: dict[str, str] = {}
    for entry in yaml.safe_load(GLOSSARY.read_text())["terms"]:
        terms.setdefault(str(entry["term"]).strip().casefold(), str(entry["term"]).strip())
    return list(terms.values())


def _loud(window: bytes) -> bool:
    samples = memoryview(window).cast("h")
    return math.sqrt(sum(s * s for s in samples) / max(1, len(samples))) / 32768 > 0.02


class FakeSocket:
    def __init__(self, server: FakeServer) -> None:
        self.server = server
        self.sent: list[str | bytes] = []
        self.inbox: asyncio.Queue[Any] = asyncio.Queue()
        self.close_code: int | None = None
        self.close_reason: str | None = None
        self.dead = False  # the server has closed: sends fail at once, before the reader sees the close
        self.audio = bytearray()
        self.turns = 0
        self._pending = bytearray()
        self._ms = 0
        self._loud = 0
        self._quiet = 0
        self._speaking = False

    def push(self, message: dict[str, Any]) -> None:
        self.inbox.put_nowait(json.dumps(message))

    def shut(self, code: int, reason: str = "") -> None:
        self.dead = True
        self.inbox.put_nowait(("close", code, reason))

    async def send(self, data: str | bytes) -> None:
        if self.dead or self.close_code is not None:
            raise ConnectionError("closed")
        self.sent.append(data)
        if isinstance(data, str):
            frame = json.loads(data)
            if frame.get("type") == "endStream":
                self.server.ended += 1
                for message in self.server.flush:
                    self.push(message)
                self.shut(1000)
            elif len(self.sent) == 1 and self.server.ack:
                self.push({"sessionId": f"s{len(self.server.sockets)}"})
            return
        self.audio += data
        self._hear(data)

    def _hear(self, pcm: bytes) -> None:
        """Energy endpointing: speechStart after two loud windows, cumulative partials while speaking, speechEnd
        and speechComplete after 300 ms of quiet."""
        self._pending += pcm
        while len(self._pending) >= WINDOW:
            window = bytes(self._pending[:WINDOW])
            del self._pending[:WINDOW]
            self._ms += 20
            loud = _loud(window)
            if not self._speaking:
                self._loud = self._loud + 1 if loud else 0
                if self._loud >= 2:
                    self._speaking, self._quiet, self.turns = True, 0, self.turns + 1
                    self.push({"type": "speechStart", "turnId": self.turns, "audioProcessedMs": self._ms - 40})
                    words = HEARD.split(" ")
                    for count in range(1, len(words)):  # each partial is the whole turn so far
                        self.push({"type": "transcript", "transcript": " ".join(words[:count]), "final": False,
                                   "audioProcessedMs": self._ms})  # fmt: skip
                continue
            self._quiet = 0 if loud else self._quiet + 20
            if self._quiet >= 300:
                self._speaking, self._loud = False, 0
                self.push({"type": "speechEnd", "turnId": self.turns, "audioProcessedMs": self._ms - self._quiet})
                self.push({"type": "speechComplete", "turnId": self.turns, "transcript": HEARD,
                           "audioProcessedMs": self._ms})  # fmt: skip
                closing = self.server.close_after.get(len(self.server.sockets) - 1)
                if closing is not None and self is self.server.sockets[-1]:
                    self.shut(*closing)

    async def recv(self) -> str:
        item = await self.inbox.get()
        if isinstance(item, tuple):
            self.close_code, self.close_reason = item[1], item[2]
            raise ConnectionError("closed")
        return item  # type: ignore[no-any-return]

    async def close(self) -> None:
        if self.close_code is None:
            self.close_code = 1000
            self.inbox.put_nowait(("close", 1000, ""))
        self.server.closed += 1


class FakeServer:
    def __init__(self, *, ack: bool = True) -> None:
        self.ack = ack
        self.sockets: list[FakeSocket] = []
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.close_after: dict[int, tuple[int, str]] = {}  # stream index -> its close after its first turn
        self.flush: list[dict[str, Any]] = []  # what the server sends after endStream, before its 1000 close
        self.ended = 0
        self.closed = 0

    async def connect(self, url: str, **options: Any) -> FakeSocket:
        self.calls.append((url, options))
        socket = FakeSocket(self)
        self.sockets.append(socket)
        return socket

    def handshakes(self) -> list[dict[str, Any]]:
        return [json.loads(s.sent[0]) for s in self.sockets if s.sent and isinstance(s.sent[0], str)]


def recognizer(server: FakeServer, **voice: Any) -> MetaRecognizer:
    return MetaRecognizer(MetaVoice(**voice), Secret(KEY), connect=server.connect)


async def _collect(stream: Any, into: list[Heard]) -> None:
    async for heard in stream.events():
        into.append(heard)


# --- the handshake ---------------------------------------------------------------------------------------------------


def test_handshake_frame_carries_the_key_and_session_settings() -> None:
    server = FakeServer()

    async def run() -> None:
        stream = await recognizer(server).open("en")
        await stream.close()

    asyncio.run(run())
    ((url, options),) = server.calls
    assert url == "wss://api.meta.ai/v1/asr/realtime"  # no key in the URL
    assert "additional_headers" not in options  # and none in a header: the endpoint ignores it
    frame = server.handshakes()[0]
    assert frame["authorization"] == {"accessToken": "Bearer " + KEY}
    assert {k: frame[k] for k in ("model", "audioEncoding", "mode", "partialMode", "emitAudioProgress")} == {
        "model": "muse-voice-transcribe-1.0", "audioEncoding": "PCM_24KHZ", "mode": "ENDPOINTING",
        "partialMode": "CUMULATIVE", "emitAudioProgress": False}  # fmt: skip
    assert frame["languageBias"] == ["English"]
    fitting = [word for word in glossary_keywords() if len(word) <= 30][:500]  # Meta's limits (measured)
    assert frame["keywords"] == fitting and "potential difference" in frame["keywords"]
    assert server.sockets[0].sent[-1] == json.dumps({"type": "endStream"})  # close ends the session


def test_keywords_are_capped_and_configurable() -> None:
    server = FakeServer()

    async def run() -> None:
        await (await recognizer(server, keywords=["ohm", "ohm", "joule"], keywords_max=1).open("en")).close()

    asyncio.run(run())
    assert server.handshakes()[0]["keywords"] == ["ohm"]


def test_packaged_keywords_fit_meta_limit() -> None:
    """Meta refuses more than 500 keywords (measured live); the packaged list is trimmed to them."""
    server = FakeServer()

    async def run() -> None:
        await (await recognizer(server).open("en")).close()

    asyncio.run(run())
    sent = server.handshakes()[0]["keywords"]
    assert len(glossary_keywords()) > 500 and len(sent) == 500 and max(map(len, sent)) <= 30


def test_packaged_keywords_are_the_glossary_terms() -> None:
    assert glossary_keywords() == glossary_terms()


def test_no_audio_before_the_acknowledgement() -> None:
    server = FakeServer(ack=False)

    async def run() -> None:
        opening = asyncio.create_task(recognizer(server).open("en"))
        await asyncio.sleep(0.1)
        assert not opening.done()  # waiting for the acknowledgement
        socket = server.sockets[0]
        assert len(socket.sent) == 1 and isinstance(socket.sent[0], str)  # the handshake, and nothing else
        socket.push({"sessionId": "s1"})
        stream = await opening
        await stream.send(b"\1\0" * 2400)
        assert isinstance(socket.sent[1], bytes)  # audio as binary PCM frames, after the acknowledgement
        await stream.close()

    asyncio.run(run())


def test_a_refused_or_silent_handshake_opens_nothing() -> None:
    async def refused() -> None:
        server = FakeServer(ack=False)
        opening = asyncio.create_task(recognizer(server).open("en"))
        await asyncio.sleep(0.05)
        server.sockets[0].push({"type": "error", "message": "bad key", "sessionId": ""})
        with pytest.raises(UpstreamError) as failure:
            await opening
        assert failure.value.reason == "upstream_auth" and server.closed == 1

    async def invalid() -> None:
        server = FakeServer(ack=False)
        opening = asyncio.create_task(recognizer(server).open("en"))
        await asyncio.sleep(0.05)
        server.sockets[0].push({"type": "error", "message": "Too many ASR keywords: received 1368, maximum is 500",
                                "sessionId": "s", "errorType": "invalid_request_error"})  # fmt: skip
        with pytest.raises(UpstreamError) as failure:
            await opening
        assert failure.value.reason == "format_error"  # not the key's fault

    async def silent() -> None:
        server = FakeServer(ack=False)
        with pytest.raises(UpstreamError) as failure:
            await recognizer(server, handshake_timeout_s=0.5).open("en")
        assert failure.value.reason == "network_unavailable" and server.closed == 1

    async def limited() -> None:
        server = FakeServer(ack=False)
        rec = recognizer(server)
        opening = asyncio.create_task(rec.open("en"))
        await asyncio.sleep(0.05)
        server.sockets[0].shut(1013)
        with pytest.raises(UpstreamError) as failure:
            await opening
        assert failure.value.reason == "rate_limit" and rec.retry_at > rec.clock()  # backs off before retrying

    for case in (refused, invalid, silent, limited):
        asyncio.run(case())


# --- events ----------------------------------------------------------------------------------------------------------


def test_events_map_to_heard_and_partials_are_cumulative() -> None:
    server = FakeServer()

    async def run() -> list[Heard]:
        stream = await recognizer(server).open("en")
        heard: list[Heard] = []
        reader = asyncio.create_task(_collect(stream, heard))
        socket = server.sockets[0]
        for message in [
            {"type": "speechStart", "turnId": 1, "audioProcessedMs": 1200},
            {"type": "transcript", "transcript": "how is", "final": False, "audioProcessedMs": 2000},
            {"type": "audioProgress", "audioProcessedMs": 2200},
            {"type": "transcript", "transcript": "how is the", "final": False, "audioProcessedMs": 2400},
            {"type": "speechEnd", "turnId": 1, "audioProcessedMs": 3600},
            {"type": "speechComplete", "turnId": 1, "transcript": "How is the weather?", "audioProcessedMs": 3600},
            {"type": "somethingNew"},
        ]:
            socket.push(message)
        await asyncio.sleep(0.05)
        await stream.close()
        await reader
        return heard

    heard = asyncio.run(run())
    assert [(h.kind, h.offset_ms, h.text) for h in heard] == [
        ("begin", 1200, ""), ("partial", 2000, "how is"), ("partial", 2400, "how is the"), ("end", 3600, ""),
        ("final", 3600, "How is the weather?")]  # fmt: skip


def test_close_takes_what_the_server_flushes_after_end_stream() -> None:
    server = FakeServer()
    server.flush = [{"type": "speechComplete", "turnId": 1, "transcript": "last words", "audioProcessedMs": 900}]

    async def run() -> list[Heard]:
        stream = await recognizer(server).open("en")
        heard: list[Heard] = []
        reader = asyncio.create_task(_collect(stream, heard))
        await stream.close()
        await reader
        return heard

    assert [(h.kind, h.text) for h in asyncio.run(run())] == [("final", "last words")]
    assert server.ended == 1


@pytest.mark.parametrize(("code", "reason", "backs_off"), [
    (1011, "Max session duration reached", False), (1011, "backend failure", True), (1013, "", True)])  # fmt: skip
def test_session_cap_and_rate_limit_end_the_stream_for_a_reconnect(code: int, reason: str, backs_off: bool) -> None:
    server = FakeServer()

    async def run() -> MetaRecognizer:
        rec = recognizer(server)
        stream = await rec.open("en")
        server.sockets[0].shut(code, reason)
        await _collect(stream, [])  # ends without an error: the voice connection opens the next stream
        return rec

    rec = asyncio.run(run())
    assert (rec.retry_at > 0) is backs_off


def test_a_policy_close_is_an_error() -> None:
    server = FakeServer()

    async def run() -> None:
        stream = await recognizer(server).open("en")
        server.sockets[0].shut(1008, "backlog")
        await _collect(stream, [])

    with pytest.raises(UpstreamError) as failure:
        asyncio.run(run())
    assert failure.value.reason == "format_error"


# --- pacing ----------------------------------------------------------------------------------------------------------


def test_audio_is_paced_at_most_ahead_of_real_time() -> None:
    server = FakeServer()

    async def run() -> float:
        stream = await recognizer(server, ahead_ms=500).open("en")
        started = time.monotonic()
        await stream.send(bytes(48 * 1000))  # a second of held audio, sent at once
        elapsed = time.monotonic() - started
        await stream.close()
        return elapsed

    assert asyncio.run(run()) >= 0.45  # one second may run at most half a second ahead


def test_gaps_are_filled_with_silence_and_offsets_skip_it() -> None:
    server = FakeServer()

    async def run() -> tuple[Any, list[Heard]]:
        stream = await recognizer(server, pad_after_ms=100).open("en")
        heard: list[Heard] = []
        reader = asyncio.create_task(_collect(stream, heard))
        await stream.send(b"\1\0" * 2400)  # 100 ms of audio, then nothing from the device
        await asyncio.sleep(0.6)
        await stream.send(b"\1\0" * 2400)
        processed = stream.sent_ms  # the stream's clock: both pieces of audio and the silence between them
        server.sockets[0].push({"type": "speechEnd", "turnId": 1, "audioProcessedMs": int(processed)})
        await asyncio.sleep(0.05)
        await stream.close()
        await reader
        return stream, heard

    stream, heard = asyncio.run(run())
    assert stream.padded_bytes >= 48 * 300  # the gap reached the server as silence, at real time
    assert bytes(server.sockets[0].audio).count(b"\0\0" * 2400)
    assert heard[0].offset_ms == pytest.approx(200, abs=2)  # the device's 200 ms of audio, silence not counted


# --- in the voice connection -----------------------------------------------------------------------------------------


class PricedTts(FakeTts):
    """A verbatim voice priced by the character (Kokoro costs nothing, so a cap needs a priced voice to be spent)."""

    def million_chars_usd(self) -> float:
        return 30.0


def meta_setup(tmp_path: Path, server: FakeServer, tts: FakeTts | None = None,
               **overrides: Any) -> tuple[Any, Any, Any]:  # fmt: skip
    stack = SpeechStack(recognizer=recognizer(server), live=None, tts=tts or FakeTts())
    client, device, _, _ = setup(tmp_path, (stack, stack.recognizer, None, stack.tts), **overrides)
    return client, device, stack


def test_a_voice_turn_runs_on_voice_transcribe_with_the_verbatim_voice(tmp_path: Path) -> None:
    server = FakeServer()
    client, device, stack = meta_setup(tmp_path, server)
    with client, connect(client, device) as ws:
        opened(ws)
        seen = scripted_turn(ws)  # the transcript is speechComplete's text, not the partials appended
    delta = next(e for e in seen if e["type"] == "conversation.item.input_audio_transcription.delta")
    assert delta["delta"] == HEARD
    done = next(e for e in seen if e["type"] == "response.done")
    assert json.loads(done["response"]["metadata"]["speech_to_speech.turn_latency"])["voice_out"] == "tts"
    assert stack.tts.texts == [s.strip() for s in SAID]
    assert server.ended == len(server.sockets) == 1  # one session, ended with endStream


@pytest.mark.parametrize("closing", [(1011, "Max session duration reached"), (1013, "")])
def test_the_connection_reconnects_after_the_session_cap_or_a_rate_limit(tmp_path: Path, closing: Any) -> None:
    server = FakeServer()
    server.close_after[0] = closing
    client, device, _ = meta_setup(tmp_path, server)
    with client, connect(client, device) as ws:
        opened(ws)
        scripted_turn(ws)
        seen = scripted_turn(ws)  # heard on the next stream; audio held while it opened
    assert len(server.sockets) == 2 and server.sockets[0].close_code == closing[0]
    assert any(e["type"] == "response.done" for e in seen)


class SlowTts(FakeTts):
    async def synthesize(self, text: str) -> AsyncIterator[bytes]:
        self.texts.append(text)
        for _ in range(20):
            await asyncio.sleep(0.05)
            yield tone(100)


def test_speech_start_barges_in(tmp_path: Path) -> None:
    """Barge-in stays the gateway's: Voice Transcribe's speechStart cancels the reply being read."""
    server = FakeServer()
    stack = SpeechStack(recognizer=recognizer(server), live=None, tts=SlowTts())
    client, device, _, _ = setup(tmp_path, (stack, stack.recognizer, None, stack.tts))
    with client, connect(client, device) as ws:
        opened(ws)
        seen: list[dict[str, Any]] = []
        speak(ws)
        request = until(ws, "jana.voice_llm.request", seen)
        answer(ws, request, ["One two three four five six seven eight nine ten. "])
        created = until(ws, "response.created", seen)
        until(ws, "response.output_audio.delta", seen)
        speak(ws, 200, 0)  # the student talks over the reply
        done = until(ws, "response.done", seen)
    assert done["response"]["id"] == created["response"]["id"]
    assert done["response"]["status"] == "cancelled"
    assert done["response"]["status_details"]["reason"] == "turn_detected"


def test_default_stack_is_voice_transcribe_and_kokoro(tmp_path: Path) -> None:
    """Voice Transcribe hears and Kokoro reads (SPEC §6.4), with no Live voice; Magpie only when configured, in dev."""
    from cloud_gateway.providers.kokoro_speech import KokoroSynthesizer
    from cloud_gateway.providers.magpie_speech import MagpieSynthesizer

    config = gateway_config(tmp_path, voice_enabled=True)
    app = create_app(config, secrets=FakeSecrets({"meta_api_key": KEY}))
    stack = app.state.voice.stack
    assert isinstance(stack.recognizer, MetaRecognizer) and stack.live is None
    assert isinstance(stack.tts, KokoroSynthesizer) and stack.tts.voice == "kokoro-82m/af_heart"
    with pytest.raises(ImportError):
        import cloud_gateway.providers.google_speech  # noqa: F401 -- JM-D14: no Google voice remains
    config = gateway_config(tmp_path / "dev", environment="dev", voice_enabled=True, voice_tts={"engine": "magpie"})
    stack = create_app(config, secrets=FakeSecrets({"meta_api_key": KEY})).state.voice.stack
    assert isinstance(stack.tts, MagpieSynthesizer)
    with pytest.raises(ValueError, match="development voice only"):
        gateway_config(tmp_path / "staging", voice_enabled=True, voice_tts={"engine": "magpie"})
    stack = create_app(
        gateway_config(tmp_path / "nokey", voice_enabled=True), secrets=FakeSecrets({})
    ).state.voice.stack
    assert stack.recognizer is None  # no Meta key, no speech to text


def test_voice_transcribe_is_priced_per_second() -> None:
    rec = recognizer(FakeServer())
    assert rec.minute_usd() * 60 == pytest.approx(0.18)  # $0.18 per audio hour


# --- every turn re-checks the credential and the quotas (§6.1 review finding) ----------------------------------------


def test_a_revoked_credential_ends_the_connection_at_the_next_turn(tmp_path: Path) -> None:
    server = FakeServer()
    client, device, _ = meta_setup(tmp_path, server)
    with client, connect(client, device) as ws:
        opened(ws)
        scripted_turn(ws)
        assert client.app.state.gateway.auth.revoke(device.credential_id)
        seen: list[dict[str, Any]] = []
        speak(ws)
        error = until(ws, "error", seen)
        with pytest.raises(WebSocketDisconnect) as closed:
            until(ws, "never", seen)
    assert error["error"]["code"] == "unauthorized" and closed.value.code == 4401
    assert not any(e["type"] == "jana.voice_llm.request" for e in seen)  # the turn never reached the device


def test_a_spent_cap_ends_the_connection_at_the_next_turn(tmp_path: Path) -> None:
    server = FakeServer()
    quotas = {"device_burst": 1000, "licence_burst": 10000, "device_daily_spend_usd": 0.000001}
    client, device, _ = meta_setup(tmp_path, server, PricedTts(), quotas=quotas)
    with client, connect(client, device) as ws:
        opened(ws)
        scripted_turn(ws)  # admitted with nothing spent; its spoken sentences are metered
        seen: list[dict[str, Any]] = []
        speak(ws)
        error = until(ws, "error", seen)
        with pytest.raises(WebSocketDisconnect) as closed:
            until(ws, "never", seen)
    assert error["error"]["code"] == "quota_exceeded" and closed.value.code == 4429


def test_a_directive_turn_is_re_checked_too(tmp_path: Path) -> None:
    server = FakeServer()
    client, device, _ = meta_setup(tmp_path, server)
    with client, connect(client, device) as ws:
        opened(ws)
        assert client.app.state.gateway.auth.revoke(device.credential_id)
        ws.send_json({"type": "conversation.item.create", "item": {"type": "message", "role": "user", "content": [
            {"type": "input_text", "text": "jana-speak: utt_" + "0" * 26}]}})  # fmt: skip
        ws.send_json({"type": "response.create"})
        seen: list[dict[str, Any]] = []
        error = until(ws, "error", seen)
    assert error["error"]["code"] == "unauthorized"
    assert not any(e["type"] == "jana.voice_llm.request" for e in seen)


# --- the deployment inference budget ----------------------------------------------------------------------------------


def test_voice_charges_are_reserved_and_settled_under_the_budget(tmp_path: Path) -> None:
    server = FakeServer()
    quotas = {"device_burst": 1000, "licence_burst": 10000, "deployment_total_spend_usd": 5.0}
    client, device, stack = meta_setup(tmp_path, server, quotas=quotas)
    with client:
        budget = client.app.state.gateway.inference_budget
        with connect(client, device) as ws:
            opened(ws)
            seen: list[dict[str, Any]] = []
            speak(ws)
            request = until(ws, "jana.voice_llm.request", seen)
            assert budget.snapshot()["held_usd"] == pytest.approx(0.183, abs=0.001)  # the stream's longest bill
            answer(ws, request, SAID)
            done = until(ws, "response.done", seen)
        deadline = time.monotonic() + 5
        while budget.snapshot()["held_usd"] and time.monotonic() < deadline:  # the gateway closes the stream
            time.sleep(0.05)
        snapshot = budget.snapshot()
    assert snapshot["held_usd"] == 0 and snapshot["spent_usd"] > 0  # settled with what was used
    assert stack.tts.texts  # the synthesizer read the reply (a Live voice is never used under a budget)
    assert json.loads(done["response"]["metadata"]["speech_to_speech.turn_latency"])["voice_out"] == "tts"


def test_a_spent_budget_refuses_speech_to_text(tmp_path: Path) -> None:
    server = FakeServer()
    quotas = {"device_burst": 1000, "licence_burst": 10000, "deployment_total_spend_usd": 0.01}
    client, device, _ = meta_setup(tmp_path, server, quotas=quotas, voice_prewarm_s=0.01)
    with client, connect(client, device) as ws:
        seen: list[dict[str, Any]] = []
        error = until(ws, "error", seen)
    assert error["error"]["code"] == "quota_exceeded" and not server.sockets  # nothing opened, nothing billed


def test_dev_config_switches_voice_on_with_kokoro(tmp_path: Path) -> None:
    from cloud_gateway.config import load_config

    config = load_config(Path(__file__).parents[1] / "deploy" / "meta-dev.toml", storage_dir=tmp_path)
    assert config.voice_enabled and config.voice_tts.engine == "kokoro"
    assert config.quotas.deployment_daily_spend_usd is not None  # voice runs under the budget
