"""W3 (SPEC §7, JM-D11): Muse Glimmer 30B as the offline tutor on the high class.

Glimmer always reasons: its template takes `reasoning_strength` and has no off switch, so the llama-server adapter
sends the router's effort as a strength (its lowest, `low`, where another model's thinking would be off), and the
router gives its reasoning room on top of the role's output cap, as it does for Muse Spark in the cloud."""

from __future__ import annotations

import asyncio
import json
from dataclasses import replace
from pathlib import Path

from agent_core.config import Settings
from agent_core.engine import turn_scope
from agent_core.providers.base import Message
from agent_core.providers.llama import LlamaServerProvider
from agent_core.providers.scripted import ScriptedProvider, default_capabilities
from agent_core.router.capabilities import RECOMMENDATIONS, recommendation_errors
from agent_core.router.config import load
from agent_core.router.core import LOCAL_REASONING_HEADROOM, Router
from jana_tools.fakes import FakeLlamaServer
from jana_tools.fakes.llama_server import default_props

ROUTER = Path(__file__).resolve().parents[1] / "agent_core" / "router" / "router.yaml"
GLIMMER = "muse-glimmer-30b"
TEMPLATE = "{%- set rs = reasoning_strength if reasoning_strength is defined and reasoning_strength else 'high' -%}"
REPLY = {"reply": {"choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": "x"}}],
                   "usage": {"prompt_tokens": 10, "completion_tokens": 5}}}  # fmt: skip


def test_glimmer_is_recommended_for_the_high_class_and_leads_the_local_candidates() -> None:
    document = json.loads(RECOMMENDATIONS.read_text())
    assert recommendation_errors(document) == []
    entry = next(e for e in document["models"] if e["model"] == GLIMMER)
    assert entry["licence"] == "Apache-2.0" and set(entry["classes"]) == {"high"}
    assert entry["thinking"] == {"available": True, "default": "on"}  # it cannot be turned off
    assert entry["max_output"] >= 8192 and entry["capabilities"]["parallel_tools"] is False
    tiers = load(ROUTER).data["tiers"]
    for tier in ("fast", "strong", "judge"):
        local = [c for c in tiers[tier] if c.startswith("local:")]
        assert local[0] == f"local:{GLIMMER}", tier


def test_the_adapter_sends_effort_as_reasoning_strength_and_keeps_each_role_in_its_slot() -> None:
    async def scenario() -> list[dict]:
        props = {**default_props(GLIMMER), "chat_template": TEMPLATE, "total_slots": 4}
        async with FakeLlamaServer([GLIMMER], props={GLIMMER: props}) as server:
            provider = LlamaServerProvider(server.url, server.api_key)
            caps = await provider.capabilities(GLIMMER)
            assert (caps.reasoning, caps.reasoning_default) == ("effort", "low")
            for role, effort in (("coach", "none"), ("diagnoser", "low"), ("solver", "high")):
                server.script.append(REPLY)
                await provider.complete(GLIMMER, [Message("user", "x")], [], role=role, effort=effort)
            await provider.close()
            return server.requests

    requests = asyncio.run(scenario())
    assert [r["chat_template_kwargs"] for r in requests] == [
        {"reasoning_strength": "low"},  # "none" is its lowest level: Glimmer always reasons
        {"reasoning_strength": "low"},
        {"reasoning_strength": "high"},
    ]
    assert [r["id_slot"] for r in requests] == [0, 2, 1]  # coach, diagnoser, solver: each role's prompt stays cached
    assert all(r["cache_prompt"] for r in requests)


def test_a_local_model_that_always_reasons_gets_room_for_it_and_a_toggle_model_does_not() -> None:
    async def complete(reasoning: str) -> dict:
        caps = replace(default_capabilities("local"), reasoning=reasoning, max_output=8192)
        local = ScriptedProvider([REPLY], installed_models=[GLIMMER], caps={GLIMMER: caps})
        router = Router(load(ROUTER), Settings(), {"local": local}, hardware_class="high")
        with turn_scope("t-glimmer"):
            await router.complete("coach", [Message("user", "Why?")], max_tokens=200, cloud_max_tokens=900)
        return local.requests[-1]

    assert asyncio.run(complete("effort"))["max_tokens"] == 200 + LOCAL_REASONING_HEADROOM
    assert asyncio.run(complete("toggle"))["max_tokens"] == 200
