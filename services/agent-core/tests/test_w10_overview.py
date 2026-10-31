"""Progress's overview (SPEC §21.1, §21.8; JM-D35, TABLE UXS-22a; W10): every installed subject as topic tiles, and
each tile's rule, bands and freshness equal the subject map's and the skill map's for the same skills. Against the
real core with the repository's Physics and Maths packs; the learner is synthetic. The UI's overview tests read the
reply written here (`packages/ui/test/fixtures/curriculum-overview.json`): set JANA_WRITE_CONCEPT_FIXTURES=1 to
rewrite it."""

from __future__ import annotations

import json
import os
from pathlib import Path

from agent_core.engine.learner_map import freshest, topic_rule
from jana_tools import REPO_ROOT
from test_m13g_learn import run
from w10_map_harness import FREE_FALL, SINGLE_POINT, V_T, world

UI_FIXTURE = REPO_ROOT / "packages" / "ui" / "test" / "fixtures" / "curriculum-overview.json"


def test_topic_rule_is_table_uxs_22a_first_matching_row() -> None:
    assert topic_rule(["mastered", "needs_review", "moved_on"]) == "needs_review"
    assert topic_rule(["learning", "moved_on"]) == "moved_on"
    assert topic_rule(["not_started", "not_started"]) == "not_started"
    assert topic_rule(["mastered", "mastered"]) == "mastered"
    assert topic_rule(["ready_to_check", "mastered"]) == "ready_to_check"
    assert topic_rule(["learning", "mastered"]) == "learning"
    assert topic_rule(["not_started", "mastered"]) == "learning"


def test_tiles_equal_the_subject_map_and_the_skill_map(tmp_path: Path) -> None:
    async def scenario() -> None:
        async with world(tmp_path) as w:
            w.practise("kc.phy.o.motion.distance_time_gradient")
            w.days(9)
            w.secure(V_T)
            w.practise(FREE_FALL)
            w.misconception(SINGLE_POINT, V_T, "suspected", 1)
            overview = await w.overview()
            installed = {s["subject_id"] for s in overview["subjects"]}
            assert installed == {"cur.phy.o", "cur.mth.o"}, "every installed subject, and only those"
            for subject in overview["subjects"]:
                code = subject["subject_id"].split(".")[1]
                tiles = [
                    t
                    for s in (await w.c.ok("GET", f"/v1/curriculum/{subject['subject_id']}/map"))["sections"]
                    for t in s["topics"]
                ]
                skills = {n["kc_id"]: n for n in (await w.map(code))["nodes"]}
                assert [t["topic_id"] for t in subject["topics"]] == [t["node_id"] for t in tiles]
                for tile, shown in zip(subject["topics"], tiles, strict=True):
                    states = [k["state"] for k in shown["kcs"]]
                    bands = {
                        b: sum(1 for k in shown["kcs"] if k["band"] == b) for b in ("not_started", "learning", "secure")
                    }
                    assert tile["kcs"] == len(shown["kcs"]) and tile["bands"] == bands
                    assert tile["rule"] == topic_rule(states)
                    assert tile["freshness"] == freshest(skills[k["kc_id"]]["freshness"] for k in shown["kcs"])
                    assert tile["refresh_due"] == any(skills[k["kc_id"]]["refresh_due"] for k in shown["kcs"])
                    assert all(skills[k["kc_id"]]["state"] in (k["state"], "explaining") for k in shown["kcs"])
            (motion,) = [t for s in overview["subjects"] for t in s["topics"] if t["topic_id"].endswith(".motion")]
            assert motion["rule"] == "learning" and motion["freshness"] == "today" and motion["mistakes"] == 1
            assert motion["bands"]["secure"] == 1
            if os.environ.get("JANA_WRITE_CONCEPT_FIXTURES"):
                UI_FIXTURE.write_text(json.dumps(overview, indent=1, ensure_ascii=False) + "\n")
            assert json.loads(UI_FIXTURE.read_text()) == overview, "UI fixture is stale"

    run(scenario())
