"""Checked figures on the live turn loop (VSL-12, VSL-45): the demo's acceleration question gets a velocity-time graph
whose every number traces to the question's givens, and the tutor can point at its slope; a pack question with a
figure shows it before any model speaks. The engine runs for real with scripted model outputs; the Physics pack's
own records supply the KCs, and the figure patterns are written here as the pack build resolves them."""

from __future__ import annotations

import asyncio
import json
import re
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from agent_core.assets.visuals import VisualContext, validate
from agent_core.engine import figures
from agent_core.engine.pointing import Targets, resolve
from agent_core.retrieval.index import KnowledgeIndex
from agent_core.store.pack_index import PackIndex
from engine_harness import close, make_engine, reply, tutor
from jana_tools import REPO_ROOT
from pack_builder.build import load_source

PACK = REPO_ROOT / "content" / "curriculum" / "phy" / "o"
DEMO = "A car speeds up from rest to 20 m/s in 5 s. What's its acceleration?"
ACCELERATION = "kc.phy.o.motion.acceleration_from_change"
VT_PATTERN = {
    "source": "wex.phy.o.motion.0002",
    "type": "motion_graph",
    "params": {"graph": "velocity_time", "points": [{"id": "A", "t": "0", "value": "10"},
                                                    {"id": "B", "t": "5.0", "value": "25"}],
               "gradient": [{"id": "slope", "from": "A", "to": "B"}], "units": {"t": "s", "value": "m/s"}},
    "parts": ["slope", "seg_A_B", "A", "B"],
}  # fmt: skip
LOOP = asyncio.new_event_loop()


def run(coro: Any) -> Any:
    return LOOP.run_until_complete(coro)


def knowledge() -> KnowledgeIndex:
    source = load_source(PACK)
    return KnowledgeIndex.from_tables([(dict(source.pack), {t: list(rows) for t, rows in source.tables.items()})])


def sources(**extra: Any) -> dict[str, Any]:
    return {"diagrams": {}, "presets": {}, "conventions": {}, "pack_values": {}, "figures": {}, **extra}


def test_pack_index_offers_a_worked_examples_figure_as_its_kcs_pattern() -> None:
    resolved, _ = validate({"spec_version": 1, "type": "motion_graph", "params": VT_PATTERN["params"],
                            "numbers_from": ["kn_zero", "kn_ten", "kn_twentyfive", "kn_five"]},
                           VisualContext("physics", "O", "S2", knowns={"kn_zero": Fraction(0), "kn_ten": Fraction(10),
                                                                       "kn_twentyfive": Fraction(25),
                                                                       "kn_five": Fraction(5)}))  # fmt: skip
    example = {"id": "wex.phy.o.motion.0002", "kc_ids": [ACCELERATION], "visual": {
        "visual_type": "motion_graph", "params": VT_PATTERN["params"], "resolved": resolved}}  # fmt: skip
    index = PackIndex()
    index._add_visuals({"pack_id": "pack.phy.o", "subject": "phy"}, {"worked_examples": [example]})
    pattern = index.visual_sources("phy")["figures"][ACCELERATION]
    assert pattern["type"] == "motion_graph" and pattern["params"]["graph"] == "velocity_time"
    assert "slope" in pattern["parts"]


def test_the_coachs_figure_note_masks_the_patterns_numbers() -> None:
    knowns = [{"known_id": "kn_01", "value": "0"}, {"known_id": "kn_02", "value": "20"},
              {"known_id": "kn_03", "value": "5"}]  # fmt: skip
    state = SimpleNamespace(problem=SimpleNamespace(statement=DEMO), hardware_class="mid", subject="physics",
                            level="O", board=SimpleNamespace(knowns=knowns))  # fmt: skip
    deps = SimpleNamespace(settings=SimpleNamespace(lean_classes=("low",)), stage="S2",
                           visual_sources=lambda code: sources(figures={ACCELERATION: VT_PATTERN}))  # fmt: skip
    engine = SimpleNamespace(state=state, deps=deps, diagnosis=SimpleNamespace(kc_ids=[ACCELERATION]))
    note = figures.opening_note(engine)
    assert "motion_graph" in note and '"graph":"velocity_time"' in note and '"id":"slope"' in note
    # Another problem's values never reach the Coach: only the shape, with this problem's givens by id.
    pattern = json.loads(note[note.index("{"): note.index(". List in its")])
    assert pattern["points"] == [{"id": "A", "t": "?", "value": "?"}, {"id": "B", "t": "?", "value": "?"}]
    assert not re.search(r"\d", json.dumps(pattern))
    assert "kn_01 = 0" in note and "kn_02 = 20" in note and "kn_03 = 5" in note and "kn_zero = 0" in note
    # No pattern for the KC, or lean hardware: no line.
    engine.diagnosis = SimpleNamespace(kc_ids=["kc.phy.o.motion.average_speed"])
    assert figures.opening_note(engine) == ""
    engine.diagnosis, state.hardware_class = SimpleNamespace(kc_ids=[ACCELERATION]), "low"
    assert figures.opening_note(engine) == ""


def _diagnosis(body: dict[str, Any]) -> dict[str, Any]:
    """The Diagnoser picks the acceleration KC by its number in the list it was given."""
    task = next(m["content"] for m in body["messages"] if m["role"] == "user")
    listed = re.search(r"Knowledge components:\n(.*?)(?:\n\n|$)", task, re.S)
    assert listed is not None, task
    ref = next(int(line.split(".", 1)[0]) for line in listed.group(1).splitlines()
               if "acceleration from a change in velocity" in line)  # fmt: skip
    return reply(json.dumps({
        "in_scope": True, "subject": "physics", "topic_ref": 1, "kc_refs": [ref], "question_kind": "calculation",
        "knowns": [{"symbol": "u", "value": "0", "unit": "m/s", "quote": "from rest"},
                   {"symbol": "v", "value": "20", "unit": "m/s", "quote": "20 m/s"},
                   {"symbol": "t", "value": "5", "unit": "s", "quote": "5 s"}],
        "unknowns": ["a"], "clarifying_question": None, "misconception_ref": None, "evidence": [], "inference": "",
        "prerequisite_gap_refs": [], "confidence": "high"}))  # fmt: skip


def _solver() -> list[Any]:
    def plan(body: dict[str, Any]) -> dict[str, Any]:
        check = next(json.loads(m["content"])["check_id"] for m in reversed(body["messages"]) if m["role"] == "tool")
        step = {"index": 1, "latex": "a = \\frac{20 - 0}{5}", "reason": "change in velocity over time",
                "check_id": check, "kc_ref": None, "value": "4", "unit": "m/s^2"}  # fmt: skip
        return reply(json.dumps({"status": "complete", "method_summary": "a = (v - u)/t", "steps": [step],
                                 "final_answer": {"latex": "a = 4\\,m/s^2", "value": "4", "unit": "m/s^2",
                                                  "check_id": check, "plausible": True},
                                 "blocked_step": None, "blocked_reason": None}))  # fmt: skip

    return [reply("", [("c0", "math_evaluate", {"expression": "(20 - 0)/5"})]), plan]


def _coach_draws(body: dict[str, Any]) -> dict[str, Any]:
    context = "\n".join(str(m["content"]) for m in body["messages"])
    assert "a checked figure fits this topic" in context and "kn_02 = 20" in context
    graph = {"spec_version": 1, "type": "motion_graph", "numbers_from": ["kn_01", "kn_02", "kn_03"],
             "params": {"graph": "velocity_time", "points": [{"id": "A", "t": "0", "value": "0"},
                                                             {"id": "B", "t": "5", "value": "20"}],
                        "gradient": [{"id": "slope", "from": "A", "to": "B"}], "units": {"t": "s", "value": "m/s"}}}
    return tutor("Here is the car's velocity-time graph. What does the slope of this line tell you?",
                 visual=[graph], expects="student_answer")  # fmt: skip


def test_demo_acceleration_question_draws_a_checked_vt_graph_and_points_at_its_slope(tmp_path: Path) -> None:
    script = {"diagnoser": [_diagnosis], "solver": _solver(), "coach": [_coach_draws]}

    async def scenario() -> tuple[Any, list[dict[str, Any]]]:
        engine, _ = await make_engine(tmp_path, script)
        engine.deps.stage = "S2"
        engine.bind_knowledge(knowledge())
        engine.deps.visual_sources = lambda code: sources(figures={ACCELERATION: VT_PATTERN})
        await engine.start_problem(DEMO)
        await close(engine)
        return engine, [f["event"] for f in engine.events.frames]

    engine, events = run(scenario())
    (drawn,) = [e for e in events if e["type"] == "visual.spec"]
    spec = drawn["spec"]
    assert spec["type"] == "motion_graph" and spec["status"] == "ok"
    assert set(spec["numbers_from"]) >= {"kn_01", "kn_02", "kn_03"}  # every number traces to a given
    assert engine.state.shown_visuals[-1]["visual_id"] == drawn["visual_id"]
    spoken = resolve(f'The slope <point at="{drawn["visual_id"]}:slope"/> is the acceleration.',
                     Targets.of(engine.state))  # fmt: skip
    assert [c.target for c in spoken.cues] == [f"{drawn['visual_id']}:slope"] and spoken.misses == ()


def test_a_coach_figure_with_an_untraced_number_is_refused(tmp_path: Path) -> None:
    """A number no given or check states (here 30 m/s) never reaches the screen: the reply goes on in words."""

    def invents(body: dict[str, Any]) -> dict[str, Any]:
        graph = {"spec_version": 1, "type": "motion_graph", "numbers_from": ["kn_01", "kn_03"],
                 "params": {"graph": "velocity_time", "points": [{"id": "A", "t": "0", "value": "0"},
                                                                 {"id": "B", "t": "5", "value": "30"}]}}  # fmt: skip
        return tutor("Here is the graph. What does its slope tell you?", visual=[graph])

    script = {"diagnoser": [_diagnosis], "solver": _solver(), "coach": [invents, invents]}

    async def scenario() -> list[dict[str, Any]]:
        engine, _ = await make_engine(tmp_path, script)
        engine.deps.stage = "S2"
        engine.bind_knowledge(knowledge())
        engine.deps.visual_sources = lambda code: sources(figures={ACCELERATION: VT_PATTERN})
        await engine.start_problem(DEMO)
        await close(engine)
        return [f["event"] for f in engine.events.frames]

    events = run(scenario())
    assert not [e for e in events if e["type"] == "visual.spec"]


def test_a_pack_question_shows_its_own_figure_before_the_coach_speaks(tmp_path: Path) -> None:
    item = next(i for i in load_source(PACK).tables["items"] if i["id"] == "itm.phy.o.motion.0077")
    knowns = {"kn_zero": Fraction(0), "kn_ten": Fraction(10), "kn_fifteen": Fraction(15)}
    request = {"spec_version": 1, "type": "motion_graph", "params": item["visual"]["params"],
               "numbers_from": list(knowns)}  # fmt: skip
    resolved, _ = validate(request, VisualContext("physics", "O", "S2", knowns=knowns))
    item = {**item, "visual": {**item["visual"], "resolved": resolved}}
    notes: list[str] = []

    def coach(body: dict[str, Any]) -> dict[str, Any]:
        notes.append("\n".join(str(m["content"]) for m in body["messages"]))
        return tutor("Look at the graph. What does its slope tell you?")

    async def scenario() -> list[dict[str, Any]]:
        diagnosis = {"in_scope": True, "subject": "physics", "topic_ref": None, "kc_refs": [],
                     "question_kind": "calculation", "knowns": [], "unknowns": [], "clarifying_question": None,
                     "misconception_ref": None, "evidence": [], "inference": "", "prerequisite_gap_refs": [],
                     "confidence": "medium"}  # fmt: skip
        engine, _ = await make_engine(tmp_path, {"diagnoser": [reply(json.dumps(diagnosis))], "coach": [coach]})
        engine.deps.stage = "S2"
        await engine.start_practice(item)
        await close(engine)
        return [f["event"] for f in engine.events.frames]

    events = run(scenario())
    kinds = [e["type"] for e in events]
    (drawn,) = [e for e in events if e["type"] == "visual.spec"]
    assert drawn["visual_id"] == resolved["visual_id"]
    first_text = next(i for i, k in enumerate(kinds) if k in ("text.delta", "text"))
    assert kinds.index("visual.spec") < first_text  # on screen before any model speaks
    assert f"the question's figure is on screen ({resolved['visual_id']}" in notes[0] and "slope" in notes[0]
