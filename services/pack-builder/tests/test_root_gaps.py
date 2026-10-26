"""Misconceptions linked to the earlier skill they really come from (`root_gap`): every link in the repository's
Maths and Physics sources names an active KC with published single-part practice to route to, and a link inside a
pack that names no KC of it fails the build."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pack_builder.build import load_source
from pack_builder.curriculum import root_gap_problems

CURRICULUM = Path(__file__).resolve().parents[3] / "content" / "curriculum"
SUBJECTS = ("mth", "phy")


def _tables() -> dict[str, dict[str, list[dict[str, Any]]]]:
    return {s: load_source(CURRICULUM / s / "o").tables for s in SUBJECTS}


def test_every_root_gap_lands_on_practice_of_an_active_kc() -> None:
    tables = _tables()
    kcs = {k["id"]: k for t in tables.values() for k in t["kcs"]}
    items = [i for t in tables.values() for i in t["items"]]
    linked = [m for t in tables.values() for m in t["misconceptions"] if m.get("root_gap")]
    assert len(linked) >= 10  # the demo topics: rearranging, gradients and rates
    for record in linked:
        target = record["root_gap"]["kc_id"]
        assert kcs.get(target, {}).get("status") == "active", (record["id"], target)
        practice = [i for i in items if target in i["kc_ids"] and len(i["parts"]) == 1
                    and i["type"] != "mcq_diagnostic" and i["review"]["status"] == "published"]  # fmt: skip
        assert len(practice) >= 2, (record["id"], target)
        idea = record["root_gap"]["idea"]["en"]
        assert 3 <= len(idea) <= 40 and not idea.endswith("."), idea  # it reads "This is really about {idea}."


def test_a_root_gap_inside_the_pack_must_name_one_of_its_kcs() -> None:
    pack = {"subject": "phy", "level": "o"}
    kcs = [{"id": "kc.phy.o.motion.average_speed", "status": "active"}]
    base = {"id": "mc.phy.o.example", "kc_ids": ["kc.phy.o.motion.free_fall"]}
    missing = {**base, "root_gap": {"kc_id": "kc.phy.o.motion.made_up", "idea": {"en": "something"}}}
    own = {**base, "root_gap": {"kc_id": "kc.phy.o.motion.free_fall", "idea": {"en": "free fall"}}}
    fine = {**base, "root_gap": {"kc_id": "kc.phy.o.motion.average_speed", "idea": {"en": "average speed"}}}
    other = {**base, "root_gap": {"kc_id": "kc.mth.o.number.rates", "idea": {"en": "working out a rate"}}}
    assert root_gap_problems([missing, own, fine, other], kcs, pack) == [
        "mc.phy.o.example: root gap kc.phy.o.motion.made_up is not an active KC of this pack",
        "mc.phy.o.example: root gap kc.phy.o.motion.free_fall is one of its own KCs",
    ]
