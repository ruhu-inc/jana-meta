"""The learner's map layers (SPEC §21.4, §21.5, §21.8; W10): freshness from opportunities and from Study activity
alone, refresh due from the learner model at now, "since last time" from the device's `app_settings` with no learning
event written, disputed misconceptions returned, the Study, notes and tracked counts per skill, and no probability in
any of the three map contracts. Against the real core with the repository's Physics and Maths packs; every learner is
synthetic and every reply is validated against the command contract."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent_core.contracts import document
from agent_core.learner import model
from agent_core.learner.mastery import DAY_MS
from test_m13g_learn import run
from w10_map_harness import (
    ABOUT_V_T,
    DISTANCE,
    FREE_FALL,
    SINGLE_POINT,
    SPEED,
    V_T,
    ident,
    node,
    world,
)


def test_freshness_from_opportunities_and_from_study_activity_alone(tmp_path: Path) -> None:
    # Skills apart from each other on the prerequisite graph: practice moves `last_seen_at` on a skill's neighbours
    # too (implied evidence, LRN-10), which is a learning touch of theirs by the same column.
    vectors, units = "kc.phy.o.measurement.resultant_vectors", "kc.phy.o.motion.speed_unit_conversion"
    dt_gradient = "kc.phy.o.motion.distance_time_gradient"

    async def scenario() -> None:
        async with world(tmp_path) as w:
            w.practise(vectors)  # 40 days before the read: longer ago
            w.days(28)
            w.practise(units)  # 12 days before: this month
            w.days(9)
            w.practise(FREE_FALL)  # 3 days before: this week
            w.days(3)
            w.practise(V_T)  # today, through a closed opportunity
            w.study(dt_gradient, "att:" + ident("att", 1)[4:] + ":0", outcome="correct")  # today, in Study only
            reply = await w.map()
            fresh = {n["kc_id"]: n["freshness"] for n in reply["nodes"]}
            assert (fresh[V_T], fresh[dt_gradient], fresh[FREE_FALL], fresh[units], fresh[vectors]) == (
                "today",
                "today",
                "week",
                "month",
                "older",
            )
            # The Study-only skill has no mastery row: it is still on the map, fresh, and not started.
            assert w.conn.execute("SELECT count(*) FROM kc_mastery WHERE kc_id = ?", (dt_gradient,)).fetchone()[0] == 0
            assert node(reply, dt_gradient)["state"] == "not_started"
            seen = {r[0] for r in w.conn.execute("SELECT kc_id FROM kc_mastery")} | {dt_gradient}
            untouched = [n for n in reply["nodes"] if n["kc_id"] not in seen]
            assert untouched and {n["freshness"] for n in untouched} == {"never"}
            # Study activity older than the 26-week scan does not count.
            w.days(200)
            assert node(await w.map(), dt_gradient)["freshness"] == "never"

    run(scenario())


def test_refresh_due_is_needs_review_from_the_model_at_now(tmp_path: Path) -> None:
    async def scenario() -> None:
        async with world(tmp_path) as w:
            w.secure(V_T)
            fresh = await w.map()
            assert (node(fresh, V_T)["state"], node(fresh, V_T)["refresh_due"]) == ("mastered", False)
            # Months later the card has decayed below the bar: the stored row still says mastered, the map does not.
            w.days(180)
            stored = w.conn.execute("SELECT status FROM kc_mastery WHERE kc_id = ?", (V_T,)).fetchone()[0]
            assert stored == "mastered"
            decayed = await w.map()
            views = model.kc_views(w.conn, w.learner.projector.ctx.params, w.now)
            assert views[V_T].state == "needs_review"
            assert (node(decayed, V_T)["state"], node(decayed, V_T)["refresh_due"]) == ("needs_review", True)
            for n in decayed["nodes"]:
                assert n["refresh_due"] == (n["state"] == "needs_review")
                if n["kc_id"] in views:
                    assert n["state"] == views[n["kc_id"]].state
            # The subject map shows the same state (TABLE UXS-22a reads the same model).
            tiles = (await w.c.ok("GET", "/v1/curriculum/cur.phy.o/map"))["sections"]
            shown = {k["kc_id"]: k["state"] for s in tiles for t in s["topics"] for k in t["kcs"]}
            assert shown[V_T] == "needs_review"

    run(scenario())


def test_changed_since_from_app_settings_with_no_learning_event_written(tmp_path: Path) -> None:
    async def scenario() -> None:
        async with world(tmp_path) as w:
            w.practise(DISTANCE)
            before = w.events()
            settings = w.conn.execute("SELECT count(*) FROM settings").fetchone()[0]
            first = await w.map()
            assert {n["changed_since"] for n in first["nodes"]} == {None}, "the first open marks nothing"
            overview = await w.overview()
            assert all(t["changed"] == 0 for s in overview["subjects"] for t in s["topics"])
            assert w.events() == before, "opening the map writes no learning event"
            assert w.conn.execute("SELECT count(*) FROM settings").fetchone()[0] == settings
            key = "map_opened_at:" + w.r.runtime.stores.profile_id
            (value,) = w.device.execute("SELECT value FROM app_settings WHERE key = ?", (key,)).fetchone()
            # Only the skills with a band above Not started are kept (a missing one reads as Not started).
            assert json.loads(value)["bands"] == {DISTANCE: "learning"}
            # Later: a skill gets its first evidence and another is secured; the app opens again.
            w.days(1)
            w.practise(V_T)
            w.secure(DISTANCE)
            recorded = w.events()
            w.new_visit()
            again = await w.map()
            marks = {n["kc_id"]: n["changed_since"] for n in again["nodes"] if n["changed_since"] is not None}
            assert marks == {V_T: "new", DISTANCE: "up"}
            # The overview read in the same visit marks the same skills, and so does a re-read of the map.
            (motion,) = [
                t
                for s in (await w.overview())["subjects"]
                if s["subject_id"] == "cur.phy.o"
                for t in s["topics"]
                if t["topic_id"].endswith(".motion")
            ]
            assert motion["changed"] == 2
            assert {n["kc_id"] for n in (await w.map())["nodes"] if n["changed_since"]} == {V_T, DISTANCE}
            assert w.events() == recorded, "reading the map and the overview again writes no learning event"
            # The next visit compares against this one: nothing has moved since.
            w.new_visit()
            assert {n["changed_since"] for n in (await w.map())["nodes"]} == {None}
            # A dated map never marks anything and never records an open.
            stamp = w.device.execute("SELECT updated_at FROM app_settings WHERE key = ?", (key,)).fetchone()[0]
            w.days(1)
            dated = await w.map(as_of=_day(w.now - DAY_MS))
            assert {n["changed_since"] for n in dated["nodes"]} == {None}
            assert w.device.execute("SELECT updated_at FROM app_settings WHERE key = ?", (key,)).fetchone()[0] == stamp

    run(scenario())


def _day(ms: int) -> str:
    from datetime import UTC, datetime

    return datetime.fromtimestamp(ms / 1000, UTC).date().isoformat()


def test_disputed_misconceptions_are_returned_and_ringed(tmp_path: Path) -> None:
    async def scenario() -> None:
        async with world(tmp_path) as w:
            w.misconception(SINGLE_POINT, V_T, "active", 3)
            w.misconception("mc.phy.o.gradient_axes_swapped", V_T, "disputed", 1)
            reply = await w.map()
            statuses = {m["misconception_id"]: m["status"] for m in reply["mistakes"]}
            assert statuses == {SINGLE_POINT: "active", "mc.phy.o.gradient_axes_swapped": "disputed"}
            links = await w.links(V_T)
            assert {m["status"] for m in links["misconceptions"]} == {"active", "disputed"}
            # A disputed one is the learner's word: the overview counts only the watched one.
            (motion,) = [
                t for s in (await w.overview())["subjects"] for t in s["topics"] if t["topic_id"].endswith(".motion")
            ]
            assert motion["mistakes"] == 1

    run(scenario())


def test_study_notes_and_tracked_counts_per_skill(tmp_path: Path) -> None:
    async def scenario() -> None:
        async with world(tmp_path) as w:
            lecture = w.source(1, "recording", "Kinematics lecture", [(252_000, ABOUT_V_T), (10_000, "Welcome")])
            notes = w.source(2, "document", "My revision notes", [])
            quiz = w.aid(1, "quiz", "Revision quiz", notes)
            cards = w.aid(2, "flashcards", "Revision cards", notes)
            w.deck(1, cards, notes, ["crd_" + "1" * 26, "crd_" + "2" * 26, "crd_" + "3" * 26])
            w.study(V_T, f"aid:{quiz}", "aid_made", aid_kind="quiz", count=5)
            # Two cards reviewed once and tagged to the skill: one due now, one not; a third never reviewed.
            w.study(V_T, "card:crd_" + "1" * 26, "card_review", rating="good")
            w.study(V_T, "card:crd_" + "2" * 26, "card_review", rating="good")
            w.review("crd_" + "1" * 26, w.now - DAY_MS, 1)
            w.review("crd_" + "2" * 26, w.now + 9 * DAY_MS, 2)
            practised = w.practise(V_T)
            w.note("Draws the graph before calculating", practised[1:2])
            w.summary([V_T, SPEED])
            reply = await w.map()
            v_t = node(reply, V_T)
            # The flashcard aid is a material through its card reviews, the quiz through its activity.
            assert v_t["study"] == {"materials": 2, "moments": 1, "cards_due": 1}
            assert (v_t["notes"], v_t["tracked"]) == (1, True)
            speed = node(reply, SPEED)
            assert speed["study"] == {"materials": 0, "moments": 0, "cards_due": 0}
            assert (speed["notes"], speed["tracked"]) == (0, True)
            assert {n["kc_id"] for n in reply["nodes"] if n["tracked"]} == {V_T, SPEED}
            assert lecture

    run(scenario())


# --- no probability in any map contract (JM-D36) --------------------------------------------------------------------

FORBIDDEN = ("p_mastery", "probability", "retrievability", "p_k", "confidence_score", "theta")


def _names(schema: Any, out: set[str]) -> set[str]:
    if isinstance(schema, dict):
        for key, value in schema.get("properties", {}).items():
            out.add(key)
            _names(value, out)
        for value in schema.values():
            _names(value, out)
    elif isinstance(schema, list):
        for value in schema:
            _names(value, out)
    return out


def _numbers(schema: Any, path: str, out: list[str], defs: dict[str, Any], seen: set[str]) -> list[str]:
    """Every non-integer number a definition can hold, by path."""
    if isinstance(schema, dict):
        ref = schema.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/$defs/") and ref not in seen:
            _numbers(defs[ref.rsplit("/", 1)[1]], path, out, defs, seen | {ref})
        if schema.get("type") == "number":
            out.append(path)
        for key, value in schema.get("properties", {}).items():
            _numbers(value, f"{path}.{key}", out, defs, seen)
        for key in ("items", "anyOf", "oneOf", "allOf"):
            found = schema.get(key)
            for value in found if isinstance(found, list) else [found] if found else []:
                _numbers(value, path, out, defs, seen)
    return out


def test_no_probability_in_any_map_contract(tmp_path: Path) -> None:
    defs = document("api/commands")["$defs"]
    for name in ("ConceptMap", "CurriculumOverview", "KcLinks"):
        names = _names(defs[name], set())
        for ref in ("ConceptNode", "ConceptEdge", "ConceptNext", "ConceptQuestion", "ConceptMistake"):
            if f"#/$defs/{ref}" in json.dumps(defs[name]):
                names |= _names(defs[ref], set())
        assert not {n for n in names if any(f in n for f in FORBIDDEN)}, name
        # The only fractional number on any map is the pack's exam weight (a curriculum fact, never the learner's).
        assert _numbers(defs[name], name, [], defs, set()) == (
            ["ConceptMap.nodes.exam_weight"] if name == "ConceptMap" else []
        ), name

    async def scenario() -> None:
        async with world(tmp_path) as w:
            w.secure(V_T)
            w.study(SPEED, "aid:" + ident("aid", 9), "aid_made", aid_kind="quiz", count=3)
            for reply in (await w.map(), await w.overview(), await w.links(V_T)):
                text = json.dumps(reply)
                assert not any(f'"{f}' in text for f in FORBIDDEN)

    run(scenario())


def test_a_deleted_profile_takes_its_last_open_with_it(tmp_path: Path) -> None:
    """DAT-09: the bands kept at the last open live in the device database under the profile's key; deleting the
    profile's per-profile state removes them (and the map's in-memory replays)."""

    async def scenario() -> None:
        async with world(tmp_path) as w:
            w.practise(V_T)
            await w.map()
            profile = w.r.runtime.stores.profile_id
            key = "map_opened_at:" + profile
            assert w.device.execute("SELECT count(*) FROM app_settings WHERE key = ?", (key,)).fetchone()[0] == 1
            w.r.runtime.drop_lesson_positions(f"prf_{profile}")
            assert w.device.execute("SELECT count(*) FROM app_settings WHERE key = ?", (key,)).fetchone()[0] == 0
            assert profile not in w.r.runtime._map_states

    run(scenario())
