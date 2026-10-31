"""Symbolic answers need whole-expression worker evidence, not matching exponent digits."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
from agent_core.engine import turn_scope
from agent_core.engine.state import Problem, state_from_json, state_to_json
from agent_core.engine.toolround import _checked_expressions
from engine_harness import close, last_check_id, make_engine, reply, tutor


@pytest.mark.parametrize(("tool", "args", "answer", "accepted"), [
    ("math_check_equivalence", {"a": "x^3*x^2", "b": "x^5"}, "x^5", True),
    ("math_simplify", {"expression": "x^3*x^2"}, "x^{5}", True),
    ("math_check_equivalence", {"a": "x^3*x^2", "b": "x^6"}, "x^6", False),
    ("math_simplify", {"expression": "y^3*y^2"}, "x^5", False),
    ("math_evaluate", {"expression": "3+2"}, "x^5", False),
])
def test_symbolic_answer_requires_the_whole_checked_expression(
    tmp_path: Path, tool: str, args: dict[str, Any], answer: str, accepted: bool,
) -> None:
    def plan(body: dict[str, Any]) -> dict:
        check = last_check_id(body)
        return reply(json.dumps({
            "status": "complete", "method_summary": "Use the product law for powers.",
            "steps": [{"index": 1, "latex": "3+2=5" if tool == "math_evaluate" else "x^3 x^2",
                       "value": "5" if tool == "math_evaluate" else None,
                       "unit": None, "check_id": None, "reason": "Same base", "kc_ref": None}],
            "final_answer": {"latex": answer, "value": answer, "unit": None,
                             "check_id": check, "plausible": True},
            "blocked_step": None, "blocked_reason": None,
        }))

    async def scenario() -> None:
        calls = [("c0", tool, args)]
        if tool == "math_check_equivalence":
            # The current solver also requires a calculation before returning its plan.
            calls.append(("c1", "math_evaluate", {"expression": "2+2"}))
        engine, _ = await make_engine(tmp_path, {
            "solver": [reply("", calls), plan] * 2,
            "coach": [tutor("What happens to the powers when the bases match?")] * 3,
        }, stage="S2")
        try:
            engine.state.problem = Problem("problem", "Simplify x^3 times x^2.", "question")
            turn = engine._begin("ask")
            with turn_scope(turn.turn_id):
                engine.state.plan = await engine._plan(turn)
            assert (engine.state.plan is not None) is accepted
            if accepted:
                assert engine.state.plan.final_value == answer
                restored = state_from_json(state_to_json(engine.state))
                engine.state = restored
                assert engine._check_for(answer, restored.plan.final_check_id) == restored.plan.final_check_id
                assert engine._check_for("z^5", restored.plan.final_check_id) is None
                assert engine._check_for("5", restored.plan.final_check_id) is None
        finally:
            await close(engine)

    asyncio.run(scenario())


@pytest.mark.parametrize(("confidence", "verdict", "assumptions"), [
    ("sampled", "equivalent", []),
    ("undecided", "unknown", []),
    ("proved", "equivalent_on_domain", []),
    ("proved", "not_equivalent", []),
    ("proved", "equivalent", ["x > 0"]),
])
def test_conditional_or_unproved_equivalence_is_not_answer_evidence(confidence, verdict, assumptions):
    assert _checked_expressions(
        "math_check_equivalence", {"a": "x/x", "b": "1", "assumptions": assumptions},
        {"value": {"verdict": verdict}, "check": {"confidence": confidence}},
    ) == []
