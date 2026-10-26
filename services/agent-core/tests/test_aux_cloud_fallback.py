"""The input guard and other auxiliary roles use the Coach's local model first and Muse Spark after it, so a computer
with no local model still screens input on Spark instead of failing open (SPEC §17 W3); a local one stays first."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from agent_core.config import Settings
from agent_core.providers.gateway import cloud_capabilities
from agent_core.providers.scripted import ScriptedProvider
from agent_core.router.config import load
from agent_core.router.core import Router

ROUTER = Path(__file__).resolve().parents[1] / "agent_core" / "router" / "router.yaml"


def _router(installed: list[str]) -> Router:
    caps = {alias: cloud_capabilities(131072, 16384) for alias in ("fast-model", "strong-model")}
    cloud = ScriptedProvider([], kind="cloud", caps=caps)
    local = ScriptedProvider([], installed_models=installed)
    return Router(load(ROUTER), Settings(), {"primary": cloud, "local": local}, hardware_class="high",
                  cloud_on=lambda role: True)  # fmt: skip


@pytest.mark.parametrize("slot", ["input_guard", "rule_matcher", "title", "compaction"])
def test_auxiliary_slots_put_the_local_model_first_and_spark_after_it(slot: str) -> None:
    async def run() -> None:
        with_local = await _router(["qwen3-vl-8b"]).resolve_slot(slot)
        assert [str(c) for c in with_local.candidates] == ["local:qwen3-vl-8b", "cloud:primary/fast-model"]
        without = await _router([]).resolve_slot(slot)
        assert [str(c) for c in without.candidates] == ["cloud:primary/fast-model"]

    asyncio.run(run())


def test_the_reflector_never_goes_to_the_cloud() -> None:
    assert "reflector" not in load(ROUTER).cloud["roles_allowed"]
