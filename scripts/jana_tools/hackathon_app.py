"""Run the app against the owner's local, budgeted Meta gateway (Muse Spark).

Development host only. The original consent, first-use, egress ledger, profile,
assessment and Study paths remain in use. This adapter never reads a provider key.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import secrets
import time
from functools import partial
from pathlib import Path
from typing import Any

import httpx
from agent_core.api.__main__ import main
from agent_core.api.core import CoreService
from agent_core.config import Settings
from agent_core.engine.assembly import AppRuntime
from agent_core.net.credentials import ID_REF
from agent_core.net.layer import OnlineLayer
from agent_core.net.state import ProbeOutcome
from agent_core.net.voice import VoiceTransportError
from agent_core.net.voice_cloud import FEATURE as VOICE_FEATURE
from agent_core.net.voice_cloud import PATH as VOICE_PATH
from agent_core.net.voice_cloud import PAYLOAD as VOICE_PAYLOAD
from agent_core.net.voice_cloud import CloudRealtimeConnection, CloudVoice
from agent_core.router.hardware import TutorPath
from agent_core.store import consents
from agent_core.store import subscription as subscriptions
from agent_core.store.keystore import FileKeyStore, KeyStore, MemoryKeyStore
from agent_core.store.sqlite import transaction
from cloud_gateway.app import VERSION as GATEWAY_VERSION
from cloud_gateway.config import GatewayConfig, load_config
from cloud_gateway.store import GatewayStore
from cloud_gateway.tier import monthly_allowance_tokens

HOST = "localhost"
ONLINE_DEMO = "JANA_ONLINE_DEMO"  # "1" from `hackathon_dev --online-demo`; anything else leaves consent to the learner
log = logging.getLogger(__name__)


class GatewayHop(httpx.AsyncBaseTransport):
    """A virtual HTTPS service name mapped only to a literal loopback gateway.

    Used behind the existing egress admission checks, never for external services.
    The actual provider connection remains HTTPS in the private gateway.
    """

    def __init__(self, port: int, transport: httpx.AsyncBaseTransport | None = None) -> None:
        if not 1 <= port <= 65535:
            raise ValueError("invalid local gateway port")
        self.port = port
        self.inner = transport or httpx.AsyncHTTPTransport(trust_env=False)

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if (
            request.url.scheme != "https"
            or request.url.host != HOST
            or request.url.port not in (None, 443)
            or request.url.username
            or request.url.password
            or not request.url.path.startswith("/v1/")
        ):
            raise httpx.ConnectError("Refused a destination outside the local gateway", request=request)
        url = request.url.copy_with(scheme="http", host="127.0.0.1", port=self.port)
        headers = dict(request.headers)
        headers["host"] = f"127.0.0.1:{self.port}"
        # The device's request goes as it is: the gateway checks it against the device contract and its Meta
        # adapter applies the provider's rules, so nothing provider-specific is added here.
        forwarded = httpx.Request(
            request.method, url, headers=headers, stream=request.stream, extensions=request.extensions
        )
        response = await self.inner.handle_async_request(forwarded)
        if response.status_code >= 400:
            # The gateway's fixed error codes never contain prompts or credentials.
            await response.aread()
            try:
                error = response.json().get("error", {})
                log.warning(
                    f"local_gateway status={response.status_code} code={error.get('code')} param={error.get('param')}"
                )
            except (ValueError, AttributeError):
                log.warning(f"local_gateway status={response.status_code}")
        return response

    async def aclose(self) -> None:
        await self.inner.aclose()


class LoopbackCloudVoice(CloudVoice):
    """Cloud voice to the local gateway's `/v1/voice/realtime`, as `GatewayHop` is for its HTTP routes: the same
    admission, credential, first-use notice, egress announcement and ledger as `CloudVoice.open`, then a plain
    WebSocket to the literal loopback port (the gateway serves HTTP locally; its Voice Transcribe connection is TLS).
    Development host only."""

    def __init__(self, *args: Any, port: int, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        if not 1 <= port <= 65535:
            raise ValueError("invalid local gateway port")
        self.port = port

    async def open(self, session_id: str) -> CloudRealtimeConnection:
        from agent_core.net.policy import EgressRefused
        from websockets.asyncio.client import connect as websocket_connect

        profile = self.profile()
        if not self.effective() or self.host() != HOST:
            raise VoiceTransportError("cloud_voice_refused")
        try:
            current, host = self.layer.client.admit(VOICE_FEATURE, f"https://{HOST}{VOICE_PATH}", VOICE_PAYLOAD,
                                                    credential=True, profile_id=profile)  # fmt: skip
            token = await self.layer.credential.token(VOICE_FEATURE, host)
        except EgressRefused:
            raise VoiceTransportError("cloud_voice_refused") from None
        except Exception:
            raise VoiceTransportError("voice_endpoint_unavailable") from None
        row = current.features[VOICE_FEATURE]
        notice = {"type": "egress.notice", "feature": VOICE_FEATURE, "destination_label": row.destination_label,
                  "data_classes": list(row.data_classes)}  # fmt: skip
        self.announce(session_id, {**notice, "state": "started"})
        self.layer.client._ledger(VOICE_FEATURE, host, len(VOICE_PATH), VOICE_PAYLOAD, profile)
        try:
            socket = await websocket_connect(
                self.url(HOST, session_id).replace(f"wss://{HOST}", f"ws://127.0.0.1:{self.port}", 1),
                additional_headers={"Authorization": "Bearer " + token},
                proxy=None, compression=None, max_size=1_000_000, max_queue=64, close_timeout=2,
                open_timeout=self.layer.settings.net_connect_timeout_s, ping_interval=1.0,
                ping_timeout=3.0)  # fmt: skip
        except Exception:
            self.announce(session_id, {**notice, "state": "ended"})
            self.layer.network_failure()
            raise VoiceTransportError("voice_endpoint_unavailable") from None
        return CloudRealtimeConnection(
            socket, self.respond, lambda: self.announce(session_id, {**notice, "state": "ended"})
        )


def gateway_config() -> GatewayConfig:
    path = os.environ.get("JANA_META_GATEWAY_CONFIG")
    if not path:
        raise ValueError("Set JANA_META_GATEWAY_CONFIG to the approved gateway configuration")
    config = load_config(Path(path))
    if (
        config.environment != "dev"
        or config.audience_host != HOST
        or config.slots.get("primary") != "meta"
        or config.quotas.deployment_total_spend_usd is None
        or config.quotas.deployment_daily_spend_usd is None
        or config.quotas.deployment_budget_expires_at is None
    ):
        raise ValueError("The browser host requires a local Meta gateway with daily, total and expiry limits")
    return config


class SponsoredRuntime(AppRuntime):
    def key_store(self) -> KeyStore:
        if self.release:
            raise ValueError("The local hackathon key store is development-only")
        if self.keys is None or isinstance(self.keys, MemoryKeyStore):
            self.keys = FileKeyStore(self.data_root.parent / f".{self.data_root.name}-keys", self.data_root)
        return self.keys

    def attach_online(self) -> OnlineLayer:
        layer = super().attach_online()
        if self.release:
            raise ValueError("The local hackathon adapter is not a release deployment")
        self.gateway = gateway_config()
        self.gateway_port = int(os.environ.get("JANA_META_GATEWAY_PORT", "8081"))
        layer.hosts = {service: HOST for service in ("gateway", "voice")}
        # Downloads/updates/voice keep their original implementations, but no such
        # external service is connected by this local inference adapter.
        layer.client._client = httpx.AsyncClient(
            transport=GatewayHop(self.gateway_port), trust_env=False, follow_redirects=False, timeout=180
        )
        layer.probe = partial(upstream_probe, self.gateway_port)
        return layer

    def prepare_cloud_voice(self, announce: Any, respond: Any) -> CloudVoice | None:
        voice = super().prepare_cloud_voice(announce, respond)
        if voice is None or self.online is None:
            return voice
        return LoopbackCloudVoice(self.online, self.public_profile,
                                  lambda: self.stores.learner if self.stores is not None else None, announce, respond,
                                  port=self.gateway_port)  # fmt: skip

    def tutor_path(self) -> TutorPath:
        # Before first-use acceptance the original engine must be able to show its
        # notice. No inference is admitted until cloud_tier_on() becomes true.
        if self.online and self.stores and self.online.cloud_effective(self.public_profile(), self.stores.learner):
            return "online"
        return super().tutor_path()

    def tutor_unavailable(self) -> bool:
        if self.tutor_path() == "online":
            return False
        if "local" not in self.providers and not self.school_server_reachable():
            return True
        return super().tutor_unavailable()


def settings_for_browser(settings: Settings) -> Settings:
    return settings.model_copy(
        update={
            # Expose the imported visual tutoring, local parent views and history
            # in the development app. This is not a release-acceptance claim.
            "build_stage": "S3",
            "study_workspace_enabled": True,
            "study_offline_enabled": False,
            "study_neural_speech_enabled": True,
            "study_batch_char_limit": 16000,
            "consent_dpia_ref": "local-synthetic-hackathon-notice",
            # Spoken turns online (SPEC §6): Muse Voice Transcribe and Kokoro behind the local gateway's voice route.
            "cloud_voice_enabled": True,
            # Offline (W3), a turn on Muse Glimmer runs as the low class (its short prompts and fewer calls) and a
            # practice hint is the authored one, shown at once.
            "offline_lean_classes": ("low", "mid", "high"),
        }
    )


async def upstream_probe(port: int, _host: str) -> ProbeOutcome:
    """The connectivity probe (ARC-08) for a gateway on this laptop: it answers its own ping with Wi-Fi off, so the
    probe asks it whether Meta answers too (W3). Offline, the router serves every call on the local model and the
    connectivity layer keeps probing, so the cloud tutor returns once Meta can be reached again."""
    try:
        async with httpx.AsyncClient(trust_env=False) as probe:
            reply = await probe.get(f"http://127.0.0.1:{port}/v1/ping", params={"upstream": "1"}, timeout=4)
    except httpx.HTTPError:
        return "failed"
    return "ok" if reply.status_code == 204 else "failed"


async def check_gateway(port: int, transport: httpx.AsyncBaseTransport | None = None) -> None:
    """Fail closed unless the already-running gateway on `port` is this repository's (its `jana-gateway-version`
    header equals `cloud_gateway.app.VERSION`) and advertises its persistent cap. A gateway from another project on
    the shared port answers the ping but knows none of this repository's kinds, so every job failed with
    `processing_failed` (live-run fix 2026-11-01); the message names the port and the version found."""
    async with httpx.AsyncClient(trust_env=False, transport=transport) as probe:
        try:
            reply = await probe.get(f"http://127.0.0.1:{port}/v1/ping", timeout=3)
        except httpx.HTTPError as error:
            raise ValueError(
                f"No gateway answered on port {port}: start this repository's gateway (version {GATEWAY_VERSION})"
                " before the browser host"
            ) from error
        version = reply.headers.get("jana-gateway-version")
        if reply.status_code != 204 or version != GATEWAY_VERSION:
            raise ValueError(
                f"The gateway on port {port} is not this repository's: it serves version {version or 'none'}"
                f" (status {reply.status_code}) and this repository's gateway serves {GATEWAY_VERSION}."
                f" Stop it and start this repository's gateway on port {port} before the browser host"
            )
        if reply.headers.get("x-jana-inference-budget") != "enabled":
            raise ValueError(f"Start the approved budgeted gateway on port {port} before the browser host")


def online_demo_grant(runtime: AppRuntime, core: CoreService, profile_id: str) -> None:
    """`--online-demo`: record, for this one profile, what Settings and the first-use cards record when an adult of 18
    or over turns the cloud tutor and online Study materials on, so a demo needs no Settings steps. The same stores and
    calls the routes use: the subscription's waiting consent, the computer's two switches (`PATCH /v1/connectivity`,
    `POST /v1/subscription`), the profile's own `cloud_tier` and `study_materials` consents
    (`PUT /v1/profiles/{id}/consents/{scope}`) and the cloud tutor's and Study's first-use notices. Personal tutor
    memory online and cloud voice stay as they were. A profile that is not an adult who gives their own consent
    (PRV-06, Meta's terms) is refused, whatever the flag says; the consent model is not changed for anyone else."""
    directory, online = runtime.directory, runtime.online
    if directory is None or online is None:
        raise ValueError("The online demo needs the host's own local runtime")
    if not directory.self_consents(profile_id):
        raise ValueError("--online-demo records consent only for a profile of an adult aged 18 or over")
    now = core.clock_ms()
    stored = subscriptions.consent_given(subscriptions.load(online.device), [profile_id])
    subscriptions.save(online.device, stored, now)
    with transaction(directory.device):
        for feature, role in (("cloud_tier", "subscription"), ("study_materials", "user")):
            directory.device.execute(
                "INSERT INTO online_features (feature, enabled, enabled_by_role, enabled_at, disabled_at)"
                " VALUES (?, 1, ?, ?, NULL) ON CONFLICT (feature) DO UPDATE SET enabled = 1,"
                " enabled_at = coalesce(excluded.enabled_at, enabled_at)",
                (feature, role, now),
            )
            directory.audit("online_feature.enable", None, {"feature": feature, "by": "online_demo"})
    notices = getattr(core, "notices", {})
    with directory.open_learner(profile_id) as conn, transaction(conn):
        for scope in ("cloud_tier", "study_materials"):
            versions = notices.get(scope, [])
            consents.grant(conn, scope, "student_18_plus", "Student", versions[-1] if versions else "unversioned",
                           core.settings.consent_dpia_ref, now, include_study=True)  # fmt: skip
    for feature in ("cloud_tier", "study_materials"):
        online.record_notice(profile_id, feature, True)
    online.connectivity.features_changed()
    online.announce()
    log.warning("online demo: cloud tutor and online Study materials recorded for %s", profile_id)


async def connect(runtime: AppRuntime, core: CoreService) -> None:
    if not isinstance(runtime, SponsoredRuntime) or runtime.online is None or runtime.directory is None:
        raise ValueError("The hackathon host requires its own local runtime")
    online = runtime.online
    await check_gateway(runtime.gateway_port)
    expires = runtime.gateway.quotas.deployment_budget_expires_at
    assert expires is not None
    end_ms = int(expires.timestamp() * 1000)
    if end_ms <= core.clock_ms():
        raise ValueError("The approved inference period has expired")
    store = GatewayStore(runtime.gateway.storage_dir)
    public = online.credential.public_key()
    credential = "dcr_" + secrets.token_urlsafe(18)
    # Provision only the app host's public key. Native challenge signing and token
    # renewal still authenticate every gateway call. No provider secret is read.
    held = online.device.execute("SELECT value FROM app_settings WHERE key='hackathon_sponsor'").fetchone()
    account = json.loads(held[0]) if held else "sub_hackathon_" + secrets.token_hex(12)
    if not held:
        online.device.execute(
            "INSERT INTO app_settings VALUES ('hackathon_sponsor',?,?)", (json.dumps(account), core.clock_ms())
        )
    state, credential = store.bind_credential(
        credential,
        public,
        "lic_hackathon",
        account,
        expires.timestamp(),
        time.time(),
        runtime.gateway.devices_per_subscription,
    )
    if state not in {"added", "renewed"}:
        store.close()
        raise ValueError("The local gateway credential could not be provisioned")
    online.keys.put(ID_REF, credential.encode())
    online.credential.forget_token()
    now = core.clock_ms()
    plan = runtime.gateway.plans.paid["jana_online"]
    entitlement = subscriptions.Entitlement(
        account,
        now,
        end_ms,
        100,
        monthly_allowance_tokens(runtime.gateway),
        "lic_hackathon",
        features=tuple(plan.features),
        limits=plan.limits.model_dump(exclude_none=True),
    )

    def sponsor(_profile_id: str | None = None) -> None:
        assert runtime.directory is not None
        known = [p["profile_id"] for p in runtime.directory.summaries()["profiles"]]
        if not known:
            return
        old = subscriptions.load(online.device)
        # Ending access is sticky; a restart never silently turns it back on.
        if old.get("ended_at") is not None:
            return
        waiting = set(old.get("consent_needed", []))
        waiting.update(p for p in known if p not in old.get("profiles", []))
        record = subscriptions.record(
            entitlement, known, known, [p for p in known if p not in waiting], "hackathon_sponsor"
        )
        subscriptions.save(online.device, record, now)
        # Only the native subscription consent command turns the feature on and
        # writes profile consent. Creating a profile never authorizes inference.

    sponsor()
    core.on_profile_created.append(sponsor)
    if os.environ.get(ONLINE_DEMO) == "1":
        # Only a profile created while the flag is on: one that exists already was never offered this, and is left as
        # its owner set it. A minor's profile is refused when it is created (the grant raises).
        core.on_profile_created.append(lambda profile_id: online_demo_grant(runtime, core, profile_id))
    # No scripted model stands in for live cloud calls. A local Muse Glimmer runtime the launcher started arrives after
    # ready (control.runtime_endpoint) and serves when the cloud cannot: the power cut (W3, SPEC §7).
    runtime.providers.pop("local", None)
    if runtime.link is not None:
        runtime.link = None
    core.readiness = "ready"
    core.components["runtime"] = "ok"

    async def close() -> None:
        # The app's private device key survives a normal restart. Keep its bounded
        # credential renewable; first-use consent and the gateway expiry still apply.
        store.close()

    core.closers.append(close)


if __name__ == "__main__":
    raise SystemExit(
        asyncio.run(
            main(runtime_factory=SponsoredRuntime, settings_transform=settings_for_browser, before_ready=connect)
        )
    )
