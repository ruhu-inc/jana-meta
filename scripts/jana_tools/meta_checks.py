"""The day-1 checks of Muse Spark (SPEC §4.4), run through the gateway's own adapter and spending ledger.

    uv run python -m jana_tools.meta_checks [--model muse-spark-1.2] [--only tools,json,stream,image,latency]

The key is read the way the gateway reads it (the keychain item jana-meta.cloud-gateway / meta_api_key, or a
gateway-only META_API_KEY) and is never printed. Every call is reserved against the dev config's daily, total and
expiry limits before it is sent, and the run stops once it has spent `--max-usd`. Prompts are synthetic; the report
keeps outcomes, counts, timings and token usage only, never a reply's text.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import io
import json
import statistics
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from cloud_gateway.config import GatewayConfig, ModelSpec, load_config
from cloud_gateway.custody import secret_source
from cloud_gateway.inference_budget import InferenceBudget
from cloud_gateway.providers import ClientFactory, Providers, default_client
from cloud_gateway.providers.base import ProviderAdapter, ProviderRequest, UpstreamError, Usage
from cloud_gateway.store import GatewayStore
from jsonschema import Draft202012Validator

from jana_tools import REPO_ROOT

CONFIG = REPO_ROOT / "services/cloud-gateway/deploy/meta-dev.toml"
TUTOR_TURN = REPO_ROOT / "contracts/agents/tutor-turn.schema.json"
MATH_SOLVE = {
    "type": "function",
    "function": {
        "name": "math_solve",
        "description": "Solves equations exactly. Always use it before stating any value.",
        "parameters": {
            "type": "object",
            "properties": {"equations": {"type": "array", "items": {"type": "string"}}},
            "required": ["equations"],
        },
    },
}
EQUATIONS = ["3x - 4 = 11", "2x + 3 = 11", "5y = 35", "7 - x = 2", "4(a + 1) = 20",
             "x/3 = 6", "9 = 2t + 1", "6k - 5 = 4k + 7", "0.5m = 4", "3(2p - 1) = 15"]  # fmt: skip
COACH_SYSTEM = (
    "You are Jana, a patient maths tutor for an adult learner. Never give the final answer. Ask one guiding question "
    "at a time. Reply only with the JSON object the schema describes."
)


@dataclass
class Result:
    name: str
    passed: bool
    detail: str
    numbers: dict[str, Any] = field(default_factory=dict)


class Run:
    def __init__(
        self, config: GatewayConfig, model: str, max_usd: float, client_factory: ClientFactory = default_client
    ) -> None:
        if model not in config.prices:
            raise SystemExit(f"{model} has no configured price; add it to defaults.toml first")
        self.config, self.model = config, ModelSpec(id=model)
        secrets = secret_source(config)
        if secrets.get(config.providers["meta"].secret) is None:
            raise SystemExit(
                "No Meta API key found. Add it to the login keychain (service jana-meta.cloud-gateway, account "
                "meta_api_key) or set META_API_KEY for this command only; nothing was sent."
            )
        self.store = GatewayStore(config.storage_dir)
        self.budget = InferenceBudget(config, self.store, time.time)
        self.providers = Providers(config, secrets, client_factory, budget=self.budget)
        self.adapter: ProviderAdapter = self.providers.adapters["meta"]
        self.start_spent = self._spent()
        self.max_usd = max_usd

    def _spent(self) -> float:
        snapshot = self.budget.snapshot()
        return float(snapshot["spent_usd"] + snapshot["held_usd"])

    def _guard(self) -> None:
        if self._spent() - self.start_spent >= self.max_usd:
            raise SystemExit(f"stopped: this run reached its --max-usd {self.max_usd:.2f}")

    async def complete(self, body: dict[str, Any]) -> tuple[dict[str, Any], Usage, float]:
        self._guard()
        started = time.perf_counter()
        reply = await self.adapter.complete(ProviderRequest(self.model, body, "meta-checks"))
        return reply.body, reply.usage, time.perf_counter() - started

    async def close(self) -> None:
        await self.providers.aclose()
        self.store.close()


def _message(body: dict[str, Any]) -> dict[str, Any]:
    return (body.get("choices") or [{}])[0].get("message") or {}


async def check_tools(run: Run) -> Result:
    """1. The Solver calls tools with tool_choice auto (the adapter maps the engine's `required`)."""
    called, errors = 0, []
    for equation in EQUATIONS:
        body = {
            "messages": [
                {"role": "system", "content": "You are a maths solver. Use math_solve for every equation."},
                {"role": "user", "content": f"Solve {equation}."},
            ],
            "tools": [MATH_SOLVE],
            "tool_choice": "required",
            "reasoning_effort": "high",
            "max_tokens": 4096,
        }
        try:
            reply, _, _ = await run.complete(body)
        except UpstreamError as error:
            errors.append(error.reason)
            continue
        calls = _message(reply).get("tool_calls") or []
        good = [c for c in calls if c.get("function", {}).get("name") == "math_solve"]
        if good and isinstance(json.loads(good[0]["function"].get("arguments") or "{}").get("equations"), list):
            called += 1
    return Result("tools", called >= 9, f"{called}/10 called math_solve with valid arguments",
                  {"called": called, "errors": errors})  # fmt: skip


async def check_json(run: Run) -> Result:
    """2. Coach turns validate against tutor-turn.schema.json on the first try."""
    schema = json.loads(TUTOR_TURN.read_text())
    validator = Draft202012Validator(schema)
    valid, errors = 0, []
    for index, equation in enumerate(EQUATIONS):
        body = {
            "messages": [
                {"role": "system", "content": COACH_SYSTEM},
                {"role": "user", "content": f"I need help with {equation}. I don't know where to start. (#{index})"},
            ],
            "response_format": {"type": "json_schema", "json_schema": {"name": "tutor_turn", "strict": True,
                                                                        "schema": schema}},
            "reasoning_effort": "low",
            "max_tokens": 4096,
        }  # fmt: skip
        try:
            reply, _, _ = await run.complete(body)
            content = _message(reply).get("content") or ""
            if not list(validator.iter_errors(json.loads(content))):
                valid += 1
        except UpstreamError as error:
            errors.append(f"{error.reason}:{error.param or ''}")
        except ValueError:
            errors.append("not_json")
    return Result("json", valid == 10, f"{valid}/10 Coach turns valid first time", {"valid": valid, "errors": errors})


async def check_stream(run: Run) -> Result:
    """3. Streaming returns usage on the final chunk, with reasoning tokens."""
    run._guard()
    body = {"messages": [{"role": "user", "content": "In one sentence, what is a linear equation?"}],
            "reasoning_effort": "low", "max_tokens": 1024}  # fmt: skip
    usage, chunks, first = None, 0, None
    started = time.perf_counter()
    async for part in run.adapter.stream(ProviderRequest(run.model, body, "meta-checks")):
        if part.chunk is not None:
            chunks += 1
            first = first or time.perf_counter() - started
        else:
            usage = part.usage
    ok = usage is not None and usage.input_tokens > 0 and usage.output_tokens > 0
    numbers = {"chunks": chunks, "first_chunk_s": round(first or 0, 2)}
    if usage is not None:
        numbers.update(input=usage.input_tokens, output=usage.output_tokens, reasoning=usage.reasoning_tokens)
    return Result("stream", ok, "usage present on the final chunk" if ok else "no usage on the stream", numbers)


def _equation_png() -> str:
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (640, 200), "white")
    ImageDraw.Draw(image).text((40, 70), "2x + 3 = 11", fill="black", font_size=72)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()


async def check_image(run: Run) -> Result:
    """4. Image input (a data URL) is accepted and read."""
    body = {
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": "Copy the equation in this image exactly, and nothing else."},
            {"type": "image_url", "image_url": {"url": _equation_png()}},
        ]}],
        "reasoning_effort": "low",
        "max_tokens": 1024,
    }  # fmt: skip
    try:
        reply, usage, seconds = await run.complete(body)
    except UpstreamError as error:
        return Result("image", False, f"refused: {error.reason}", {})
    text = (_message(reply).get("content") or "").replace(" ", "")
    ok = "2x+3=11" in text
    return Result("image", ok, "read the equation" if ok else "accepted but misread",
                  {"input_tokens": usage.input_tokens, "seconds": round(seconds, 2)})  # fmt: skip


async def check_latency(run: Run) -> Result:
    """5. Time to a complete Coach turn at reasoning_effort low (target ≤ 3 s typical, SPEC §12)."""
    schema = json.loads(TUTOR_TURN.read_text())
    times = []
    for equation in EQUATIONS[:5]:
        body = {
            "messages": [{"role": "system", "content": COACH_SYSTEM},
                         {"role": "user", "content": f"Help me start {equation}."}],
            "response_format": {"type": "json_schema", "json_schema": {"name": "tutor_turn", "schema": schema}},
            "reasoning_effort": "low",
            "max_tokens": 4096,
        }  # fmt: skip
        try:
            _, _, seconds = await run.complete(body)
            times.append(seconds)
        except UpstreamError:
            continue
    if not times:
        return Result("latency", False, "no turn completed", {})
    median = statistics.median(times)
    return Result("latency", median <= 3.0, f"median {median:.2f} s over {len(times)} turns",
                  {"median_s": round(median, 2), "max_s": round(max(times), 2)})  # fmt: skip


CHECKS = {"tools": check_tools, "json": check_json, "stream": check_stream, "image": check_image,
          "latency": check_latency}  # fmt: skip


async def main_async(args: argparse.Namespace, client_factory: ClientFactory = default_client) -> int:
    config = load_config(args.config)
    run = Run(config, args.model, args.max_usd, client_factory)
    results: list[Result] = []
    try:
        for name in args.only:
            try:
                results.append(await CHECKS[name](run))
            except UpstreamError as error:
                results.append(Result(name, False, f"provider: {error.reason}", {}))
            print(f"{'PASS' if results[-1].passed else 'FAIL'}  {name:8} {results[-1].detail}", flush=True)
    finally:
        spent = run._spent() - run.start_spent
        await run.close()
    report = {"model": args.model, "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "spent_usd": spent,
              "results": [r.__dict__ for r in results]}  # fmt: skip
    folder = config.storage_dir.parent / "checks"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{args.model}-{report['at']}.json"
    path.write_text(json.dumps(report, indent=2))
    print(f"spent about ${spent:.4f} (held amounts included); report: {path}")
    return 0 if all(r.passed for r in results) else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--model", default="muse-spark-1.3")
    parser.add_argument("--max-usd", type=float, default=1.0)
    parser.add_argument("--only", type=lambda s: [x.strip() for x in s.split(",")], default=list(CHECKS))
    args = parser.parse_args()
    if unknown := [name for name in args.only if name not in CHECKS]:
        parser.error(f"unknown checks: {', '.join(unknown)}")
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    sys.exit(main())
