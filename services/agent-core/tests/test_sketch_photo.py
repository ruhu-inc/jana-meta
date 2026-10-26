"""Snap your sketch (JM-D10): the student's own photographed free-body diagram or velocity-time graph, compared with
the problem's checked visual, with the wrong part lit on their drawing and never the answer given.

The drawings are what the reader returns (elements with their ends on the image, y down); the truths are the shipped
renderer fixtures for `free_body` and `motion_graph`, whose values the tools checked when they were resolved."""

from __future__ import annotations

import asyncio
import json
import math
from pathlib import Path
from typing import Any

import pytest
from agent_core.engine.sketch_photo import (
    NO_TRUTH,
    UNREAD_ONE,
    SketchCheck,
    check,
    coach_note,
    sketch_turn,
    truth_visual,
)
from agent_core.engine.turn import TurnIds
from engine_harness import close, make_engine, tutor

ROOT = Path(__file__).resolve().parents[3]
FREE_BODY = json.loads((ROOT / "packages/renderers/fixtures/visuals/free-body.json").read_text())["spec"]
MOTION = json.loads((ROOT / "packages/renderers/fixtures/visuals/motion-graph.json").read_text())["spec"]
CAP = "cap_01J8Z5W6X7Y8Z9A0B1C2D3E4F5"


def element(n: int, kind: str, label: str | None, start: tuple[float, float], end: tuple[float, float],
            confidence: float = 0.9) -> dict[str, Any]:  # fmt: skip
    return {"region_id": f"rgn_{n}", "kind": "diagram", "order": n, "text": label or "", "confidence": confidence,
            "needs_confirmation": False, "low_confidence_spans": [], "language": "en", "direction": "ltr",
            "sketch_element": {"kind": kind, "label": label, "from": {"x": start[0], "y": start[1]},
                               "to": {"x": end[0], "y": end[1]}}}  # fmt: skip


def arrow(n: int, label: str | None, degrees: float, tilt: float = 0.0, confidence: float = 0.9) -> dict[str, Any]:
    """An arrow from the block's centre, `degrees` anticlockwise from +x (y up), on a photo tilted by `tilt`."""
    a = math.radians(degrees + tilt)
    return element(n, "arrow", label, (0.5, 0.5), (0.5 + 0.2 * math.cos(a), 0.5 - 0.2 * math.sin(a)), confidence)


def slope(n: int, degrees: float, tilt: float = 0.0) -> dict[str, Any]:
    a = math.radians(degrees + tilt)
    return element(n, "line_segment", None, (0.5 - 0.4 * math.cos(a), 0.5 + 0.4 * math.sin(a)),
                   (0.5 + 0.4 * math.cos(a), 0.5 - 0.4 * math.sin(a)))  # fmt: skip


def outcomes(result: SketchCheck) -> dict[str | None, str]:
    return {f.region_id: f.outcome for f in result.findings}


def checked(spec: dict[str, Any] | None, regions: list[dict[str, Any]]) -> SketchCheck:
    return asyncio.run(check(spec, regions))


# --- free-body diagrams: block on a 30 degree slope, weight 270, normal reaction 120, friction 30 ----------------


def test_a_correct_free_body_diagram_passes_every_arrow() -> None:
    drawing = [slope(0, 30), arrow(1, "W", 270), arrow(2, "R", 122), arrow(3, "friction", 25)]
    result = checked(FREE_BODY, drawing)
    assert outcomes(result) == {"rgn_1": "ok", "rgn_2": "ok", "rgn_3": "ok"} and result.problems == []


def test_a_friction_arrow_down_the_slope_is_found_on_the_drawing() -> None:
    drawing = [slope(0, 30), arrow(1, "mg", 268), arrow(2, "N", 118), arrow(3, "F", 210)]
    result = checked(FREE_BODY, drawing)
    (problem,) = result.problems
    assert (problem.region_id, problem.outcome, problem.about, problem.name) == ("rgn_3", "opposite", "F", "friction")


def test_an_arrow_off_by_a_right_angle_is_the_wrong_direction() -> None:
    result = checked(FREE_BODY, [arrow(1, "W", 270), arrow(2, "R", 30), arrow(3, "F", 30)])
    assert outcomes(result)["rgn_2"] == "wrong_direction"


def test_a_tilted_photo_or_a_mirrored_slope_is_not_a_mistake() -> None:
    tilted = [slope(0, 30, tilt=12), arrow(1, "W", 270, tilt=12), arrow(2, "R", 120, tilt=12),
              arrow(3, "F", 30, tilt=12)]  # fmt: skip
    assert checked(FREE_BODY, tilted).problems == []
    mirrored = [slope(0, -30), arrow(1, "W", 270), arrow(2, "R", 60), arrow(3, "F", 150)]
    assert checked(FREE_BODY, mirrored).problems == []
    # Mirrored, friction still drawn down that slope: still wrong.
    wrong = [slope(0, -30), arrow(1, "W", 270), arrow(2, "R", 60), arrow(3, "F", 330)]
    assert [p.region_id for p in checked(FREE_BODY, wrong).problems] == ["rgn_3"]


def test_unreadable_arrows_are_labelled_not_judged_and_nothing_is_called_missing() -> None:
    drawing = [arrow(1, "W", 270), arrow(2, "[?]", 200), arrow(3, "F", 30, confidence=0.3)]
    result = checked(FREE_BODY, drawing)
    assert outcomes(result) == {"rgn_1": "ok", "rgn_2": "unread", "rgn_3": "unread"}
    assert result.problems == []  # the normal reaction may be one of the unread arrows: never guessed missing


def test_a_missing_force_and_an_invented_one_are_both_found() -> None:
    result = checked(FREE_BODY, [arrow(1, "W", 270), arrow(2, "R", 120), arrow(3, "P", 0)])
    assert outcomes(result) == {"rgn_1": "ok", "rgn_2": "ok", "rgn_3": "extra", None: "missing"}
    missing = next(f for f in result.findings if f.outcome == "missing")
    assert missing.about == "F" and missing.name == "friction"


# --- velocity-time graphs: up to 12 m/s in 4 s, steady to 10 s, down to rest at 14 s ---------------------------


def axis(n: int, label: str, vertical: bool) -> dict[str, Any]:
    return element(n, "axis", label, (0.1, 0.9), (0.1, 0.1) if vertical else (0.9, 0.9))


def segment(n: int, start: tuple[float, float], end: tuple[float, float]) -> dict[str, Any]:
    return element(n, "line_segment", None, start, end)


def test_a_velocity_time_graph_is_checked_part_by_part() -> None:
    right = [axis(0, "v", True), axis(1, "t", False), segment(2, (0.1, 0.9), (0.3, 0.4)),
             segment(3, (0.3, 0.4), (0.6, 0.41)), segment(4, (0.6, 0.41), (0.8, 0.9))]  # fmt: skip
    assert checked(MOTION, right).problems == []
    climbing = [*right[:3], segment(3, (0.3, 0.4), (0.6, 0.2)), right[4]]
    (problem,) = checked(MOTION, climbing).problems
    assert (problem.region_id, problem.outcome, problem.about) == ("rgn_3", "wrong_shape", "seg_B_C")


def test_a_segment_drawn_right_to_left_reads_the_same_and_an_axis_label_is_checked() -> None:
    drawing = [axis(0, "s", True), axis(1, "time", False), segment(2, (0.3, 0.4), (0.1, 0.9)),
               segment(3, (0.6, 0.4), (0.3, 0.4)), segment(4, (0.6, 0.4), (0.8, 0.9))]  # fmt: skip
    result = checked(MOTION, drawing)
    assert [(p.region_id, p.outcome) for p in result.problems] == [("rgn_0", "axis_label")]


def test_too_few_parts_are_missing_and_too_many_are_extra() -> None:
    short = [segment(2, (0.1, 0.9), (0.3, 0.4)), segment(3, (0.3, 0.4), (0.6, 0.4))]
    assert [f.outcome for f in checked(MOTION, short).problems] == ["missing"]
    long = [*short, segment(4, (0.6, 0.4), (0.8, 0.9)), segment(5, (0.8, 0.9), (0.9, 0.9))]
    assert [(f.region_id, f.outcome) for f in checked(MOTION, long).problems] == [("rgn_5", "extra_segment")]


# --- what is said -----------------------------------------------------------------------------------------------


def test_nothing_to_compare_with_is_said_plainly() -> None:
    assert checked(None, [arrow(1, "W", 270)]).reason == "no_truth"
    assert checked(FREE_BODY, [{"region_id": "rgn_0", "text": "a box"}]).reason == "nothing_read"


def test_the_coach_is_told_where_to_point_and_never_the_answer() -> None:
    result = checked(FREE_BODY, [arrow(1, "W", 270), arrow(2, "R", 120), arrow(3, "F", 210)])
    note = coach_note(result, CAP)
    assert f'<point at="{CAP}:rgn_3"/>' in note and "friction" in note
    assert "say_spoken only" in note and "never in say" in note  # markers are for the ear, never the screen
    assert "never say which way it should point" in note
    for leak in ("30", "up the slope", "along the slope", "degrees"):
        assert leak not in note


def test_the_truth_is_the_checked_visual_shown_for_this_problem() -> None:
    from types import SimpleNamespace

    shown = [{"visual_id": FREE_BODY["visual_id"], "parts": [], "kind": "free_body"}]
    persisted = {"prt_1": {"kind": "visual", "content": MOTION}, "prt_2": {"kind": "visual", "content": FREE_BODY}}
    engine = SimpleNamespace(state=SimpleNamespace(shown_visuals=shown), persisted=persisted)
    assert truth_visual(engine) is FREE_BODY
    engine.state.shown_visuals = []
    assert truth_visual(engine) is None  # a visual of an earlier problem is not this one's truth


# --- the turn ---------------------------------------------------------------------------------------------------


def sketch_capture(regions: list[dict[str, Any]]) -> dict[str, Any]:
    return {"capture_id": CAP, "purpose": "sketch", "text": "W R F", "regions": regions}


@pytest.mark.parametrize("shown", [True, False])
def test_the_sketch_turn_lights_the_wrong_arrow_and_asks_about_it(tmp_path: Path, shown: bool) -> None:
    async def run() -> tuple[list[dict[str, Any]], str, list[str]]:
        engine, provider = await make_engine(tmp_path, {"coach": [tutor("Look at the arrow you drew for friction.")]})
        try:
            if shown:
                engine.state.shown_visuals = [{"visual_id": FREE_BODY["visual_id"], "parts": [], "kind": "free_body"}]
                engine.persisted["prt_fb"] = {"kind": "visual", "content": FREE_BODY, "turn_id": "trn_x"}
            drawing = [arrow(1, "W", 270), arrow(2, "R", 120), arrow(3, "F", 210), arrow(4, "[?]", 0)]
            await sketch_turn(engine, sketch_capture(drawing), TurnIds())
            coached = [r for r in provider.requests if r.get("_role") == "coach"]
            return ([f["event"] for f in engine.events.frames], json.dumps(coached[-1]["messages"]) if coached else "",
                    list(engine.state.photo_marks))  # fmt: skip
        finally:
            await close(engine)

    events, context, marks = asyncio.run(run())
    texts = [e.get("delta", "") for e in events if e["type"] == "text.delta"]
    if not shown:
        assert any(NO_TRUTH in t for t in texts) and context == ""  # no model call, nothing guessed
        return
    (highlight,) = [e for e in events if e["type"] == "board.highlight"]
    assert highlight["photo_regions"] == [f"{CAP}:rgn_3"] and highlight["step_ids"] == []
    assert any(UNREAD_ONE in t for t in texts)  # the unread arrow is labelled in the engine's own words
    assert f"{CAP}:rgn_3" in context and "friction" in context
    assert f"{CAP}:rgn_3" in marks  # and the Coach's spoken cue may point at it


def test_an_unlabelled_arrow_is_unread_not_an_invented_force() -> None:
    result = checked(FREE_BODY, [arrow(1, "W", 270), arrow(2, None, 120)])
    assert outcomes(result)["rgn_2"] == "unread" and not any(f.outcome == "extra" for f in result.findings)


def test_what_the_student_confirms_is_a_plain_description_of_each_part() -> None:
    from agent_core.engine.vision import sketch_part

    assert sketch_part({"kind": "arrow", "label": "F"}) == "arrow labelled F"
    assert sketch_part({"kind": "line_segment", "label": None}) == "line segment"
