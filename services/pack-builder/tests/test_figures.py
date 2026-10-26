"""Checked figures on items, worked examples and lessons (VSL-12, VSL-13): resolved and traced at build time.

A record's `visual` names a catalogue kind (optionally over a template preset) and the build resolves it through the
engine's one validator with the verification tools. Every number it shows traces to a build check, a preset or a
given of the record's statement; a question's figure never shows its own answer. Seeded faults are applied to copies
of the source tree."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest
import yaml
from agent_core.config import Settings
from agent_core.contracts import errors as contract_errors
from pack_builder import source as tree
from pack_builder.build import build, load_source, problems_of
from signing_service.keys import DEV_KEY_ID, dev_key

REPO = Path(__file__).resolve().parents[3]
PHY = REPO / "content" / "curriculum" / "phy" / "o"
MTH = REPO / "content" / "curriculum" / "mth" / "o"


def _records(doc: dict[str, Any], table: str) -> dict[str, dict[str, Any]]:
    return {str(r["id"]): r for r in doc[table]}


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> dict[str, dict[str, Any]]:
    docs = {}
    for name, source in (("phy", PHY), ("mth", MTH)):
        out = tmp_path_factory.mktemp(name)
        docs[name] = json.loads(build(source, out, key=dev_key(), key_id=DEV_KEY_ID).json_path.read_text())
    return docs


def _copy(tmp_path: Path, source: Path = PHY) -> Path:
    target = tmp_path / "src" / source.parent.name / "o"
    shutil.copytree(source, target)
    shutil.copytree(tree.ref_dir(source), tree.ref_dir(target))
    return target


def _problems(source: Path) -> list[str]:
    found, _ = problems_of(load_source(source), Settings())
    return found


def _edit(path: Path, change: Any) -> None:
    record = yaml.safe_load(path.read_text(encoding="utf-8"))
    change(record)
    path.write_text(yaml.safe_dump(record, sort_keys=False, allow_unicode=True), encoding="utf-8")


def test_figures_carried_pre_resolved(built: dict[str, dict[str, Any]]) -> None:
    kinds = set()
    for doc in built.values():
        for table in ("items", "worked_examples"):
            for rid, record in _records(doc, table).items():
                resolved = (record.get("visual") or {}).get("resolved")
                if resolved is None:
                    assert "visual" not in record or "diagram_id" in record["visual"], rid
                    continue
                assert contract_errors("visuals/visual-spec#/$defs/resolved", resolved) == [], rid
                assert resolved["status"] == "ok", rid
                kinds.add(resolved["type"])
    # Every Maths and Physics kind wired into content, each with a renderer.
    assert {"function_graph", "motion_graph", "free_body", "circuit", "ray_diagram"} <= kinds


def test_demo_velocity_time_figure(built: dict[str, dict[str, Any]]) -> None:
    example = _records(built["phy"], "worked_examples")["wex.phy.o.motion.0002"]
    resolved = example["visual"]["resolved"]
    assert resolved["type"] == "motion_graph" and resolved["params"]["graph"] == "velocity_time"
    assert "slope" in [p["id"] for p in resolved["parts"]]
    # The points are the statement's givens (10 m/s, 25 m/s, 5.0 s) and the start of the clock.
    assert {"kn_zero", "kn_given1", "kn_given2", "kn_given3"} == set(resolved["numbers_from"])


def test_preset_figure_traces_to_checks_and_the_preset(built: dict[str, dict[str, Any]]) -> None:
    example = _records(built["phy"], "worked_examples")["wex.phy.o.circuits.0001"]
    resolved = example["visual"]["resolved"]
    assert resolved["ref"] == "dgm.phy.circuit_series_two_lamps.v1"
    assert any(s.startswith("chk_build_fig_") for s in resolved["numbers_from"])  # phys_circuit's readings
    assert "pack:pack.phy.o/visual_presets/dgm.phy.circuit_series_two_lamps.v1" in resolved["numbers_from"]
    assert resolved["computed"]["labels"]["V1.reading"] == "30/7 V"  # the p.d. across the 5 Ω lamp, tool-computed


def test_question_figure_never_shows_the_answer(built: dict[str, dict[str, Any]], tmp_path: Path) -> None:
    item = _records(built["phy"], "items")["itm.phy.o.circuits.0001"]
    assert item["visual"]["resolved"]["computed"].get("labels", {}) == {}  # no readings on the question's own figure
    source = _copy(tmp_path)

    def show_total(record: dict[str, Any]) -> None:
        record["visual"]["params"]["show"] = ["equivalent_resistance"]

    _edit(source / "items" / "itm.phy.o.circuits.0001.yaml", show_total)
    assert "itm.phy.o.circuits.0001: its figure shows the answer (part a key 8)" in _problems(source)


def test_untraced_figure_number_fails_the_build(tmp_path: Path) -> None:
    source = _copy(tmp_path)

    def invent(record: dict[str, Any]) -> None:
        record["visual"]["params"]["points"][1]["value"] = "30"

    _edit(source / "worked-examples" / "wex.phy.o.motion.0002.yaml", invent)
    found = [p for p in _problems(source) if "figure" in p]
    assert found and found[0].startswith("wex.phy.o.motion.0002: its figure does not resolve (visual_untraced_number")
