"""Tutoring-turn latency on Muse Spark (SPEC §12): seeded Maths and Physics turns through the shipped engine.

    uv run python -m jana_tools.turn_latency [--only maths-linear,phys-car] [--max-usd 1.0] [--out DIR]

The engine is assembled as the app assembles it, with the sandboxed tool worker, and its cloud tier is the gateway's
own Meta adapter and spending ledger, called in-process in place of the HTTP hop (`InProcessGateway`): the device's
request body, the gateway's minimisation, the alias's effort mapping and the daily, total and expiry caps are the real
ones, and the key is read the way the gateway reads it. The run stops once it has spent `--max-usd`.

Each case is a full guided turn: the opening of a typed question (input guard, Diagnoser, Solver and its tools,
Coach, gates), or a student's follow-up in that session. The report gives per-call and total timings, the time to the
first text the student sees, and a quality check per turn: the Solver's numbers came from tool calls, every number on
the board traces to a check, nothing withheld (the answer, a step not reached) appears in what the student is shown,
and the turn was not degraded. Prompts are synthetic; the report keeps timings, token counts, check outcomes and the
shown text of these synthetic turns only.
"""

from __future__ import annotations

import argparse
import asyncio
import functools
import json
import re
import statistics
import sys
import tempfile
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Any

from jana_tools import REPO_ROOT

CONFIG = REPO_ROOT / "services/cloud-gateway/deploy/meta-dev.toml"


@dataclass(frozen=True)
class Case:
    """One seeded turn. `follows` names the case whose session this follow-up continues; `leaks` are patterns that
    would give away what the student must still find; `computes` says the Solver must plan it with tools."""

    name: str
    subject: str
    text: str
    leaks: tuple[str, ...] = ()
    computes: bool = True
    follows: str | None = None
    core: bool = True  # one of the ten seeded turns the median is reported on


CASES = (
    Case("maths-linear", "mathematics", "Solve 7x \u2212 3 = 18", (r"x\s*=\s*3\b",)),
    Case("maths-linear-wrong", "mathematics", "x = 2", (r"x\s*=\s*3\b",), follows="maths-linear"),
    Case("maths-brackets", "mathematics", "Solve 5(x + 2) = 35", (r"x\s*=\s*5\b",)),
    Case("maths-percent", "mathematics", "What is 15% of 240?", (r"\b36\b",)),
    Case("maths-triangle", "mathematics", "Find the area of a triangle with base 12 cm and height 9 cm.", (r"\b54\b",)),
    Case("phys-car", "physics", "A car speeds up from rest to 20 m/s in 5 s. What is its acceleration?",
         (r"\b4\s*m\s*/\s*s",)),
    Case("phys-car-right", "physics", "a = (20 - 0)/5 = 4 m/s^2", (), follows="phys-car"),
    Case("phys-force", "physics", "A 2 kg mass accelerates at 3 m/s². What resultant force acts on it?",
         (r"\b6\s*N\b",)),
    Case("phys-ohm", "physics", "A 12 V battery drives a current of 0.5 A through a resistor. What is its resistance?",
         (r"\b24\b",)),
    Case("phys-define-speed", "physics", "What is meant by the term speed?", (), computes=False),
)  # fmt: skip
# Wrong answers to the openings above (`--wrong-answers`): each runs the Checker, for its verdict and redo counts. They
# are follow-ups in the opening's session, reported apart from the ten seeded turns.
WRONG_ANSWERS = (
    Case("maths-brackets-wrong", "mathematics", "x = 7", (r"x\s*=\s*5\b",), follows="maths-brackets", core=False),
    Case("maths-percent-wrong", "mathematics", "24", (r"\b36\b",), follows="maths-percent", core=False),
    Case("maths-triangle-wrong", "mathematics", "108 cm^2", (r"\b54\b",), follows="maths-triangle", core=False),
    Case("phys-force-wrong", "physics", "F = 1.5 N", (r"\b6\s*N\b",), follows="phys-force", core=False),
    Case("phys-ohm-wrong", "physics", "R = 6 ohm", (r"\b24\b",), follows="phys-ohm", core=False),
)


@dataclass
class CallRecord:
    role: str
    alias: str
    start_s: float  # from the start of the turn
    seconds: float
    first_chunk_s: float | None
    stream: bool
    input_tokens: int
    output_tokens: int
    reasoning_tokens: int
    cached_tokens: int
    effort: str | None
    tools_offered: int
    tool_calls: int
    max_tokens: int | None
    tools_called: list[str] = field(default_factory=list)
    reply: str | None = None  # a specialist's structured reply (synthetic problems only), when --replies is set


@dataclass
class Clock:
    """The current turn's start, so each call is placed on the turn's timeline."""

    started: float = field(default_factory=time.perf_counter)
    calls: list[CallRecord] = field(default_factory=list)

    def now(self) -> float:
        return time.perf_counter() - self.started


class InProcessGateway:
    """The engine's egress client, served by the gateway's own provider pipeline in this process: the same model
    resolution, minimisation and budgeted Meta adapter as `cloud_gateway.app.Gateway.chat`, without the HTTP hop and
    the device credential (this is a development measurement, never an app path)."""

    def __init__(self, config: Any, max_usd: float) -> None:
        from cloud_gateway.custody import secret_source
        from cloud_gateway.inference_budget import InferenceBudget
        from cloud_gateway.providers import Providers, default_client
        from cloud_gateway.store import GatewayStore

        secrets = secret_source(config)
        if secrets.get(config.providers["meta"].secret) is None:
            raise SystemExit(
                "No Meta API key found. Add it to the login keychain (service jana-meta.cloud-gateway, account "
                "meta_api_key) or set META_API_KEY for this command only; nothing was sent."
            )
        self.store = GatewayStore(config.storage_dir)
        self.budget = InferenceBudget(config, self.store, time.time)
        self.providers = Providers(config, secrets, default_client, budget=self.budget)
        self.start_spent = self.spent()
        self.max_usd = max_usd
        self.clock = Clock()
        self.failures: list[dict[str, Any]] = []
        self.keep_replies = False

    def spent(self) -> float:
        snapshot = self.budget.snapshot()
        return float(snapshot["spent_usd"] + snapshot["held_usd"])

    def run_usd(self) -> float:
        return self.spent() - self.start_spent

    def _resolve(self, body: dict[str, Any], headers: dict[str, str]) -> tuple[Any, Any, dict[str, Any]]:
        from cloud_gateway import minimise
        from cloud_gateway.providers.base import ProviderRequest

        if self.run_usd() >= self.max_usd:
            raise SystemExit(f"stopped: this run reached its --max-usd {self.max_usd:.2f}")
        resolved = self.providers.resolve(body.get("model"))
        if resolved is None:
            raise SystemExit(f"the gateway does not serve {body.get('model')}")
        _, adapter, model = resolved
        upstream = ProviderRequest(model, minimise.forwarded(body), headers["x-session-pseudonym"])
        return adapter, upstream, upstream.body

    def _record(self, body: dict[str, Any], headers: dict[str, str], start: float, first: float | None,
                usage: Any, tool_calls: int, stream: bool) -> None:  # fmt: skip
        self.clock.calls.append(CallRecord(
            headers.get("x-jana-role", "unspecified"), str(body.get("model")), round(start, 2),
            round(self.clock.now() - start, 2), round(first - start, 2) if first is not None else None, stream,
            usage.input_tokens, usage.output_tokens, usage.reasoning_tokens, usage.cached_tokens,
            body.get("reasoning_effort"),
            len(body.get("tools") or []), tool_calls, body.get("max_tokens") or body.get("max_completion_tokens"),
        ))  # fmt: skip

    async def send(self, feature: str, method: str, url: str, payload_class: str, *, body: Any = None,
                   headers: dict[str, str] | None = None, **_: Any) -> Any:  # fmt: skip
        from agent_core.net.client import Response

        headers = dict(headers or {})
        adapter, upstream, _sent = self._resolve(body, headers)
        start = self.clock.now()
        try:
            reply = await adapter.complete(upstream)
        except Exception as raised:  # as the gateway replies to the device (`cloud_gateway.app.Gateway.chat`)
            from cloud_gateway.app import _upstream
            from cloud_gateway.errors import device_error

            failure = _upstream(raised)
            error = device_error(failure.reason, failure.retry_after_s, failure.param)
            self.failures.append({"role": headers.get("x-jana-role", "unspecified"), "reason": failure.reason,
                                  "param": failure.param, "message": failure.message[:300]})  # fmt: skip
            return Response(error.status, error.headers(), error.body())
        message = (reply.body.get("choices") or [{}])[0].get("message") or {}
        self._record(body, headers, start, None, reply.usage, len(message.get("tool_calls") or []), False)
        self.clock.calls[-1].tools_called = [f"{c['function']['name']}({c['function'].get('arguments', '')[:120]})"
                                             for c in message.get("tool_calls") or []]  # fmt: skip
        if self.keep_replies and headers.get("x-jana-role") != "coach":
            self.clock.calls[-1].reply = str(message.get("content") or "")[:4000]
        return Response(200, {}, reply.body)

    async def stream_events(self, feature: str, url: str, payload_class: str, body: Any, *,
                            headers: dict[str, str] | None = None, **_: Any) -> AsyncIterator[Any]:  # fmt: skip
        from cloud_gateway.providers.base import Usage

        headers = dict(headers or {})
        adapter, upstream, _sent = self._resolve(body, headers)
        start, first, usage, last, calls = self.clock.now(), None, Usage(), None, 0
        texts: list[str] = []
        try:
            async for part in adapter.stream(upstream):
                if part.chunk is not None:
                    if first is None:
                        first = self.clock.now()
                    last = part.chunk
                    for choice in part.chunk.get("choices") or []:
                        calls += len((choice.get("delta") or {}).get("tool_calls") or [])
                        texts.append(str((choice.get("delta") or {}).get("content") or ""))
                    yield part.chunk
                if part.usage is not None:
                    usage = part.usage
        except Exception as raised:  # as the gateway replies: an error before the first chunk, else an error event
            from agent_core.net.client import Response
            from cloud_gateway.app import _upstream
            from cloud_gateway.errors import device_error

            failure = _upstream(raised)
            error = device_error(failure.reason, failure.retry_after_s)
            self.failures.append({"role": headers.get("x-jana-role", "unspecified"), "reason": failure.reason,
                                  "param": failure.param, "message": failure.message[:300]})  # fmt: skip
            yield Response(error.status, error.headers(), error.body()) if first is None else error.body()
            return
        self._record(body, headers, start, first, usage, calls, True)
        if self.keep_replies:
            self.clock.calls[-1].reply = "".join(texts)[:6000]
        yield {"id": (last or {}).get("id", "chatcmpl"), "object": "chat.completion.chunk", "choices": [],
               "usage": usage.openai()}  # fmt: skip

    async def close(self) -> None:
        await self.providers.aclose()
        self.store.close()


@functools.cache
def knowledge() -> Any:
    """The O-level Maths and Physics packs, from the curriculum sources the installed packs are built from."""
    from agent_core.retrieval.index import KnowledgeIndex
    from pack_builder.build import load_source

    sources = [load_source(REPO_ROOT / "content" / "curriculum" / code / "o") for code in ("mth", "phy")]
    return KnowledgeIndex.from_tables([(dict(s.pack), {t: list(rows) for t, rows in s.tables.items()})
                                       for s in sources])  # fmt: skip


async def open_engine(gateway: InProcessGateway, subject: str, out: Path, supervisor: Any) -> Any:
    """The shipped engine on the online tier only, as the browser demo host runs it with no local model."""
    from agent_core.config import Settings
    from agent_core.engine.assembly import assemble
    from agent_core.engine.events import new_id
    from agent_core.engine.state import SessionState
    from agent_core.providers.gateway import GatewayProvider, cloud_capabilities
    from agent_core.router.online import cloud_models

    from jana_tools.hackathon_app import settings_for_browser

    settings = settings_for_browser(Settings())
    models = cloud_models()
    caps = {m: cloud_capabilities(int(v["context"]), int(v["max_output"]), bool(v["vision"]))
            for m, v in models.items()}  # fmt: skip
    prices = {m: (float(v["price_in_per_mtok"]), float(v["price_out_per_mtok"])) for m, v in models.items()}
    provider = GatewayProvider(gateway, lambda: "localhost", "primary", caps=caps, prices=prices)  # type: ignore[arg-type]
    state = SessionState(new_id("ses"), subject=subject, level="O", mode="guided", origin="ask")
    engine = assemble({"primary": provider}, settings, state, REPO_ROOT / "content" / "agent", REPO_ROOT / "skills",
                      out / "spill", supervisor, session_date="2026-10-26", cloud_on=lambda role: True)  # fmt: skip
    engine.deps.router.network = lambda: "online"
    engine.bind_knowledge(knowledge())  # as the app binds the installed packs
    engine.plan_gaps = []
    verified = engine._verified_plan

    def recorded(envelope: dict[str, Any]) -> tuple[Any, str]:  # why a Solver plan was refused, for the report
        plan, gap = verified(envelope)
        engine.plan_gaps.append({"gap": gap, "stop": envelope.get("stop_reason"), "errors": envelope.get("errors"),
                                 "steps": [(s.get("latex"), s.get("value"), s.get("check_id"))
                                 for s in ((envelope.get("output") or {}).get("steps") or [])]} if plan is None
                                else {"gap": ""})  # fmt: skip
        return plan, gap

    engine._verified_plan = recorded
    return engine


def _numbers(text: str) -> list[Fraction]:
    from agent_core.engine.state import numbers_in

    return list(numbers_in(text))


def quality(case: Case, engine: Any, turn_id: str, shown: str, result: Any, withheld: list[Any]) -> dict[str, Any]:
    """The rules the speed-up must keep: tools for the numbers, checked board, nothing withheld shown, no
    degradation."""
    state = engine.state
    trace = engine.traces[-1] if engine.traces else {}
    tools = [c for c in trace.get("tool_calls", []) if c.get("status") == "ok"]
    board = [s for s in state.board.steps if s.owner != "student"]
    leaks = [p for p in case.leaks if re.search(p, shown, re.IGNORECASE)]
    # Values the engine withheld before the turn that appear in what was shown (PED-08): the gate's own test.
    stated = set(_numbers(case.text))
    shown_values = set(_numbers(shown))
    withheld_shown = [str(v) for v, _ in withheld if v in shown_values and v not in stated]
    opening = case.follows is None
    checks = {
        "shown_text": bool(shown.strip()),
        "not_degraded": result.degraded_reason is None,
        "plan_verified": state.plan is not None if opening and case.computes else True,
        "tools_called": bool(tools) if opening and case.computes else True,
        "board_checked": all(s.check_id for s in board),
        "no_answer_leak": not leaks and not withheld_shown,
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "leaks": leaks,
        "withheld_shown": withheld_shown,
        "tool_calls": len(tools),
        "gates_fired": [g["gate"] for g in trace.get("gates", []) if g.get("fired")],
    }


async def run_case(case: Case, engine: Any, gateway: InProcessGateway) -> dict[str, Any]:
    first_text: list[float] = []
    timeline: list[tuple[float, str]] = []
    emit = engine.events.emit

    def watched(event: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        if event.get("type") == "text.delta" and not first_text:
            first_text.append(gateway.clock.now())
        timeline.append((round(gateway.clock.now(), 2), str(event.get("type"))))
        return emit(event, **kwargs)

    engine.events.emit = watched
    withheld = list(engine.state.withheld())
    engine.plan_gaps.clear()
    gateway.clock = Clock()
    gateway.failures = []
    try:
        result = await (engine.start_problem(case.text) if case.follows is None else engine.student_turn(case.text))
    finally:
        engine.events.emit = emit
    total = gateway.clock.now()
    shown = engine.events.student_text(result.turn_id)
    calls = gateway.clock.calls
    return {
        "case": case.name,
        "core": case.core,
        "subject": case.subject,
        "total_s": round(total, 2),
        "first_text_s": round(first_text[0], 2) if first_text else None,
        "model_s": round(sum(c.seconds for c in calls), 2),
        "status": result.status,
        "stop_reason": result.stop_reason,
        "degraded_reason": result.degraded_reason,
        "calls": [c.__dict__ for c in calls],
        "quality": quality(case, engine, result.turn_id, shown, result, withheld),
        "shown": shown,
        "plan_gaps": list(engine.plan_gaps),
        "gates": [
            (g["gate"], g.get("nudges", 0), g.get("outcome"), g.get("reason"))
            for g in (engine.traces[-1].get("gates", []) if engine.traces else [])
            if g.get("fired")
        ],
        "failures": gateway.failures,
        "events": timeline,
        "phases": [
            (p["phase"], p["start_offset_ms"], p["duration_ms"])
            for p in (engine.traces[-1].get("phases", []) if engine.traces else [])
        ],
    }


def checker_redos(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Each turn's Checker verdict: written while tools were offered (unconstrained), or redone by a decode-only call
    after it broke the verdict contract."""
    verdicts = redone = 0
    for r in results:
        calls = [c for c in r["calls"] if c["role"] == "checker"]
        if not calls:
            continue
        verdicts += 1
        redone += any(c["tools_offered"] == 0 for c in calls)
    return {"verdicts": verdicts, "redone": redone, "rate": round(redone / verdicts, 2) if verdicts else None}


def summary(results: list[dict[str, Any]], spent: float) -> dict[str, Any]:
    core = [r for r in results if r.get("core", True)]
    totals = [r["total_s"] for r in core]
    firsts = [r["first_text_s"] for r in results if r["first_text_s"] is not None]
    by_role: dict[str, list[float]] = {}
    for r in results:
        for c in r["calls"]:
            by_role.setdefault(c["role"], []).append(c["seconds"])
    return {
        "turns": len(results),
        "median_total_s": round(statistics.median(totals), 2) if totals else None,
        "p90_total_s": round(statistics.quantiles(totals, n=10)[-1], 2) if len(totals) > 1 else None,
        "core_turns": len(core),
        "checker": checker_redos(results),
        "max_total_s": max(totals) if totals else None,
        "median_first_text_s": round(statistics.median(firsts), 2) if firsts else None,
        "quality_passed": sum(r["quality"]["passed"] for r in results),
        "per_role_median_s": {k: round(statistics.median(v), 2) for k, v in sorted(by_role.items())},
        "per_role_calls": {k: len(v) for k, v in sorted(by_role.items())},
        "spent_usd": round(spent, 4),
    }


def table(results: list[dict[str, Any]]) -> list[str]:
    lines = [f"{'case':<20}{'total':>7}{'first':>7}  ok  calls (role seconds/reasoning tokens)"]
    for r in results:
        calls = " ".join(f"{c['role'][:5]}@{c['start_s']}+{c['seconds']}/{c['reasoning_tokens']}"
                         for c in r["calls"])  # fmt: skip
        first = "-" if r["first_text_s"] is None else f"{r['first_text_s']:.1f}"
        failed = [k for k, v in r["quality"]["checks"].items() if not v]
        ok = "yes" if r["quality"]["passed"] else "NO " + ",".join(failed)
        lines.append(f"{r['case']:<20}{r['total_s']:>7.1f}{first:>7}  {ok}  {calls}")
    return lines


async def main_async(args: argparse.Namespace) -> int:
    from agent_core.config import Settings
    from agent_core.tools.worker import WorkerSupervisor
    from agent_core.tools.worker.launch import process_factory
    from cloud_gateway.config import load_config

    wanted = set(args.only.split(",")) if args.only else None
    seeded = CASES + (WRONG_ANSWERS if args.wrong_answers else ())
    cases = [c for c in seeded if wanted is None or c.name in wanted or (c.follows in wanted if c.follows else False)]
    out = Path(args.out or tempfile.mkdtemp(prefix="jana-turn-latency-"))
    out.mkdir(parents=True, exist_ok=True)
    config = load_config(Path(args.config))
    for override in args.thinking or []:  # an experiment only: `strong-model.high=minimal`
        target, effort = override.split("=")
        alias, asked = target.split(".")
        spec = config.providers["meta"].models[alias]
        assert spec.thinking is not None
        config.providers["meta"].models[alias] = spec.model_copy(
            update={"thinking": spec.thinking.model_copy(update={asked: effort})}
        )
    for override in args.model or []:  # an experiment only: `fast-model=muse-spark-1.2`
        alias, model_id = override.split("=")
        models = config.providers["meta"].models
        models[alias] = models[alias].model_copy(update={"id": model_id})
    gateway = InProcessGateway(config, args.max_usd)
    gateway.keep_replies = args.replies
    settings = Settings(worker_pool_size=2, worker_respawn_backoff_s=(0.0,))
    supervisor = WorkerSupervisor(process_factory(settings, scratch_root=out / "scratch"), settings)
    await supervisor.start()
    engines: dict[str, Any] = {}
    results = []
    try:
        try:
            for _ in range(args.repeat):
                for case in cases:
                    if case.follows is None:
                        engines[case.name] = await open_engine(gateway, case.subject, out, supervisor)
                    elif case.follows not in engines:
                        continue
                    engine = engines[case.name if case.follows is None else case.follows]
                    result = await run_case(case, engine, gateway)
                    results.append(result)
                    print(table([result])[1], flush=True)
        except SystemExit as stopped:  # --max-usd reached mid-turn: report the turns that finished
            print(stopped, flush=True)
        spent = gateway.run_usd()
    finally:
        await supervisor.close()
        await gateway.close()
    report = {"summary": summary(results, spent), "results": results}
    (out / "report.json").write_text(json.dumps(report, indent=1, ensure_ascii=False))
    print("\n".join(table(results)))
    print(json.dumps(report["summary"], indent=1))
    print(f"report: {out / 'report.json'}")
    return 0 if report["summary"]["quality_passed"] == len(results) else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", default=str(CONFIG))
    parser.add_argument("--only", help="comma-separated case names (a follow-up runs with its opening)")
    parser.add_argument("--max-usd", type=float, default=1.0)
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--out")
    parser.add_argument("--model", action="append", help="try another model for an alias: alias=model id")
    parser.add_argument("--wrong-answers", action="store_true", help="add wrong answers that run the Checker")
    parser.add_argument("--replies", action="store_true", help="keep specialists' replies in the report")
    parser.add_argument("--thinking", action="append", help="try another Spark effort: alias.asked=sent")
    return asyncio.run(main_async(parser.parse_args()))


if __name__ == "__main__":
    sys.exit(main())
