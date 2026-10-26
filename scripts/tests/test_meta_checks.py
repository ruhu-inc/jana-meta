"""The day-1 Muse Spark check runner against a fake Meta endpoint: no network, no key, no spend."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

import httpx
import pytest
from jana_tools import REPO_ROOT, meta_checks


def fake_meta(request: httpx.Request) -> httpx.Response:
    body = json.loads(request.content)
    assert request.url == "https://api.meta.ai/v1/chat/completions"
    assert request.headers["authorization"] == "Bearer synthetic-meta-key"
    assert body["model"] == "muse-spark-1.3" and body.get("tool_choice") in (None, "auto")
    usage = {"prompt_tokens": 100, "completion_tokens": 40, "completion_tokens_details": {"reasoning_tokens": 25}}
    if body["stream"]:
        chunks = [
            {"choices": [{"index": 0, "delta": {"content": "An equation of degree one."}}]},
            {"choices": [], "usage": usage},
        ]
        text = "".join(f"data: {json.dumps(c)}\n\n" for c in chunks) + "data: [DONE]\n\n"
        return httpx.Response(200, text=text, headers={"content-type": "text/event-stream"})
    if body.get("tools"):
        call = {
            "id": "call_1",
            "type": "function",
            "function": {"name": "math_solve", "arguments": '{"equations": ["x=1"]}'},
        }
        message = {"role": "assistant", "content": None, "tool_calls": [call]}
    elif isinstance(body["messages"][-1]["content"], list):
        message = {"role": "assistant", "content": "2x + 3 = 11"}
    else:
        message = {"role": "assistant", "content": "not the schema's JSON"}
    return httpx.Response(200, json={"choices": [{"index": 0, "message": message}], "usage": usage})


def test_checks_run_through_the_ledger_and_write_a_report_without_reply_text(tmp_path: Path, monkeypatch) -> None:
    config = tmp_path / "meta-dev.toml"
    config.write_text((REPO_ROOT / "services/cloud-gateway/deploy/meta-dev.toml").read_text()
                      .replace('"~/.jana-meta/gateway"', json.dumps(str(tmp_path / "gateway"))))  # fmt: skip
    monkeypatch.setenv("META_API_KEY", "synthetic-meta-key")
    args = argparse.Namespace(
        config=config, model="muse-spark-1.3", max_usd=1.0, only=["tools", "json", "stream", "image"]
    )
    factory = lambda name, spec: httpx.AsyncClient(transport=httpx.MockTransport(fake_meta))  # noqa: E731
    status = asyncio.run(meta_checks.main_async(args, factory))
    assert status == 1  # the fake's Coach replies are not schema JSON, so one check fails
    [path] = (tmp_path / "checks").glob("muse-spark-1.3-*.json")
    report = json.loads(path.read_text())
    outcome = {r["name"]: r["passed"] for r in report["results"]}
    assert outcome == {"tools": True, "json": False, "stream": True, "image": True}
    assert report["spent_usd"] > 0  # every call was reserved and settled in the ledger
    assert "degree one" not in path.read_text() and "synthetic-meta-key" not in path.read_text()


def test_unknown_model_without_a_price_is_refused(tmp_path: Path) -> None:
    from cloud_gateway.config import load_config

    config = load_config(storage_dir=tmp_path)
    with pytest.raises(SystemExit, match="no configured price"):
        meta_checks.Run(config, "muse-wonder-1.0", 1.0)


def test_no_key_stops_before_any_call(tmp_path: Path, monkeypatch) -> None:
    from cloud_gateway import custody
    from cloud_gateway.config import load_config

    monkeypatch.delenv("META_API_KEY", raising=False)
    monkeypatch.setattr(custody, "KeychainSecrets", lambda *a, **k: custody.ChainedSecrets(()))
    config = load_config(REPO_ROOT / "services/cloud-gateway/deploy/meta-dev.toml", storage_dir=tmp_path)
    with pytest.raises(SystemExit, match="No Meta API key found"):
        meta_checks.Run(config, "muse-spark-1.3", 1.0)
    assert not (tmp_path / "gateway.db").exists() and not list(tmp_path.iterdir())  # no ledger touched
