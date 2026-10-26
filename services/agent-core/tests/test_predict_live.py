"""Predict before you see in a tutoring session (VSL-47): the learner's locked-in prediction for a predict-first
simulation reaches the tutor, which highlights the result and is told to point at it and ask for an explanation; the
engine, not the client, decides whether the prediction matched, and the usual guess is evidence of the scenario's pack
misconception. The engine runs for real with scripted model outputs; the circuit scenario is the renderer package's."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
from agent_core.engine.pointing import Targets, resolve
from agent_core.engine.predictions import PredictionRefused
from engine_harness import checker_steps, close, make_engine, reply, solver_steps, tutor
from test_root_gap import knowledge

CIRCUIT = "poe.phy.circuit_series_to_parallel.v1"
MISCONCEPTION = "mc.phy.o.parallel_adding_branch_raises_resistance"
SIM = {"spec_version": 1, "type": "circuit_sim",
       "params": {"emf": 6, "resistors": [{"id": "R1", "resistance": 10}, {"id": "R2", "resistance": 10}],
                  "arrangement": "series", "predict": CIRCUIT}}  # fmt: skip
STATEMENT = "Two 10 ohm resistors are in series with a 6 V cell. What happens to the current if they go in parallel?"
LOOP = asyncio.new_event_loop()


def run(coro: Any) -> Any:
    return LOOP.run_until_complete(coro)


def _diagnosis() -> dict[str, Any]:
    return reply(json.dumps({"in_scope": True, "subject": "physics", "topic_ref": None, "kc_refs": [],
                             "question_kind": "explanation", "knowns": [], "unknowns": [], "clarifying_question": None,
                             "misconception_ref": None, "evidence": [], "inference": "", "prerequisite_gap_refs": [],
                             "confidence": "medium"}))  # fmt: skip


class Coach:
    """Draws the predict-first simulation on its first turn; records every later turn's context."""

    def __init__(self) -> None:
        self.contexts: list[str] = []

    def __call__(self, body: dict[str, Any]) -> dict[str, Any]:
        self.contexts.append("\n".join(str(m["content"]) for m in body["messages"]))
        if len(self.contexts) == 1:
            return tutor("Predict first: write what you think happens to the current, then run it.", visual=[SIM])
        return tutor("The current from the cell went up. Why do you think it did?")


async def _session(tmp_path: Path, coach: Coach) -> tuple[Any, str]:
    script = {"diagnoser": [_diagnosis()], "solver": solver_steps(), "checker": checker_steps(), "coach": [coach] * 4}
    engine, _ = await make_engine(tmp_path, script)
    engine.deps.stage = "S2"
    engine.bind_knowledge(knowledge())
    learned: list[Any] = []
    engine.learning = learned.extend
    engine.learned = learned
    await engine.start_problem(STATEMENT)
    (shown,) = [v for v in engine.state.shown_visuals if v.get("predict") == CIRCUIT]
    return engine, shown["visual_id"]


def body(event: str, choice: str | None, text: str) -> dict[str, Any]:
    return {"client_event_id": "cli_1", "event": event, "scenario_id": CIRCUIT, "choice": choice, "text": text}


def test_the_usual_guess_is_highlighted_pointed_at_and_counted(tmp_path: Path) -> None:
    coach = Coach()

    async def scenario() -> tuple[Any, str, list[dict[str, Any]], Any]:
        engine, visual_id = await _session(tmp_path, coach)
        before = len(engine.events.frames)
        await engine.sim_prediction(visual_id, body("committed", "falls", "It will go down, more resistors."))
        events = [f["event"] for f in engine.events.frames[before:]]
        # The tutor's cue at the result resolves to the readout on screen (VSL-45).
        spoken = resolve(f'The current <point at="{visual_id}:out.current"/> went up.', Targets.of(engine.state))
        await close(engine)
        return engine, visual_id, events, spoken

    engine, visual_id, events, spoken = run(scenario())
    (focus,) = [e for e in events if e["type"] == "visual.focus"]
    assert focus["visual_id"] == visual_id and focus["part_ids"] == ["out.current"]
    note = coach.contexts[-1]
    assert "it was the usual guess" in note and f"{visual_id}:out.current" in note and "ask the student" in note
    assert "It will go down, more resistors." in note  # the learner's words, as their escaped message
    evidence = [e for e in engine.learned if e.type == "misconception_evidence"]
    assert [e.payload["misconception_id"] for e in evidence] == [MISCONCEPTION]
    assert [c.target for c in spoken.cues] == [f"{visual_id}:out.current"] and spoken.misses == ()


def test_a_right_prediction_and_its_explanation(tmp_path: Path) -> None:
    coach = Coach()

    async def scenario() -> Any:
        engine, visual_id = await _session(tmp_path, coach)
        await engine.sim_prediction(visual_id, body("committed", "rises", ""))
        await engine.sim_prediction(visual_id, body("explained", None, "Two paths let more charge through."))
        await close(engine)
        return engine

    engine = run(scenario())
    assert "it matched the result" in coach.contexts[-2]
    assert not [e for e in engine.learned if e.type == "misconception_evidence"]
    explained = coach.contexts[-1]
    assert "explained the simulation's result" in explained and "never give the explanation" in explained
    assert "An extra parallel path lets more current flow" in explained  # the pack's fix names the idea


def test_a_prediction_is_refused_for_a_visual_not_predicting(tmp_path: Path) -> None:
    coach = Coach()

    async def scenario() -> None:
        engine, visual_id = await _session(tmp_path, coach)
        with pytest.raises(PredictionRefused, match="not_predicted"):
            await engine.sim_prediction(visual_id, body("explained", None, "Because."))
        with pytest.raises(PredictionRefused, match="not_found"):
            await engine.sim_prediction("vis_01JZ0000000000000000000000", body("committed", "rises", ""))
        other = {**body("committed", "rises", ""), "scenario_id": "poe.phy.gas_heated_flask.v1"}
        with pytest.raises(PredictionRefused, match="not_predicting"):
            await engine.sim_prediction(visual_id, other)
        await close(engine)

    run(scenario())


def test_a_lesson_steps_predict_first_sim_is_shown_and_asked_for_first(tmp_path: Path) -> None:
    """A lesson step whose figure is a predict-first simulation shows it in the session before the Coach speaks, and
    the Coach is told to ask for the prediction first and never to say what it will show."""
    from types import SimpleNamespace

    from agent_core.assets.resolvers import resolver
    from agent_core.assets.visuals import Resolver, VisualContext, validate
    from agent_core.engine import lessons, turn_scope
    from jana_tools.visual_fixtures import _call
    from test_root_gap import tables

    resolved, _ = validate(SIM, VisualContext("physics", "O", "S2"), Resolver(resolver(_call("lesson"))))
    item = next(i for i in tables("phy")["items"] if i["id"] == "itm.phy.o.circuits.0022")
    block = {"type": "step", "action": "predict", "text": "Predict first.", "items": [{"item_id": item["id"]}],
             "visual": {"visual_type": "circuit_sim", "params": SIM["params"], "resolved": resolved}}  # fmt: skip
    contexts: list[str] = []

    def coach(body: dict[str, Any]) -> dict[str, Any]:
        contexts.append("\n".join(str(m["content"]) for m in body["messages"]))
        return tutor("Write your prediction in the simulation first.")

    async def scenario() -> list[dict[str, Any]]:
        engine, _ = await make_engine(tmp_path, {"coach": [coach]})
        engine.deps.stage = "S2"
        engine.lesson_desk = SimpleNamespace(item=lambda item_id: dict(item))
        flow = SimpleNamespace(index=1, view={"blocks": [{}, block]},
                               lesson_id="les.phy.o.circuits.series_and_parallel_circuits")  # fmt: skip
        turn = engine._begin("ask")
        with turn_scope(turn.turn_id):
            await lessons._present(engine, turn, flow, block)
        await close(engine)
        return [f["event"] for f in engine.events.frames]

    events = run(scenario())
    (drawn,) = [e for e in events if e["type"] == "visual.spec"]
    assert drawn["visual_id"] == resolved["visual_id"] and drawn["spec"]["params"]["predict"] == CIRCUIT
    assert "a predict-first simulation is on screen" in contexts[0]
    assert "never say or hint at what it will show" in contexts[0]


def test_projectile_range_the_usual_guess_points_at_the_range(tmp_path: Path) -> None:
    """The demo case: 30° then 60° at 20 m/s. "Further" is the usual guess; the tutor is told to point at the range,
    which the run shows is the same, and the steeper-launch misconception gets its evidence."""
    projectile = "poe.phy.projectile_angle_30_60.v1"
    sim = {"spec_version": 1, "type": "projectile_sim", "params": {"mode": "angled", "speed": 20, "angle": 30,
                                                                    "height": 0, "predict": projectile}}  # fmt: skip
    contexts: list[str] = []

    def coach(body_: dict[str, Any]) -> dict[str, Any]:
        contexts.append("\n".join(str(m["content"]) for m in body_["messages"]))
        if len(contexts) == 1:
            return tutor("Predict first: which ball lands further?", visual=[sim])
        return tutor("They landed the same distance away. Why do you think that is?")

    script = {"diagnoser": [_diagnosis()], "solver": solver_steps(), "checker": checker_steps(), "coach": [coach] * 3}

    async def scenario() -> tuple[Any, str, list[dict[str, Any]]]:
        engine, _ = await make_engine(tmp_path, script)
        engine.deps.stage = "S2"
        engine.bind_knowledge(knowledge())
        engine.deps.visual_sources = lambda code: {"diagrams": {}, "presets": {}, "pack_values": {}, "figures": {},
                                                   "conventions": {"phy.g": "9.8"}}  # fmt: skip
        learned: list[Any] = []
        engine.learning = learned.extend
        await engine.start_problem("Two balls are launched at 20 m/s, at 30 and at 60 degrees. Which lands further?")
        (shown,) = [v for v in engine.state.shown_visuals if v.get("predict") == projectile]
        before = len(engine.events.frames)
        prediction = {**body("committed", "further", "The 60 degree one."), "scenario_id": projectile}
        await engine.sim_prediction(shown["visual_id"], prediction)
        events = [f["event"] for f in engine.events.frames[before:]]
        await close(engine)
        return learned, shown["visual_id"], events

    learned, visual_id, events = run(scenario())
    (focus,) = [e for e in events if e["type"] == "visual.focus"]
    assert focus["part_ids"] == ["out.range"]
    assert f"{visual_id}:out.range" in contexts[-1] and "it was the usual guess" in contexts[-1]
    evidence = [e.payload["misconception_id"] for e in learned if e.type == "misconception_evidence"]
    assert evidence == ["mc.phy.o.steeper_launch_goes_further"]
