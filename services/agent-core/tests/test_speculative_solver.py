"""The Solver started beside the Diagnoser on a new question (SPEC §12): online, both calls spend seconds reasoning
before their first token, and the Solver needs the diagnosis mostly to choose its teaching skill. The guess is the
pack index's best-matching KC (no model call); its plan is used only when the diagnosis gives the same teaching
skill, else it is dropped and the Solver runs with the diagnosis as before. Never on local models (one call at a
time), never when the diagnosis ends the turn without a plan. Scripted models, synthetic questions."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from agent_core.engine import team
from engine_harness import STATEMENT, close, solver_steps, tutor
from test_d94_session_subject import diagnosis, guard, make_engine, roles, run

SAFE = "Which quantities does the question give you, and which one does it ask for?"


class Log:
    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []

    def log(self, level: str, component: str, event: str, **fields: Any) -> None:
        self.records.append({"event": event, **fields})

    def outcomes(self) -> list[str]:
        return [r["outcome"] for r in self.records if r["event"] == "plan.speculative"]


def online(engine: Any) -> None:
    """The Diagnoser and the Solver served by a cloud candidate first (the calls still go to the scripted model)."""

    async def first(role: str) -> bool:
        return True

    engine._online_first = first


def solver_script() -> list[Any]:
    """Order-proof Solver steps: each answers its own request (a tool call first, the plan once a check came back),
    so a guess cancelled part-way never shifts the steps a later run gets."""
    call, plan = solver_steps()

    def step(body: dict[str, Any]) -> dict[str, Any]:
        return plan(body) if any(m["role"] == "tool" for m in body["messages"]) else call

    return [step] * 6


def kc_refs(engine: Any, same: bool) -> list[int]:
    """A diagnosis KC (1-based among the Diagnoser's candidates) whose teaching skill is (or is not) the guess's."""
    _, kcs, _ = team.candidates(engine, STATEMENT)
    skills, level = engine.deps.assets.skills, engine.state.level
    guessed = skills.teaching_for(kcs[:1], level)
    for n, kc in enumerate(kcs, 1):
        skill = skills.teaching_for([kc], level)
        if (skill is not None and guessed is not None and skill.name == guessed.name) == same and skill is not None:
            return [n]
    raise AssertionError("no candidate KC with the wanted skill")


def start(tmp_path: Path, *, same: bool | None, served_online: bool = True,
          clarify: bool = False) -> tuple[Any, Any, Log]:  # fmt: skip
    probe, _, _ = run(make_engine(tmp_path / "probe", {}, "physics"))
    refs = kc_refs(probe, same) if same is not None else []
    run(close(probe))
    fields: dict[str, Any] = {"kc_refs": refs, "topic_ref": 1}
    if clarify:
        fields["clarifying_question"] = "Which way is up?"
    slow = {**diagnosis("physics", **fields), "stall_s": 0.2}  # the guess's run finishes first
    script = {"input_guard": [guard()], "diagnoser": [slow], "solver": solver_script(),
              "coach": [tutor(SAFE)] * 2}  # fmt: skip
    engine, provider, _ = run(make_engine(tmp_path, script, "physics"))
    log = Log()
    engine.logger = log
    if served_online:
        online(engine)
    try:
        run(engine.start_problem(STATEMENT))
    finally:
        run(close(engine))
    return engine, provider, log


def solver_tasks(provider: Any) -> list[str]:
    return [json.dumps(r["messages"]) for r in provider.requests if r.get("_role") == "solver"]


def test_the_guessed_plan_is_used_when_the_diagnosis_gives_the_same_skill(tmp_path: Path) -> None:
    engine, provider, log = start(tmp_path, same=True)
    assert log.outcomes() == ["used"]
    order = roles(provider)
    assert order.count("solver") == 2, "one Solver run (its tool call and its plan), not two"
    assert engine.state.plan is not None and "coach" in order
    assert all("Given quantities" not in task for task in solver_tasks(provider)), "the guess sends the question only"


def test_a_different_skill_drops_the_guess_and_the_solver_runs_with_the_diagnosis(tmp_path: Path) -> None:
    engine, provider, log = start(tmp_path, same=False)
    assert log.outcomes() == ["other_skill"]
    assert engine.state.plan is not None
    assert any("Given quantities" in task for task in solver_tasks(provider)), "the planned run has the givens"


def test_a_turn_the_diagnosis_ends_without_a_plan_drops_the_guess(tmp_path: Path) -> None:
    engine, _, log = start(tmp_path, same=True, clarify=True)
    assert log.outcomes() == ["not_planned"]
    assert engine.state.plan is None and engine.speculation is None


def test_no_guess_on_local_models_or_when_switched_off(tmp_path: Path) -> None:
    _, provider, log = start(tmp_path / "local", same=True, served_online=False)
    assert log.outcomes() == [] and roles(provider).count("solver") == 2
    order = roles(provider)
    assert order.index("solver") > order.index("diagnoser"), "locally the Solver waits for the diagnosis"


def test_a_dropped_guess_never_leaves_an_unretrieved_error() -> None:
    loop = asyncio.new_event_loop()
    try:

        async def failing() -> dict[str, Any]:
            raise RuntimeError("upstream")

        async def go() -> None:
            call = asyncio.ensure_future(failing())
            await asyncio.sleep(0)
            call.add_done_callback(lambda done: done.cancelled() or done.exception())
            await asyncio.sleep(0)

        errors: list[Any] = []
        loop.set_exception_handler(lambda _, context: errors.append(context))
        loop.run_until_complete(go())
        assert errors == []
    finally:
        loop.close()
