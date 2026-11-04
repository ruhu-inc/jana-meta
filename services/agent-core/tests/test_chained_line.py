"""A chained working line is judged by the value it states and by its plain arithmetic."""

import asyncio
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from agent_core.engine import team, turn_scope
from agent_core.engine.state import Plan, PlanStep, Problem
from engine_harness import close, make_engine, tutor


@pytest.mark.parametrize(
    ("line", "expected", "solved"),
    [
        ("a = 20 / 4 = 5 m/s^2", "correct", True),
        ("a = (25 - 5) / 4 = 5", "correct", True),
        ("a = (v - u) / t = 20 / 4 = 5 m/s^2", "correct", True),
        ("a = 20 / 2 = 10 m/s^2", "incorrect", False),
        ("a = 20 / 3 = 5 m/s^2", "incorrect", False),
    ],
)
def test_a_chained_line_is_judged_by_the_value_it_states(
    tmp_path: Path, line: str, expected: str, solved: bool
) -> None:
    async def scenario() -> None:
        engine, _ = await make_engine(tmp_path, {"coach": [tutor("Good.")]})
        try:
            engine.state.problem = Problem("prb_chain", "A car goes from 5 m/s to 25 m/s in 4 s. Find a.", "chain")
            engine.state.plan = Plan(
                [PlanStep(1, "a = (v - u)/t", "5", "m/s^2", "chk_chain")],
                "5",
                "m/s^2",
                "chk_chain",
                final_latex="a = 5",
            )
            engine.state.check_values["chk_chain"] = [Fraction(5)]
            turn = engine._begin("answer")
            with turn_scope(turn.turn_id):
                assert await engine._check_attempt(turn, line) == expected
            assert engine.state.solved is solved
        finally:
            await close(engine)

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("lean", "status", "asked"), [(True, "incorrect", False), (True, "unchecked", True), (False, "incorrect", True)]
)
def test_a_lean_class_skips_the_checker_only_on_a_wrong_answer_the_code_decided(
    monkeypatch: pytest.MonkeyPatch, lean: bool, status: str, asked: bool
) -> None:
    calls: list[str] = []

    async def delegate(role: str, _task: str, _turn: Any) -> dict[str, Any]:
        calls.append(role)
        return {}

    async def diagnose(*_args: Any, **_kwargs: Any) -> None:
        return None

    monkeypatch.setattr(team, "diagnose", diagnose)
    engine = SimpleNamespace(state=SimpleNamespace(problem=SimpleNamespace(statement="Find a.")), delegate=delegate,
                             _lean=lambda: lean)  # fmt: skip
    asyncio.run(team.read_answer(engine, None, "a = 10", status))
    assert calls == (["checker"] if asked else [])
