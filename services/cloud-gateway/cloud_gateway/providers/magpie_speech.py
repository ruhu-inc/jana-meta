"""NVIDIA Magpie as cloud voice's verbatim voice, for development only (SPEC §6.2, §6.4).

The API-catalog trial forbids distributing its audio, so nothing judges hear may come from here: the configuration
refuses `voice_meta.tts = "magpie"` outside the dev environment, and the demo uses Kokoro. One request per accepted
sentence (Magpie is not streaming); its 22.05 kHz WAV is resampled to the bridge's 24 kHz. Text and audio are never
logged."""

from __future__ import annotations

import array
import io
import sys
import wave
from collections.abc import AsyncIterator

import httpx

from cloud_gateway.config import VoiceTts
from cloud_gateway.custody import Secret
from cloud_gateway.podcast_speech import MAX_AUDIO, SpeechError, validate_audio
from cloud_gateway.providers.base import UpstreamError

BASE = "https://877104f7-e885-42b9-8de8-f6e4c6303969.invocation.api.nvcf.nvidia.com"
SOURCE_RATE, RATE = 22_050, 24_000
CHUNK = 12_000 * 2  # half a second of output per yield
MAX_TEXT = 600  # the function's own bound


async def magpie_wav(client: httpx.AsyncClient, key: str, text: str, voice: str) -> bytes:
    """One Magpie synthesis on the API-catalog function: a validated 22.05 kHz mono PCM16 WAV of exactly `text`."""
    try:
        async with client.stream(
            "POST",
            BASE + "/v1/audio/synthesize",
            headers={"authorization": "Bearer " + key},
            files={
                k: (None, v)
                for k, v in {
                    "text": text,
                    "language": "en-US",
                    "voice": voice,
                    "encoding": "LINEAR_PCM",
                    "sample_rate_hz": "22050",
                }.items()
            },
        ) as reply:
            if reply.status_code in (401, 403):
                raise SpeechError("neural_speech_key_rejected")
            if reply.status_code == 429:
                raise SpeechError("neural_speech_limit")
            if reply.status_code != 200:
                raise SpeechError("neural_speech_unavailable")
            data, size = [], 0
            async for part in reply.aiter_bytes():
                size += len(part)
                if size > MAX_AUDIO:
                    raise SpeechError("neural_speech_invalid_audio")
                data.append(part)
            audio = b"".join(data)
    except httpx.HTTPError:
        raise SpeechError("neural_speech_unavailable") from None
    validate_audio(audio, SOURCE_RATE)
    return audio


def resample(pcm: bytes, source: int = SOURCE_RATE, target: int = RATE) -> bytes:
    """Mono PCM16 by linear interpolation (speech, upsampling by 160/147: no audible aliasing to filter)."""
    samples = array.array("h", pcm[: len(pcm) - len(pcm) % 2])
    if sys.byteorder == "big":
        samples.byteswap()
    count = len(samples)
    if count == 0:
        return b""
    length = (count * target) // source
    out = array.array("h", bytes(2 * length))
    step = source / target
    last = count - 1
    for index in range(length):
        position = index * step
        left = int(position)
        if left >= last:
            out[index] = samples[last]
            continue
        fraction = position - left
        a, b = samples[left], samples[left + 1]
        out[index] = int(a + (b - a) * fraction)
    if sys.byteorder == "big":
        out.byteswap()
    return out.tobytes()


def _reason(error: SpeechError) -> str:
    return {"neural_speech_key_rejected": "upstream_auth", "neural_speech_limit": "rate_limit"}.get(
        error.reason, "server_error")  # fmt: skip


class MagpieSynthesizer:
    def __init__(self, voice: VoiceTts, key: Secret | None, client: httpx.AsyncClient | None = None) -> None:
        self.settings, self.key = voice, key
        self.voice = voice.magpie_voice
        self.client = client or httpx.AsyncClient(trust_env=False, follow_redirects=False, timeout=30)

    def million_chars_usd(self) -> float:
        return 0.0  # the trial is free; it is bounded by NVIDIA's own rate limits

    async def warm(self) -> None:
        return None

    async def synthesize(self, text: str) -> AsyncIterator[bytes]:
        if not text or len(text) > MAX_TEXT:
            raise UpstreamError("format_error", "speech text out of bounds")
        if self.key is None:
            raise UpstreamError("upstream_auth", "no NVIDIA key", extra={"unbilled": True})
        try:
            try:
                audio = await magpie_wav(self.client, self.key.reveal(), text, self.settings.magpie_voice)
            except SpeechError as error:
                if error.reason != "neural_speech_unavailable" or not self.settings.magpie_fallback_voice:
                    raise
                audio = await magpie_wav(self.client, self.key.reveal(), text, self.settings.magpie_fallback_voice)
        except SpeechError as error:
            raise UpstreamError(_reason(error), "synthesis failed") from None
        with wave.open(io.BytesIO(audio), "rb") as source:
            pcm = resample(source.readframes(source.getnframes()))
        for at in range(0, len(pcm), CHUNK):
            yield pcm[at : at + CHUNK]

    async def aclose(self) -> None:
        await self.client.aclose()
