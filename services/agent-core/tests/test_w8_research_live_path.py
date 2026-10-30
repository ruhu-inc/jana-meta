"""The research conversation's live path (SPEC §18.1a, §19 status fix 2026-10-29). Run through the real router and a
real GatewayProvider against fake HTTP services (the egress layer, its policy, credential and first-use notice), not a
stub provider: a profile that has never answered the online tutor's first-use notice (ARC-10) gets no cloud candidate,
so the conversation asks the notice itself and sends the same turn with the answer; any refusal names its code in the
API error's details and the job trace, never prompt text. Every learner and reply here is synthetic."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
from agent_core.config import Settings
from agent_core.contracts import errors
from agent_core.engine.research_chat import ChatError, Start, job_trace, next_turn, trace_record
from agent_core.router.config import load
from agent_core.router.core import Router
from agent_core.router.online import cloud_session
from net_harness import FakeServices, enable, layer

ROUTER = Path(__file__).resolve().parents[1] / "agent_core" / "router" / "router.yaml"
PROFILE = "prf_private"
QUESTION = {"kind": "question", "question": "What is this pack for?", "chips": ["An exam", "Curiosity"],
            "asks": "purpose", "brief": None}  # fmt: skip
REPLY = {"id": "chatcmpl-1", "object": "chat.completion", "model": "fast-model",
         "choices": [{"index": 0, "message": {"role": "assistant", "content": json.dumps(QUESTION)},
                      "finish_reason": "stop"}],
         "usage": {"prompt_tokens": 40, "completion_tokens": 20}}  # fmt: skip


async def _talk(tmp: Path, *, notice: bool, cloud_on: Any = None) -> tuple[Any, list[Any], Any]:
    """One turn of the conversation through the open profile's cloud session, as the app's research router has it:
    `cloud_on` is the router's gate (by default the app's: the cloud tier is on only once the notice is accepted)."""
    tmp.mkdir(parents=True, exist_ok=True)
    async with FakeServices(tmp) as fake:
        fake.chat = [REPLY] * 3
        online = layer(tmp, fake)
        try:
            enable(online, "cloud_tier")
            online.connectivity.state = "online"
            if notice:
                online.record_notice(PROFILE, "cloud_tier", True)
            cloud = cloud_session(online, Settings(), profile_id=PROFILE, terms=["Ada"])
            gate = cloud_on or (lambda role: online.notice_answer(PROFILE) == "accepted")
            router = Router(load(ROUTER), Settings(), dict(cloud.providers), hardware_class="high", cloud_on=gate)
            router.network, router.budget = cloud.network, cloud.budget
            trace = job_trace(PROFILE)
            try:
                outcome: Any = await next_turn(router, Start(topic="electrolysis of brine"), [], None, trace=trace)
            except ChatError as error:
                outcome = error
            return outcome, list(fake.requests), trace
        finally:
            await online.stop()


def test_the_research_chat_reaches_the_gateway_through_a_gateway_provider(tmp_path: Path) -> None:
    # Never asked: the router has no cloud candidate, nothing is sent, and the details say why by code.
    refused, sent, trace = asyncio.run(_talk(tmp_path / "unasked", notice=False))
    assert isinstance(refused, ChatError) and str(refused) == "model_unavailable"
    assert refused.details["router_reason"] == "model_not_found"
    assert refused.details["dropped"] == {"cloud:primary/fast-model": "cloud tier off"}
    assert not any(r.path == "/v1/chat/completions" for r in sent)
    assert "electrolysis" not in json.dumps(refused.details)  # codes only, never prompt text
    # Accepted: the turn goes through the egress layer to the gateway's chat route, in its contract.
    turn, sent, trace = asyncio.run(_talk(tmp_path / "accepted", notice=True))
    assert turn == QUESTION
    chats = [r for r in sent if r.path == "/v1/chat/completions"]
    assert len(chats) == 1 and errors("cloud/gateway#/$defs/ChatCompletionRequest", chats[0].json()) == []
    assert chats[0].headers["x-jana-role"] == "research_chat"
    assert "electrolysis of brine" in json.dumps(chats[0].json()["messages"])
    record = trace_record(trace)
    assert record is not None and record["job_name"] == "research_chat" and record["status"] == "complete"
    assert [c["provider_kind"] for c in record["model_calls"]] == ["cloud"]


def test_a_refused_send_names_its_code_in_the_details_and_the_trace(tmp_path: Path) -> None:
    """A gate that lets the call through while the egress layer refuses it (here: the notice still pending): the
    provider's refusal code reaches the error's details and the job trace's `degraded_reason`."""
    refused, sent, trace = asyncio.run(_talk(tmp_path, notice=False, cloud_on=lambda role: True))
    assert isinstance(refused, ChatError)
    codes = [e.get("code") for e in refused.details["provider_errors"]]
    assert codes and set(codes) == {"egress_notice_pending"}
    assert not any(r.path == "/v1/chat/completions" for r in sent)
    record = trace_record(trace)
    assert record is not None and record["status"] == "error" and record["degraded_reason"] == "egress_notice_pending"
    assert record["model_calls"] and all(c["provider_kind"] == "cloud" for c in record["model_calls"])
    assert "electrolysis" not in json.dumps(record)


class _Online:
    """The connectivity layer's first-use notice answers, as the route reads and records them."""

    def __init__(self) -> None:
        self.answers: dict[str, str] = {}

    def notice_answer(self, profile_id: str | None, feature: str = "cloud_tier") -> str | None:
        return self.answers.get(f"{profile_id}:{feature}")

    def record_notice(self, profile_id: str | None, feature: str, accepted: bool) -> None:
        self.answers[f"{profile_id}:{feature}"] = "accepted" if accepted else "declined"


@pytest.mark.parametrize("first_answer", ["accepted", "declined"])
def test_the_route_asks_the_online_tutor_notice_and_records_the_answer(tmp_path: Path, first_answer: str) -> None:
    from test_research_api import Router as Scripted
    from test_research_api import scenario

    async def play(r: Any, send: Any, get: Any, gateway: Any) -> None:
        router = Scripted([QUESTION, QUESTION])
        r.core.research_router = lambda: router
        online = _Online()
        r.core.online = online
        first = {"start": {"topic": "electrolysis of brine"}, "history": [], "answer": None, "skip": False}
        asked = await send("POST", "/v1/study/research/chat", first)
        assert asked.status_code == 403, asked.text
        details = asked.json()["error"]["details"]
        assert (asked.json()["error"]["code"], details["reason"], details["feature"]) == (
            "feature_disabled", "notice_required", "cloud_tier")  # fmt: skip
        assert router.prompts == [], "nothing reached the router before the notice"
        answered = await send("POST", "/v1/study/research/chat", {**first, "cloud_notice": first_answer})
        assert list(online.answers.values()) == [first_answer]
        if first_answer == "declined":
            assert answered.status_code == 403
            assert answered.json()["error"]["details"]["reason"] == "notice_declined" and router.prompts == []
            return
        assert answered.status_code == 200, answered.text
        again = await send("POST", "/v1/study/research/chat", first)  # remembered: not asked again
        assert again.status_code == 200 and len(router.prompts) == 2

    scenario(tmp_path, play)
