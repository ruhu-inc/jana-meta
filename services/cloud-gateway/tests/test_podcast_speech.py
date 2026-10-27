"""Podcast narration (JM-D13, SPEC §6.4): the gateway's own verbatim voice (Kokoro-82M, Apache-2.0) reads each
passage, never a hosted trial. No-network contract, durable limits and no content in storage; not a quality check."""

import asyncio
import base64
import io
import wave
from pathlib import Path

import pytest
from cloud_gateway.podcast_speech import PodcastSpeech, SpeechError, validate_audio
from cloud_gateway.speech_fakes import FakeTts
from gateway_stubs import Device, gateway_config, harness

TEXT = "CANARY: Enzymes are biological catalysts."
DEPLOY = Path(__file__).resolve().parents[1] / "deploy"


def wav(frames=2400):
    output = io.BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setparams((1, 2, 24000, 0, "NONE", "not compressed"))
        audio.writeframes(b"\x01\x00" * frames)
    return output.getvalue()


class FailingTts(FakeTts):
    async def synthesize(self, text):
        self.texts.append(text)
        raise RuntimeError("synthetic worker failure")
        yield b""


def setup(tmp, tts=None, **limits):
    h = harness(gateway_config(tmp, podcast_speech={"enabled": True, **limits}))
    service = h.client._transport.app.state.podcast_speech
    voice = FakeTts() if tts is None else tts
    service.tts = lambda: voice
    return h, service, voice


def body(index=0):
    return {"request_id": "cli_" + str(index) * 26, "text": TEXT, "voice_index": 0}


def test_podcast_is_read_by_the_gateways_own_voice_with_no_content_in_storage(tmp_path):
    async def run():
        h, _, voice = setup(tmp_path)
        assert (await h.client.get("/v1/podcast/voice")).status_code == 401
        device = Device()
        await device.login(h.client)
        status = await h.client.get("/v1/podcast/voice", headers=device.headers())
        assert status.json() == {"enabled": True, "configured": True, "provider": "kokoro"}
        reply = await h.client.post("/v1/podcast/speech", json=body(), headers=device.headers())
        assert reply.status_code == 200, reply.text
        audio = base64.b64decode(reply.json()["audio_base64"])
        validate_audio(audio)
        with wave.open(io.BytesIO(audio)) as read:
            assert read.getframerate() == 24000 and read.getnframes() == 2 * 24 * 150
        assert reply.json()["voice"] == "kokoro-82m/af_heart"
        assert reply.headers["cache-control"] == "no-store"
        assert voice.texts == [TEXT]
        gw = h.client._transport.app.state.gateway
        assert gw.store._db.execute("SELECT characters,state FROM podcast_speech_receipts").fetchone() == (
            len(TEXT),
            "completed",
        )
        for line in gw.store._db.iterdump():
            assert TEXT not in line and "RIFF" not in line

    asyncio.run(run())


def test_without_a_voice_the_podcast_says_it_is_not_configured(tmp_path):
    async def run():
        h, service, _ = setup(tmp_path)
        service.tts = lambda: None
        device = Device()
        await device.login(h.client)
        status = await h.client.get("/v1/podcast/voice", headers=device.headers())
        assert status.json()["configured"] is False
        reply = await h.client.post("/v1/podcast/speech", json=body(), headers=device.headers())
        assert reply.status_code == 503 and reply.json()["error"]["code"] == "neural_speech_not_configured"

    asyncio.run(run())


@pytest.mark.parametrize(
    "change",
    [
        {"nvidia_consent": True},
        {"voice_index": 2},
        {"voice_index": True},
        {"text": ""},
        {"text": "x" * 601},
        {"profile_id": "private"},
        {"request_id": "invalid"},
    ],
)
def test_invalid_requests_never_reach_the_voice(tmp_path, change):
    async def run():
        h, _, voice = setup(tmp_path)
        device = Device()
        await device.login(h.client)
        reply = await h.client.post("/v1/podcast/speech", json={**body(), **change}, headers=device.headers())
        assert reply.status_code != 200 and voice.texts == []

    asyncio.run(run())


def test_limits_and_duplicate_protection_survive_service_restart(tmp_path):
    async def run():
        h, service, voice = setup(tmp_path, daily_characters=len(TEXT), total_characters=2 * len(TEXT))
        device = Device()
        await device.login(h.client)
        assert (await h.client.post("/v1/podcast/speech", json=body(), headers=device.headers())).status_code == 200
        gw = h.client._transport.app.state.gateway
        restarted = PodcastSpeech(gw, service.tts)
        with pytest.raises(SpeechError, match="already_sent"):
            await restarted.synthesize(device.credential_id, body())
        with pytest.raises(SpeechError, match="limit"):
            await service.synthesize(device.credential_id, body(1))
        h.clock.now += 86400
        assert len(await service.synthesize(device.credential_id, body(1))) > 44
        h.clock.now += 86400
        with pytest.raises(SpeechError, match="limit"):
            await service.synthesize(device.credential_id, body(2))
        assert len(voice.texts) == 2

    asyncio.run(run())


def test_a_failed_reading_remains_counted_and_cannot_repeat(tmp_path):
    async def run():
        h, _, voice = setup(tmp_path, tts=FailingTts(), daily_requests=1)
        device = Device()
        await device.login(h.client)
        for item in (body(), body(), body(1)):
            result = await h.client.post("/v1/podcast/speech", json=item, headers=device.headers())
            assert result.status_code != 200
        assert len(voice.texts) == 1
        gw = h.client._transport.app.state.gateway
        assert gw.store._db.execute("SELECT characters,state FROM podcast_speech_receipts").fetchone() == (
            len(TEXT),
            "held",
        )

    asyncio.run(run())


@pytest.mark.parametrize("audio", [b"html error page", b"RIFF" + b"0" * 100, wav()[:-20]])
def test_invalid_audio_is_withheld(audio):
    with pytest.raises(SpeechError, match="invalid_audio"):
        validate_audio(audio)


def test_the_development_config_never_turns_on_a_hosted_podcast_trial():
    text = (DEPLOY / "meta-dev.toml").read_text()
    assert "free_prototyping" not in text and "NVIDIA" not in text
    assert 'engine = "magpie"' not in text
