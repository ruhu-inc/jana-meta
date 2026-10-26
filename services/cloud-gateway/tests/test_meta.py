"""Meta Model API (Muse Spark): the shipped configuration against network-free provider stubs. No paid calls."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx
import pytest
from agent_core.config import Settings
from agent_core.providers.scripted import ScriptedProvider
from agent_core.router.config import load
from agent_core.router.core import Router
from agent_core.router.online import cloud_models
from cloud_gateway.config import ModelSpec, load_config
from cloud_gateway.custody import KeychainSecrets, Secret, secret_source
from cloud_gateway.providers.base import ProviderRequest
from cloud_gateway.providers.meta import MetaAdapter, prepare_body
from cloud_gateway.secret_scan import scan_bytes
from gateway_stubs import FAKE_KEYS, Device, Output, gateway_config, harness

ROOT = Path(__file__).resolve().parents[3]
TOOLS = [{"type": "function", "function": {"name": "math_solve", "parameters": {"type": "object"}}}]


def test_only_auto_tool_choice_reaches_spark_without_mutating_the_caller() -> None:
    body = {"messages": [], "tools": TOOLS, "tool_choice": "required"}
    assert prepare_body(body)["tool_choice"] == "auto"
    assert body["tool_choice"] == "required"
    named = {**body, "tool_choice": {"type": "function", "function": {"name": "math_solve"}}}
    assert prepare_body(named)["tool_choice"] == "auto"
    assert prepare_body({**body, "tool_choice": "auto"})["tool_choice"] == "auto"
    # "none" is not accepted: the turn goes without tools at all.
    no_tools = prepare_body({**body, "tool_choice": "none", "parallel_tool_calls": False})
    assert {"tools", "tool_choice", "parallel_tool_calls"}.isdisjoint(no_tools)


@pytest.mark.parametrize(("asked", "sent"), [("none", "minimal"), ("low", "low"), ("high", "high")])
def test_reasoning_effort_maps_none_to_minimal(asked: str, sent: str) -> None:
    assert prepare_body({"messages": [], "reasoning_effort": asked})["reasoning_effort"] == sent


def test_refused_fields_and_history_reasoning_are_dropped_and_completions_not_stored() -> None:
    body = {
        "messages": [
            {"role": "user", "content": "Synthetic question"},
            {"role": "assistant", "content": "A hint.", "reasoning_content": "private thoughts"},
        ],
        "stop": ["\n"],
        "n": 1,
        "logprobs": True,
        "chat_template_kwargs": {"enable_thinking": False},
        "top_p": 0,
        "response_format": {"type": "json_schema", "json_schema": {"name": "x", "schema": {"type": "object"}}},
        "seed": 7,
    }
    sent = prepare_body(body)
    assert {"stop", "n", "logprobs", "chat_template_kwargs", "top_p"}.isdisjoint(sent)
    assert sent["messages"][1] == {"role": "assistant", "content": "A hint."}
    assert sent["response_format"] == body["response_format"] and sent["seed"] == 7  # kept as is
    strict = {"type": "json_schema", "json_schema": {"name": "x", "strict": True, "schema": {"type": "object"}}}
    relaxed = prepare_body({"messages": [], "response_format": strict})["response_format"]
    assert relaxed["json_schema"] == {"name": "x", "strict": False, "schema": {"type": "object"}}  # still decoded
    assert strict["json_schema"]["strict"] is True
    assert sent["store"] is False
    assert prepare_body(sent) == sent


def test_reasoning_never_reaches_the_device_in_replies_or_streams() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if json.loads(request.content)["stream"]:
            chunks = [
                {"choices": [{"index": 0, "delta": {"reasoning_content": "thinking..."}}]},
                {"choices": [{"index": 0, "delta": {"content": "What do you subtract?"}}]},
                {"choices": [], "usage": {"prompt_tokens": 50, "completion_tokens": 30,
                                          "completion_tokens_details": {"reasoning_tokens": 20}}},
            ]  # fmt: skip
            text = "".join(f"data: {json.dumps(c)}\n\n" for c in chunks) + "data: [DONE]\n\n"
            return httpx.Response(200, text=text, headers={"content-type": "text/event-stream"})
        reply = {
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "A hint.",
                                                 "reasoning_content": "thinking..."}}],
            "usage": {"prompt_tokens": 50, "completion_tokens": 30,
                      "completion_tokens_details": {"reasoning_tokens": 20}},
        }  # fmt: skip
        return httpx.Response(200, json=reply)

    async def run() -> None:
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        adapter = MetaAdapter(load_config().providers["meta"], Secret("synthetic-meta-key"), client)
        request = ProviderRequest(ModelSpec(id="muse-spark-1.3"), {"messages": []}, "synthetic")
        reply = await adapter.complete(request)
        assert reply.body["choices"][0]["message"] == {"role": "assistant", "content": "A hint."}
        # Reasoning tokens are part of completion_tokens: billed as reported, never added again.
        assert (reply.usage.output_tokens, reply.usage.reasoning_tokens) == (30, 20)
        parts = [part async for part in adapter.stream(request)]
        assert "thinking" not in json.dumps([p.chunk for p in parts])
        assert parts[-1].usage is not None and parts[-1].usage.output_tokens == 30
        await client.aclose()

    asyncio.run(run())


@pytest.mark.parametrize("environment", ["dev", "staging", "pilot", "production"])
def test_meta_key_comes_from_the_gateway_environment_only_and_never_shows(environment: str) -> None:
    source = secret_source(
        load_config(environment=environment), {"META_API_KEY": "fake-meta-key"}, KeychainSecrets(system="Plan9")
    )
    key = source.get("meta_api_key")
    assert key is not None and key.reveal() == "fake-meta-key"
    assert "fake-meta-key" not in repr(key) and "fake-meta-key" not in repr(source)
    assert source.get("nebius_api_key") is None


def test_secret_scanner_finds_a_meta_key() -> None:
    canary = b"LL" + b"M_" + b"1234567890_" + b"Ab3" * 10
    findings = scan_bytes(canary, "fixture")
    assert [f.pattern for f in findings] == ["meta_api_key"] and canary.decode() not in str(findings[0])


def test_shipped_models_prices_and_capabilities_agree() -> None:
    config = load_config()
    assert config.slots == {"primary": "meta"}
    provider = config.providers["meta"]
    assert provider.adapter == "meta" and provider.base_url == "https://api.meta.ai/v1"
    assert {alias: spec.id for alias, spec in provider.models.items()} == {
        "fast-model": "muse-spark-1.3",
        "strong-model": "muse-spark-1.3",
    }
    assert not any(spec.id.endswith("-contributor") for spec in provider.models.values())  # Standard mode only
    price = config.prices["muse-spark-1.3"]
    assert (price.input, price.cached_input, price.output) == (1.25, 0.15, 4.25)
    assert config.study_model == "primary/strong-model"
    assert set(cloud_models()) == set(provider.models)
    for alias, capabilities in cloud_models().items():
        assert capabilities["price_in_per_mtok"] == config.prices[provider.models[alias].id].input
        assert capabilities["price_out_per_mtok"] == config.prices[provider.models[alias].id].output
        assert capabilities["vision"] is True


def test_dev_config_uses_the_meta_keychain_service_and_a_persistent_ledger() -> None:
    config = load_config(ROOT / "services/cloud-gateway/deploy/meta-dev.toml")
    assert config.keychain_service == "jana-meta.cloud-gateway"
    assert config.storage_dir == Path.home() / ".jana-meta" / "gateway"  # survives restarts and temp cleanup
    assert config.quotas.deployment_total_spend_usd == 120.0 and config.quotas.deployment_daily_spend_usd == 10.0
    assert config.quotas.deployment_budget_expires_at is not None
    assert config.quotas.deployment_budget_expires_at.isoformat() >= "2026-11-05"


def test_request_uses_the_real_model_id_and_a_header_only_secret(tmp_path: Path) -> None:
    async def run() -> None:
        defaults = load_config()
        h = harness(
            gateway_config(
                tmp_path,
                slots=dict(defaults.slots),
                providers={"meta": defaults.providers["meta"].model_dump()},
                prices={key: value.model_dump() for key, value in defaults.prices.items()},
            )
        )
        device = Device()
        await device.login(h.client)
        h.stubs["meta"].say(Output(text="What can you subtract from both sides?"))
        request = {
            "model": "primary/fast-model",
            "messages": [{"role": "user", "content": "Help me solve 2x + 3 = 11."}],
            "reasoning_effort": "low",
            "max_tokens": 256,
        }
        response = await device.chat(h.client, request)
        assert response.status_code == 200, response.text
        sent = h.stubs["meta"].seen[-1]
        assert sent.url == "https://api.meta.ai/v1/chat/completions"
        assert sent.model == "muse-spark-1.3"
        assert sent.body["reasoning_effort"] == "minimal" and sent.body["store"] is False  # the fast alias's low
        assert sent.body["safety_identifier"] == device.pseudonym  # the per-session pseudonym, nothing else
        assert sent.headers["authorization"] == f"Bearer {FAKE_KEYS['meta_api_key']}"
        assert FAKE_KEYS["meta_api_key"] not in response.text and FAKE_KEYS["meta_api_key"] not in str(sent.body)
        await h.client.aclose()

    asyncio.run(run())


def test_router_prefers_spark_for_every_role_but_respects_the_online_switch() -> None:
    async def run() -> None:
        config = load(ROOT / "services/agent-core/agent_core/router/router.yaml")
        local = ScriptedProvider([], installed_models=["qwen3-vl-8b"])
        router = Router(
            config,
            Settings(),
            {"primary": ScriptedProvider([], kind="cloud"), "local": local},
            hardware_class="mid",
            cloud_on=lambda role: True,
        )
        for role, alias in (
            ("coach", "fast-model"),
            ("diagnoser", "fast-model"),
            ("solver", "strong-model"),
            ("checker", "strong-model"),
        ):
            _, candidates, _ = await router.candidates(role)
            assert str(candidates[0]) == f"cloud:primary/{alias}"
            assert not any("fallback" in str(c) for c in candidates)  # no other cloud provider (JM-D9)
        router.cloud_on = lambda role: False
        _, candidates, _ = await router.candidates("coach")
        assert candidates and all(candidate.locality == "local" for candidate in candidates)

    asyncio.run(run())


@pytest.mark.parametrize(
    ("alias", "asked", "sent"),
    [("fast-model", "low", "minimal"), ("fast-model", "high", "medium"), ("strong-model", "high", "low"),
     ("strong-model", "medium", "minimal")],
)  # fmt: skip
def test_each_alias_sets_how_much_spark_reasons_for_a_requested_effort(alias: str, asked: str, sent: str) -> None:
    spec = load_config().providers["meta"]
    adapter = MetaAdapter(spec, Secret("synthetic-meta-key"), httpx.AsyncClient())
    body = {"messages": [], "reasoning_effort": asked}
    assert adapter._body(ProviderRequest(spec.models[alias], body, "synthetic"), False)["reasoning_effort"] == sent
    assert body["reasoning_effort"] == asked  # the caller's body is not changed
    asyncio.run(adapter.aclose())
