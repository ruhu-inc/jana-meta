"""Learn a diagram from a photo (JM-D10, SPEC §5.2): the diagram drill's reading.

The student photographs a labelled diagram (the parts of the heart, a circuit). Muse Spark names each labelled part
and boxes both the part and its printed label; SAM 3.1 outlines the part; the student confirms the names. The drill
then hides the labels and asks "tap the part…", and code marks each tap against the part's outline
(`client-core/src/diagram-drill.ts`). Here: the reader's schema and instruction, the cloud read through SAM, and the
capture record a diagram leaves. Every photo and reading is synthetic."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
from agent_core.api.captures import ocr_label_boxes
from agent_core.api.errors import ApiError
from agent_core.contracts import errors as contract_errors
from agent_core.engine.events import new_id
from agent_core.engine.vision import DIAGRAM_READ_INSTRUCTION, PhotoReading, reader_output
from engine_harness import close
from test_m21_capture_drafts import QUAD, setup
from test_photo_regions import found_in_each_box, reader, run, screened, working_photo


def part(order: int, name: str, box: tuple[int, int, int, int], label: tuple[int, int, int, int] | None,
         confidence: float = 0.95) -> dict[str, Any]:  # fmt: skip
    """A part as Spark reads it: 0..1000 boxes for the part itself and for its printed label."""
    x, y, w, h = box
    return {"region_id": f"rgn_{order}", "kind": "diagram", "order": order, "text": name, "confidence": confidence,
            "needs_confirmation": False, "low_confidence_spans": [], "language": "en", "direction": "ltr",
            "bbox": {"x": x, "y": y, "w": w, "h": h}, "number_label": None, "diagram_description": None,
            "table": None,
            "label_box": None if label is None else dict(zip("xywh", label, strict=True))}  # fmt: skip


HEART = {"regions": [part(0, "left ventricle", (500, 500, 200, 250), (820, 700, 150, 40)),
                     part(1, "right atrium", (250, 250, 180, 180), (20, 260, 140, 40)),
                     part(2, "[?]", (400, 100, 100, 80), (600, 60, 120, 40), confidence=0.3)],
         "refusal": None}  # fmt: skip


def test_the_diagram_reader_asks_for_each_part_and_its_label_and_no_other_reader_does() -> None:
    _, schema, validator = reader_output("diagram")
    region = schema["$defs"]["region"]
    assert "label_box" in region["required"] and "outline" not in region["properties"]
    assert "sketch_element" not in region["properties"]
    assert not list(validator.iter_errors(HEART)), "Spark's 0..1000 grid, 1001 included, fits the schema"
    for purpose in ("question", "working", "sketch"):
        assert "label_box" not in reader_output(purpose)[1]["$defs"]["region"]["properties"]
    # The instruction keeps the drill honest: the part, not its words; nothing named that is not labelled.
    assert "never the label's words" in DIAGRAM_READ_INSTRUCTION
    assert "never name a part that is not labelled" in DIAGRAM_READ_INSTRUCTION


def test_a_diagram_is_read_in_the_cloud_and_each_part_outlined_by_sam(tmp_path: Path) -> None:
    engine, cloud = reader(tmp_path, HEART)  # one scripted reply: an uncertain label gets no crop re-read
    cloud.answer = found_in_each_box
    try:
        reading: PhotoReading = run(engine.read_photo(working_photo(), send_to_cloud=True, screen=screened,
                                                      structured=True, purpose="diagram"))  # fmt: skip
        assert reading.status == "read" and reading.outlined == 3 and reading.reread == 0
        (sent,) = cloud.segments
        assert sent["objects"][0]["box"] == [392, 294, 568, 456], "the part's box, not its label's"
        ventricle = reading.regions[0]
        assert ventricle["label_box"] == pytest.approx({"x": 0.82, "y": 0.7, "w": 0.15, "h": 0.04})
        assert ventricle["outline"] and ventricle["bbox"]["x"] < 0.82, "the outline is around the part"
        (vision,) = [r for r in cloud.requests if r.get("_role") == "vision"]
        assert "labelled diagram the student wants to learn" in json.dumps(vision["messages"])
    finally:
        run(close(engine))


def read_diagram(tmp_path: Path, regions: list[dict[str, Any]]) -> tuple[Any, Any, dict[str, Any]]:
    """A diagram capture through the capture desk, with the cloud reading given (boxes already 0..1)."""
    core, engine, desk, sid = setup(tmp_path)

    async def cloud_read(*_: Any, **kwargs: Any) -> PhotoReading:
        assert kwargs["purpose"] == "diagram"
        return PhotoReading("read", regions=regions, reader={"path": "cloud_vision", "model_id": "muse-spark-1.3",
                            "model_version": None, "hardware_class": "mid", "duration_ms": 900},
                            egress={"left_device": True, "destination": "cloud_tier"})  # fmt: skip

    engine.read_photo = cloud_read  # type: ignore[method-assign]

    async def go() -> dict[str, Any]:
        cap = desk.create({"client_capture_id": new_id("cli"), "session_id": sid, "source": "photo_file",
                           "purpose": "diagram"}, b"synthetic-original-never-stored")["capture_id"]  # fmt: skip
        await desk.crop(cap, {"corners": QUAD, "rotation": 0})
        desk.read(cap, {"send_to_cloud": True})
        await desk.tasks[cap]
        return desk.get(cap)

    return core, desk, asyncio.run(go())


def unit(region: dict[str, Any]) -> dict[str, Any]:
    out = {**region, "bbox": {k: v / 1000 for k, v in region["bbox"].items()}}
    if region["label_box"] is not None:
        out["label_box"] = {k: v / 1000 for k, v in region["label_box"].items()}
    return out


def test_a_diagram_capture_keeps_each_part_its_label_box_and_is_never_a_question(tmp_path: Path) -> None:
    parts = [unit(r) for r in HEART["regions"]]
    parts[1]["label_box"] = {"x": 0.9, "y": 0.1, "w": 0.2, "h": 0.04}  # runs off the image: dropped, part kept
    _, desk, record = read_diagram(tmp_path, parts)
    try:
        assert record["status"] == "awaiting_confirmation", "a diagram has no question words and is still read"
        assert [r["kind"] for r in record["regions"]] == ["diagram"] * 3
        assert [r["text"] for r in record["regions"]] == ["left ventricle", "right atrium", "[?]"]
        assert record["regions"][0]["label_box"] == pytest.approx({"x": 0.82, "y": 0.7, "w": 0.15, "h": 0.04})
        assert record["regions"][1]["label_box"] is None and record["regions"][1]["bbox"] is not None
        assert record["questions"] == [] and [a["kind"] for a in record["attachments"]] == ["photo"], (
            "no numbered questions and no diagram crops: the parts stay on the one photo"
        )
        assert not contract_errors("input/captured-question", record)
        confirmed = desk.confirm(record["capture_id"], {"text": record["text"]})
        assert confirmed["regions"][0]["label_box"] is not None, "confirming keeps where each label was"
        with pytest.raises(ApiError, match="validation_failed"):
            desk.turn_body(record["session_id"], {"intent": "ask", "capture_id": record["capture_id"]})
    finally:
        asyncio.run(desk.close())


def test_a_diagram_with_no_confident_part_is_unreadable(tmp_path: Path) -> None:
    _, desk, record = read_diagram(tmp_path, [unit(part(0, "[?]", (100, 100, 200, 200), None, confidence=0.2))])
    try:
        assert record["status"] == "unreadable" and record["refusal"] == {"reason": "unreadable"}
    finally:
        asyncio.run(desk.close())


def test_each_label_box_comes_from_the_devices_own_ocr_line_that_names_the_part() -> None:
    """Spark's label boxes are often a line off, so the drill's cover would show the word; the OCR line is exact."""
    parts = [unit(r) for r in HEART["regions"]]
    lines = [
        {"text": "Figure 1: the left ventricle and atria", "bbox": {"x": 0.05, "y": 0.02, "w": 0.6, "h": 0.04}},
        {"text": "left ventricle", "bbox": {"x": 0.83, "y": 0.68, "w": 0.14, "h": 0.03}},
        {"text": "valve right atrium", "bbox": {"x": 0.0, "y": 0.25, "w": 0.18, "h": 0.03}},
    ]
    ocr_label_boxes(parts, lines)
    # The line naming the part nearest the reader's guess, not the caption that also contains the words.
    assert parts[0]["label_box"] == {"x": 0.83, "y": 0.68, "w": 0.14, "h": 0.03}
    # A longer line is cut to the name's share of its characters ("right atrium" is the last 12 of 18).
    assert parts[1]["label_box"] == pytest.approx({"x": 0.06, "y": 0.25, "w": 0.12, "h": 0.03})
    assert parts[2]["label_box"] == {k: v / 1000 for k, v in HEART["regions"][2]["label_box"].items()}, (
        "an unread part keeps the reader's box"
    )
    stem = [unit(part(0, "stem", (100, 100, 50, 300), (700, 400, 80, 40)))]
    ocr_label_boxes(stem, [{"text": "the system", "bbox": {"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.03}}])
    assert stem[0]["label_box"] == {"x": 0.7, "y": 0.4, "w": 0.08, "h": 0.04}, "a word inside another is no match"
