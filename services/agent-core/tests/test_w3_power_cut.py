"""W3 (SPEC §7, §17): the power cut. A cloud call never waits out its request timeout before the local model serves it,
and the cloud tutor comes back once a probe finds the network again (`cloud_offline` resets)."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any

import pytest
from agent_core.config import Settings
from agent_core.engine import turn_scope
from agent_core.net.client import Response
from agent_core.net.state import Connectivity
from agent_core.providers.base import Message
from agent_core.providers.gateway import GatewayProvider, cloud_capabilities
from agent_core.providers.scripted import ScriptedProvider
from agent_core.router import core
from agent_core.router.config import load
from agent_core.router.core import Router

ROUTER = Path(__file__).resolve().parents[1] / "agent_core" / "router" / "router.yaml"
LOCAL = "qwen3-vl-8b"
REPLY = {"reply": {"choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": "x"}}],
                   "usage": {"prompt_tokens": 10, "completion_tokens": 5}}}  # fmt: skip


class StalledCloud(ScriptedProvider):
    """A cloud call whose connection went with the Wi-Fi: it never answers."""

    async def complete(self, model: str, messages: list[Message], tools: list[Any], **settings: Any) -> Any:
        self.requests.append({"model": model})
        await asyncio.Event().wait()

    async def stream(self, model: str, messages: list[Message], tools: list[Any], **settings: Any) -> Any:
        self.requests.append({"model": model})
        await asyncio.Event().wait()
        yield None  # never reached


def _router(cloud: ScriptedProvider, network: dict[str, str], **kw: Any) -> tuple[Router, ScriptedProvider]:
    local = ScriptedProvider([REPLY] * 4, installed_models=[LOCAL])
    router = Router(load(ROUTER), Settings(), {"primary": cloud, "local": local}, hardware_class="high",
                    cloud_on=lambda role: True, network=lambda: network["now"], **kw)  # fmt: skip
    return router, local


def test_a_stalled_cloud_call_is_served_locally_once_a_probe_finds_the_network_gone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(core, "CLOUD_STALL_CHECK_S", 0.05)
    network = {"now": "online"}
    probes: list[str] = []

    async def recheck() -> str:
        probes.append("probe")
        network["now"] = "online" if len(probes) < 3 else "offline"  # still there twice, then the Wi-Fi goes
        return network["now"]

    caps = {m: cloud_capabilities(131072, 16384) for m in ("fast-model", "strong-model")}
    cloud = StalledCloud([], kind="cloud", caps=caps)
    router, local = _router(cloud, network, recheck=recheck)

    async def run() -> Any:
        with turn_scope("t-cut"):
            return await router.complete("coach", [Message("user", "Why?")])

    started = time.monotonic()
    result = asyncio.run(run())
    assert time.monotonic() - started < 2  # seconds, not the 120 s request timeout
    assert result.turn.text == "x" and len(local.requests) == 1 and len(cloud.requests) == 1
    assert probes == ["probe"] * 3 and router.cloud_offline
    assert result.record.events[0] == {"event": "fallback", "from": "cloud:primary/fast-model",
                                       "reason": "network_unavailable"}  # fmt: skip


def test_cloud_offline_resets_when_a_probe_finds_the_network_again() -> None:
    network = {"now": "offline"}
    asked: list[str] = []
    caps = {m: cloud_capabilities(131072, 16384) for m in ("fast-model", "strong-model")}
    cloud = ScriptedProvider([REPLY] * 4, kind="cloud", caps=caps)
    router, local = _router(cloud, network, recheck_soon=lambda: asked.append("soon"))
    router.cloud_offline = True  # a network failure marked it during an earlier call

    async def coach() -> Any:
        with turn_scope("t-back"):
            return await router.complete("coach", [Message("user", "Why?")])

    asyncio.run(coach())
    assert len(local.requests) == 1 and cloud.requests == [] and asked  # offline: local, and a probe is asked for
    network["now"] = "online"  # the probe found the network again
    asyncio.run(coach())
    assert len(cloud.requests) == 1 and not router.cloud_offline


def test_the_gateway_saying_it_cannot_reach_meta_is_the_network_gone() -> None:
    reported: list[str] = []
    provider = GatewayProvider(None, lambda: "localhost", "primary", on_network_failure=reported.append)  # type: ignore[arg-type]
    body = {"error": {"code": "upstream_unreachable", "message": "The model provider is unreachable."}}
    error = provider._failure(Response(502, {}, body))
    assert error.reason == "network_unavailable" and reported == ["offline"]
    other = provider._failure(Response(502, {}, {"error": {"code": "upstream_error", "message": "x"}}))
    assert other.reason == "server_error" and reported == ["offline"]


def test_a_turn_while_offline_asks_for_a_probe_once_the_last_check_is_old_enough() -> None:
    async def probe(host: str) -> Any:
        return "failed"

    connectivity = Connectivity(lambda: {"cloud_tier"}, lambda: "gateway", probe)
    connectivity.report_failure()
    due = connectivity._due
    connectivity.recheck_soon(60)
    assert connectivity._due == due  # checked just now: the backoff stands
    connectivity.checked_ms -= 61_000
    connectivity.recheck_soon(60)
    assert connectivity._due < due  # old enough: probe now
