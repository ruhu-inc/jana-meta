"""A companion turn's calls through the real router and a real GatewayProvider against fake HTTP services (SPEC
§19.5.1, §19 status fix 2026-10-29). A turn with a `study_search` tool round ends in the decode-only call, which sends
the companion's output schema as a `response_format`; every request must match the gateway's ChatCompletionRequest
contract, whose json_schema name is the providers' (letters, digits, `_`, `-`). The contract path the companion
names its output by, `agents/companion-turn`, was sent as that name and Muse Spark refused it with 400 twice. A
failed companion turn records its model calls in the turn trace and names the refusal by code. Every learner and
reply here is synthetic."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from agent_core.config import Settings
from agent_core.contracts import document, errors
from agent_core.contracts.cloud.gateway import ChatCompletionRequest
from agent_core.engine import turn_scope
from agent_core.providers.openai_compat import format_name
from agent_core.router import Message, ToolSchema
from agent_core.router.config import load
from agent_core.router.core import Router
from agent_core.router.online import cloud_session
from jsonschema import Draft202012Validator
from net_harness import FakeServices, enable, layer

ROUTER = Path(__file__).resolve().parents[1] / "agent_core" / "router" / "router.yaml"
PROFILE = "prf_private"
SEARCH = ToolSchema("study_search", "Search the learner's own materials.",
                    {"type": "object", "additionalProperties": False, "required": ["query"],
                     "properties": {"query": {"type": "string", "minLength": 1, "maxLength": 200}}})  # fmt: skip
REPLY = {"text": "Your pack says range is greatest at 45 degrees. Shall I make the cards?", "action": None}


def _completion(message: dict[str, Any]) -> dict[str, Any]:
    return {"id": "chatcmpl-1", "object": "chat.completion", "model": "fast-model",
            "choices": [{"index": 0, "message": message, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 40, "completion_tokens": 20}}  # fmt: skip


async def _turn(tmp: Path) -> list[Any]:
    """The two calls a companion turn with one study_search round makes (`engine.companion._call`): the tool round,
    then the decode-only call with the output schema and the tools made uncallable."""
    schema = {k: v for k, v in document("agents/companion-turn").items() if k not in ("$schema", "$id")}
    output = ("agents/companion-turn", schema, Draft202012Validator(schema))
    search = {"name": "study_search", "arguments": json.dumps({"query": "range and maximum height"})}
    async with FakeServices(tmp) as fake:
        fake.chat = [
            _completion({"role": "assistant", "content": None,
                         "tool_calls": [{"id": "call_1", "type": "function", "function": search}]}),
            _completion({"role": "assistant", "content": json.dumps(REPLY)}),
        ]  # fmt: skip
        online = layer(tmp, fake)
        try:
            enable(online, "cloud_tier")
            online.connectivity.state = "online"
            online.record_notice(PROFILE, "cloud_tier", True)
            cloud = cloud_session(online, Settings(), profile_id=PROFILE, terms=["Ada"])
            router = Router(load(ROUTER), Settings(), dict(cloud.providers), hardware_class="high",
                            cloud_on=lambda role: True)  # fmt: skip
            router.network, router.budget = cloud.network, cloud.budget
            asked = "<student>Make me 10 flashcards on range and maximum height</student>"
            history = [Message("system", "You are the learner's study companion."), Message("user", asked)]
            with turn_scope("t-companion"):
                first = await router.complete("companion", history, [SEARCH], output=None, effort="low")
            (call,) = first.turn.tool_calls
            history += [Message("assistant", first.turn.text, tool_calls=[call]),
                        Message("tool", "<own-materials>[1] Pack: range is greatest at 45 degrees.</own-materials>",
                                tool_call_id=call.id, name="study_search")]  # fmt: skip
            with turn_scope("t-companion"):
                decoded = await router.complete("companion", history, [SEARCH], output=output, tools_off=True,
                                                effort="low")  # fmt: skip
            assert decoded.schema_valid and decoded.structured == REPLY
            return [r for r in fake.requests if r.path == "/v1/chat/completions"]
        finally:
            await online.stop()


def test_a_study_search_round_and_the_decode_call_match_the_gateway_contract(tmp_path: Path) -> None:
    sent = asyncio.run(_turn(tmp_path))
    assert len(sent) == 2
    for request in sent:
        assert errors("cloud/gateway#/$defs/ChatCompletionRequest", request.json()) == []
        # The gateway also validates the generated model before forwarding the original body.
        parsed = ChatCompletionRequest.model_validate(request.json())
        assert parsed.model_dump(by_alias=True, exclude_unset=True) == request.json()
        assert request.headers["x-jana-role"] == "companion"
    decode = sent[1].json()
    assert decode["response_format"]["json_schema"]["name"] == "agents_companion-turn"
    assert [m["role"] for m in decode["messages"]][-2:] == ["assistant", "tool"]
    # The name the companion's output used to be sent under is refused by the contract, as Muse Spark refused it.
    refused = {**decode, "response_format": {"type": "json_schema",
                                             "json_schema": {**decode["response_format"]["json_schema"],
                                                             "name": "agents/companion-turn"}}}  # fmt: skip
    assert errors("cloud/gateway#/$defs/ChatCompletionRequest", refused) != []


def test_format_names_keep_to_the_providers_rule() -> None:
    assert format_name("agents/companion-turn") == "agents_companion-turn"
    assert format_name("ResearchChatTurn") == "ResearchChatTurn"
    assert format_name("") == "output" and format_name(None) == "output"
    assert len(format_name("x" * 100)) == 64


def test_a_failed_companion_turn_records_its_model_calls_and_names_the_code(tmp_path: Path) -> None:
    from w8_companion_harness import run, stop_core, thread

    refused = {"error": {"status": 400, "body": {"error": {"code": "format_error", "message": "invalid name"}}}}

    async def go() -> None:
        t = await thread(tmp_path, {"companion": [refused] * 4})
        try:
            opened = await t.open()
            await t.say(opened["session_id"], "Make me 10 flashcards on range and maximum height")
            assert t.r.runtime.traces is not None, "this harness keeps traces"
            t.r.runtime.traces.flush()
            records = t.r.runtime.traces.records()
            turns = [r for r in records if r.get("kind") == "turn" and r.get("mode") == "study_companion"]
            assert turns, "the companion turn is traced"
            trace = turns[-1]
            assert trace["degraded"] is True and trace["degraded_reason"] == "format_error"
            assert trace["model_calls"] and all(c.get("reason") for c in trace["model_calls"])
            assert errors("trace/turn-trace", trace) == []
        finally:
            await stop_core(t.r)

    run(go())
