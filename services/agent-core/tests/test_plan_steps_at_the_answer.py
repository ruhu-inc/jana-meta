"""A Solver plan's step on the way ("7x = 21" before "x = 3") is checked at the answer a tool found (AGT-10, §12).

`math_solve` gives only the answer, so a step on the way to it had no check, the plan was refused and the retry came
back as one step ("7x - 3 = 18 => x = 3"), slower and worse to teach from. The engine now evaluates the step's side in
the unknown at the checked answer with `math_evaluate`; a step that does not hold there still has no check."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
from engine_harness import close, last_check_id, make_engine, reply, tutor

STATEMENT = "Solve 7x - 3 = 18"


def solver(first_step: str, first_value: str) -> list[Any]:
    def plan(body: dict[str, Any]) -> dict:
        check = last_check_id(body)
        step = {"reason": "", "kc_ref": None, "unit": None}
        return reply(json.dumps({
            "status": "complete", "method_summary": "Add 3 to both sides, then divide by 7.",
            "steps": [{**step, "index": 1, "latex": first_step, "value": first_value, "check_id": check},
                      {**step, "index": 2, "latex": "x=3", "value": "3", "check_id": check}],
            "final_answer": {"latex": "x=3", "value": "3", "unit": None, "check_id": check, "plausible": True},
            "blocked_step": None, "blocked_reason": None,
        }))  # fmt: skip

    return [reply("", [("c0", "math_solve", {"equations": ["7*x-3=18"], "unknowns": ["x"]})]), plan]


@pytest.mark.parametrize(("first_step", "first_value", "verified"), [("7x=21", "21", True), ("7x=24", "24", False)])
def test_a_step_is_checked_at_the_answer_a_tool_found(tmp_path: Path, first_step: str, first_value: str,
                                                      verified: bool) -> None:  # fmt: skip
    async def scenario() -> None:
        twice = solver(first_step, first_value) * 2  # the one retry gets the same plan
        engine, _ = await make_engine(tmp_path, {"solver": twice, "coach": [tutor("What could you do first?")] * 3})
        try:
            await engine.start_problem(STATEMENT)
            if not verified:
                assert engine.state.plan is None  # the honest blocker: 24 holds at no checked answer
                return
            plan = engine.state.plan
            assert plan is not None and [s.latex for s in plan.steps] == ["7x=21", "x=3"]
            step = plan.steps[0]
            assert step.check_id is not None and 21 in engine.state.check_values[step.check_id]
        finally:
            await close(engine)

    asyncio.run(scenario())
