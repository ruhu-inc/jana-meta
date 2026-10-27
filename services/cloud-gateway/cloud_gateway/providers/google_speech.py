"""Cloud Text-to-Speech streaming synthesis (VOC-28, D124): cloud voice's interim verbatim voice, configured by
`voice_google_tts`, until the Magpie synthesizer (SPEC §6.2) replaces it and JM-D14 removes this module. Speech to
text is Muse Voice Transcribe (`meta_speech.py`).

A gRPC-only streaming API, reached through Google's client library (the `google-voice` extra, imported only when a
project is configured), with the attached service identity; there is no documented API-key path. The text is never
logged; failures become `UpstreamError` with a reason code only."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator
from typing import Any

from cloud_gateway.config import GoogleTts
from cloud_gateway.providers.base import UpstreamError

SCOPE = "https://www.googleapis.com/auth/cloud-platform"
RATE = 24_000
MAX_TEXT = 2000


def _credentials() -> Any:
    """The attached identity (the metadata server on Google Cloud; local application default credentials when the
    live smoke test runs on a developer's machine)."""
    import google.auth

    credentials, _ = google.auth.default(scopes=[SCOPE])
    return credentials


class ChirpSynthesizer:
    """Chirp 3 HD streaming synthesis: plain text (no SSML, no markup), read as given."""

    def __init__(self, voice: GoogleTts, language: str = "en") -> None:
        self.settings = voice
        self.voice = voice.tts_voices.get(language) or next(iter(voice.tts_voices.values()))
        self._client: Any = None

    def million_chars_usd(self) -> float:
        return self.settings.tts_million_chars_usd

    def client(self) -> Any:
        if self._client is None:
            from google.cloud import texttospeech

            host = ("texttospeech.googleapis.com" if self.settings.tts_location == "global"
                    else f"{self.settings.tts_location}-texttospeech.googleapis.com")  # fmt: skip
            self._client = texttospeech.TextToSpeechAsyncClient(credentials=_credentials(),
                                                                client_options={"api_endpoint": host})  # fmt: skip
        return self._client

    async def warm(self) -> None:
        with contextlib.suppress(Exception):
            self.client()

    async def synthesize(self, text: str) -> AsyncIterator[bytes]:
        if not text or len(text) > MAX_TEXT:
            raise UpstreamError("format_error", "speech text out of bounds")
        from google.cloud import texttospeech as tts

        config = tts.StreamingSynthesizeConfig(
            voice=tts.VoiceSelectionParams(name=self.voice, language_code="-".join(self.voice.split("-")[:2])),
            streaming_audio_config=tts.StreamingAudioConfig(audio_encoding=tts.AudioEncoding.PCM,
                                                            sample_rate_hertz=RATE))  # fmt: skip

        async def requests() -> AsyncIterator[Any]:
            yield tts.StreamingSynthesizeRequest(streaming_config=config)
            yield tts.StreamingSynthesizeRequest(input=tts.StreamingSynthesisInput(text=text))

        try:
            call = await self.client().streaming_synthesize(requests=requests())
        except Exception:
            raise UpstreamError("network_unavailable", "synthesis open failed") from None
        odd = b""
        try:
            async for response in call:
                pcm = odd + bytes(response.audio_content)
                cut = len(pcm) - len(pcm) % 2
                odd = pcm[cut:]
                if cut:
                    yield pcm[:cut]
        except asyncio.CancelledError:
            with contextlib.suppress(Exception):
                call.cancel()
            raise
        except Exception:
            raise UpstreamError("server_error", "synthesis stream failed") from None
        finally:
            with contextlib.suppress(Exception):
                call.cancel()

    async def aclose(self) -> None:
        client, self._client = self._client, None
        if client is not None:
            with contextlib.suppress(Exception):
                await client.transport.close()
