"""A cloud model that always reasons (Muse Spark) spends output tokens on reasoning before its reply: a cloud call gets
the role's cloud output cap plus reasoning headroom by effort, within the model's limit; a local call is unchanged."""

from __future__ import annotations

import asyncio
from pathlib import Path

from agent_core.config import Settings
from agent_core.engine import turn_scope
from agent_core.providers.base import Message
from agent_core.providers.gateway import cloud_capabilities
from agent_core.providers.scripted import ScriptedProvider
from agent_core.router.config import load
from agent_core.router.core import REASONING_HEADROOM, Router

ROUTER = Path(__file__).resolve().parents[1] / "agent_core" / "router" / "router.yaml"
REPLY = {"reply": {"choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": "x"}}],
                   "usage": {"prompt_tokens": 10, "completion_tokens": 5}}}  # fmt: skip


def _router(cloud_on: bool) -> tuple[Router, ScriptedProvider, ScriptedProvider]:
    caps = {alias: cloud_capabilities(131072, 16384) for alias in ("fast-model", "strong-model")}
    cloud = ScriptedProvider([REPLY] * 4, kind="cloud", caps=caps)
    local = ScriptedProvider([REPLY] * 4, installed_models=["qwen3-vl-8b"])
    router = Router(load(ROUTER), Settings(), {"primary": cloud, "local": local}, hardware_class="high",
                    cloud_on=lambda role: cloud_on)  # fmt: skip
    return router, cloud, local


def test_cloud_call_gets_the_cloud_cap_plus_reasoning_room_and_local_keeps_its_own() -> None:
    async def run() -> None:
        messages = [Message("user", "Solve 2x + 3 = 11.")]
        with turn_scope("t-headroom"):
            await check(messages)

    async def check(messages: list[Message]) -> None:
        router, cloud, local = _router(cloud_on=True)
        await router.complete("diagnoser", messages, max_tokens=400, cloud_max_tokens=800)
        sent = cloud.requests[-1]
        assert sent["max_tokens"] == 800 + REASONING_HEADROOM["low"]  # the diagnoser reasons at "low"
        assert "cloud_max_tokens" not in sent
        router, cloud, local = _router(cloud_on=False)
        await router.complete("diagnoser", messages, max_tokens=400, cloud_max_tokens=800)
        assert local.requests[-1]["max_tokens"] == 400 and "cloud_max_tokens" not in local.requests[-1]

    asyncio.run(run())


def test_reasoning_room_never_exceeds_the_models_output_limit() -> None:
    async def run() -> None:
        router, cloud, _ = _router(cloud_on=True)
        with turn_scope("t-headroom"):
            await router.complete("solver", [Message("user", "Solve.")], max_tokens=1000, cloud_max_tokens=15000)
        assert cloud.requests[-1]["max_tokens"] == 16384

    asyncio.run(run())
