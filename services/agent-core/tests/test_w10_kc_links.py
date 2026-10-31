"""A skill's links (SPEC §21.3, JM-D38, JM-D39; W10): the Study materials tagged to it, the lecture moments whose
transcript chunk names it, the tutor's notes citing events on it, whether the tutor is tracking it, and its
misconceptions; each list bounded; read on the device only. Against the real core with the repository's Physics and
Maths packs; every title and note is invented test data. The UI's sheet tests read the reply written here
(`packages/ui/test/fixtures/kc-links.json`): set JANA_WRITE_CONCEPT_FIXTURES=1 to rewrite it."""

from __future__ import annotations

import ast
import json
import os
from pathlib import Path

from agent_core.engine import learner_map
from jana_tools import REPO_ROOT
from test_m13g_learn import run
from w10_map_harness import ABOUT_V_T, SINGLE_POINT, SPEED, V_T, ident, world

UI_FIXTURE = REPO_ROOT / "packages" / "ui" / "test" / "fixtures" / "kc-links.json"


def stable(links: dict) -> dict:
    """The reply with the ids and times a run stamps from the clock fixed, for the UI fixture."""
    out = json.loads(json.dumps(links))
    for n, note in enumerate(out["notes"]):
        note["note_id"] = ident("mem", n + 1)
    for m in out["misconceptions"]:
        m["last_seen_at"] = 1_790_000_000_000
    return out


def test_materials_moments_notes_tracked_and_misconceptions(tmp_path: Path) -> None:
    async def scenario() -> None:
        async with world(tmp_path) as w:
            lecture = w.source(
                1,
                "recording",
                "Kinematics lecture",
                [(10_000, "Welcome to the course"), (252_000, ABOUT_V_T), (400_000, ABOUT_V_T)],
            )
            slides = w.source(2, "slides", "Motion in a straight line: velocity-time graphs and acceleration")
            other = w.source(3, "document", "Shopping list")
            quiz = w.aid(1, "quiz", "Practice questions", other)
            w.study(V_T, f"aid:{quiz}", "aid_made", aid_kind="quiz", count=5)
            practised = w.practise(V_T)
            note = w.note("Draws the graph before calculating", practised[1:2])
            w.note("Likes worked examples first", w.practise(SPEED)[1:2])
            w.summary([V_T])
            w.misconception(SINGLE_POINT, V_T, "active", 3)
            links = await w.links(V_T)
            assert links["kc_id"] == V_T
            assert links["materials"] == [
                {"aid_id": quiz, "kind": "quiz", "title": "Practice questions"},
                {
                    "source_id": slides,
                    "kind": "slides",
                    "title": "Motion in a straight line: velocity-time graphs and acceleration",
                },
            ]
            assert links["moments"] == [
                {"source_id": lecture, "at_ms": 252_000, "title": "Kinematics lecture"},
                {"source_id": lecture, "at_ms": 400_000, "title": "Kinematics lecture"},
            ]
            assert links["notes"] == [
                {"note_id": note, "text": "Draws the graph before calculating", "confidence": "tentative"}
            ]
            assert links["tracked"] is True
            assert [(m["misconception_id"], m["status"]) for m in links["misconceptions"]] == [(SINGLE_POINT, "active")]
            speed = await w.links(SPEED)
            assert (speed["materials"], speed["moments"], speed["tracked"]) == ([], [], False)
            assert [n["text"] for n in speed["notes"]] == ["Likes worked examples first"]
            if os.environ.get("JANA_WRITE_CONCEPT_FIXTURES"):
                UI_FIXTURE.write_text(json.dumps(stable(links), indent=1, ensure_ascii=False) + "\n")
            assert json.loads(UI_FIXTURE.read_text()) == stable(links), "UI fixture is stale"

    run(scenario())


def test_lists_are_bounded_and_ids_checked(tmp_path: Path) -> None:
    async def scenario() -> None:
        async with world(tmp_path) as w:
            base = w.source(1, "document", "Notes")
            for n in range(15):
                w.days(0.01)
                w.study(V_T, f"aid:{w.aid(n + 10, 'summary', f'Summary {n}', base)}", "aid_made", aid_kind="summary")
            chunks = [(n * 30_000, ABOUT_V_T) for n in range(15)]
            w.source(2, "recording", "Long lecture", chunks)
            practised = w.practise(V_T, times=8)
            for n in range(8):
                w.note(f"Observation {n}", practised[1 + 2 * n : 2 + 2 * n])
            links = await w.links(V_T)
            assert (len(links["materials"]), len(links["moments"]), len(links["notes"])) == (12, 12, 6)
            # Newest first: the last summary made leads.
            assert links["materials"][0]["title"] == "Summary 14"
            assert (await w.c.get("/v1/curriculum/kcs/not-a-kc/links")).status_code == 422
            assert (await w.c.get("/v1/curriculum/kcs/kc.phy.o.motion.no_such_skill/links")).status_code == 404
            assert ident("aid", 1)

    run(scenario())


def test_links_and_the_map_are_device_only() -> None:
    """Nothing the learner's map reads reaches a model or the network (JM-D39): the module imports no provider,
    router, gateway or network code, and the desk's map methods take no model."""
    source = Path(learner_map.__file__).read_text()
    imported = {n.module for n in ast.walk(ast.parse(source)) if isinstance(n, ast.ImportFrom) and n.module}
    imported |= {a.name for n in ast.walk(ast.parse(source)) if isinstance(n, ast.Import) for a in n.names}
    assert not {m for m in imported if any(p in m for p in ("providers", "router", "net", "gateway", "httpx", "cloud"))}
    learn = (REPO_ROOT / "services" / "agent-core" / "agent_core" / "engine" / "learn.py").read_text()
    for method in ("def overview", "def kc_links", "def mark_open"):
        body = learn.split(method, 1)[1].split("\n    def ", 1)[0]
        assert "run_tool" not in body and "router" not in body and "self.record(" not in body, method


def test_video_sources_give_moments_too(tmp_path: Path) -> None:
    """W9's video files and video links carry timed transcript chunks (each line starts "[m:ss]"): their moments are
    lecture moments like a recording's."""

    async def scenario() -> None:
        async with world(tmp_path) as w:
            film = w.source(4, "video_link", "Projectiles explained", [(252_000, f"[4:12] {ABOUT_V_T}")])
            clip = w.source(5, "video", "Lab clip", [(30_000, f"[0:30] {ABOUT_V_T}")])
            links = await w.links(V_T)
            assert {(m["source_id"], m["at_ms"]) for m in links["moments"]} == {(film, 252_000), (clip, 30_000)}
            v_t = next(n for n in (await w.map())["nodes"] if n["kc_id"] == V_T)
            assert v_t["study"]["moments"] == 2

    run(scenario())
