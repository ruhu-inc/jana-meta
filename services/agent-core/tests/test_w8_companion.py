"""W8 phase 2 (SPEC §19.3.3, §19.5.1, §19.6, §19.8): Your tutor in Study. One episode per profile per day; homework
handed to the guided tutor with no model call; distress screened before routing; recall in the user message with a
byte-identical cached prefix; a change-keyed status line; fact binding; make_aid and start_research as durable
actions that survive a restart; the study tools' literal matcher, integer refs and fixed queries; past-scope recall
local and inside the profile; what a cloud call is offered; profile isolation; and the turn API's model_unavailable
check before the companion's branch. Every learner, source and message here is synthetic."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
from agent_core.config import Settings
from agent_core.contracts import errors
from agent_core.engine.companion import cloud_tools, fact_binding_errors, strip_for_cloud
from agent_core.engine.memory_session import MemoryAccess, SessionMemory
from agent_core.engine.memory_tools import MemoryTools, StudyTools
from agent_core.learner.service import NOTES_WRITER
from agent_core.store.ids import new_ulid
from agent_core.tools.spec import InvalidArguments
from memory_harness import PROFILE_A, store
from test_m10a_profiles import student
from w8_companion_harness import Thread, calls, reopen, run, stop_core, thread, turn

HOMEWORK = "A car accelerates from rest to 20 m/s in 5 s. Calculate its acceleration."
DISTRESS = "I can't do this anymore, sometimes I want to die"
MOTION = (
    "Motion in a straight line\n\nFor motion in a straight line with uniform acceleration, v = u + at gives the final "
    "velocity.\n\nThe projectile's range depends on its launch speed."
)


def _user(request: dict[str, Any]) -> str:
    return str(request["messages"][-1]["content"])


def _system(request: dict[str, Any]) -> str:
    return str(request["messages"][0]["content"])


def _tool_results(request: dict[str, Any]) -> list[Any]:
    return [json.loads(m["content"]) if m["content"].startswith("{") else m["content"]
            for m in request["messages"] if m["role"] == "tool"]  # fmt: skip


def _note(t: Thread, text: str) -> None:
    learner = t.r.core.records.learner  # type: ignore[union-attr]
    sid = new_ulid()
    learner.conn.execute("INSERT INTO sessions (session_id, mode, subject, started_at) VALUES (?, 'guided', 'physics',"
                         " 1)", (sid,))  # fmt: skip
    hint = learner.record("hint", {"session_id": sid, "problem_ref": "prob_1", "step_index": 0, "rung": 1,
                                   "trigger": "student_request", "kc_ids": ["kc.phy.o.motion.average_speed"]},
                          source="engine", session_id=sid)  # fmt: skip
    learner.record("note_written", {"note_id": new_ulid(), "text": text, "status": "active", "subject": "physics",
                                    "source_event_ids": [hint.event_id]}, source="reflector", session_id=sid,
                   writer=NOTES_WRITER)  # fmt: skip


def _source(t: Thread) -> dict[str, Any]:
    return dict(t.r.core.study.desk().create({"kind": "text", "title": "Kinematics notes", "text": MOTION}))


# --- episodes (§19.3.3, JM-D23) ---------------------------------------------------------------------------------


def test_one_episode_per_profile_per_day_under_concurrent_opens(tmp_path: Path) -> None:
    async def go() -> None:
        t = await thread(tmp_path, {})
        try:
            first, second = await asyncio.gather(t.open(), t.open())
            assert first["session_id"] == second["session_id"] and first["thread_id"] == second["thread_id"]
            assert sorted([first["resumed"], second["resumed"]]) == [False, True]
            for opened in (first, second):
                assert errors("api/commands#/$defs/CompanionOpened", opened) == []
            conn = t.r.core.records.learner.conn  # type: ignore[union-attr]
            assert conn.execute("SELECT count(*) FROM companion_episodes").fetchone()[0] == 1
            assert conn.execute(
                "SELECT mode FROM sessions WHERE session_id = ?", (first["session_id"].removeprefix("ses_"),)
            ).fetchone() == ("study_companion",)
            # The thread is not listed with tutoring sessions.
            listed = (await t.api.call("GET", "/v1/sessions", profile=t.token)).json()["sessions"]
            assert first["session_id"] not in [s["session_id"] for s in listed]
        finally:
            await stop_core(t.r)

    run(go())


# --- a turn (§19.5.1) --------------------------------------------------------------------------------------------


def test_homework_is_handed_to_the_tutor_with_no_model_call_and_the_question_in_the_payload(tmp_path: Path) -> None:
    async def go() -> None:
        t = await thread(tmp_path, {})
        try:
            opened = await t.open()
            await t.say(opened["session_id"], HOMEWORK)
            assert t.companion_requests() == []  # PED-01: no model is asked to answer it
            snap = await t.snapshot(opened["session_id"])
            actions = list(snap.get("actions", {}).values())
            assert [(a["action"], a["payload"]) for a in actions] == [("open_tutor", {"question": HOMEWORK})]
            assert errors("api/commands#/$defs/Snapshot", snap) == []
            assert any("tutor" in str(p.get("text")) for p in snap["parts"].values())
        finally:
            await stop_core(t.r)

    run(go())


def test_distress_is_screened_before_routing(tmp_path: Path) -> None:
    async def go() -> None:
        t = await thread(tmp_path, {})
        try:
            opened = await t.open()
            await t.say(opened["session_id"], DISTRESS)
            assert t.companion_requests() == []
            snap = await t.snapshot(opened["session_id"])
            assert snap.get("actions", {}) == {}  # never routed: no hand-over, no action
            notices = [p["notice"]["code"] for p in snap["parts"].values() if p.get("kind") == "notice"]
            assert "calm_screen" in notices or any(p.get("kind") == "notice" for p in snap["parts"].values())
            conn = t.r.core.records.learner.conn  # type: ignore[union-attr]
            flagged = [
                json.loads(r[0]) for r in conn.execute("SELECT payload FROM events WHERE type = 'safety_flagged'")
            ]
            assert [f["category"] for f in flagged] == ["distress"]
        finally:
            await stop_core(t.r)

    run(go())


def test_recall_goes_in_the_user_message_and_the_prefix_is_byte_identical(tmp_path: Path) -> None:
    async def go() -> None:
        t = await thread(tmp_path, {"companion": [turn("Let's start with average speed."), turn("Good idea.")]})
        try:
            _note(t, "Mixes up distance and displacement in speed questions")
            opened = await t.open()
            await t.say(opened["session_id"], "What did I find hard last time?")
            await t.say(opened["session_id"], "And what about motion graphs?")
            first, second = t.companion_requests()
            assert _system(first) == _system(second)  # the cached prefix: soul, role, tools, learner block
            assert "Mixes up distance" in _user(first) and "Mixes up distance" not in _system(first)
            assert "<learner-notes>" in _user(first)
        finally:
            await stop_core(t.r)

    run(go())


def test_the_status_line_is_appended_only_when_its_key_changes(tmp_path: Path) -> None:
    async def go() -> None:
        t = await thread(tmp_path, {"companion": [turn("Hello."), turn("Sure."), turn("Let’s review.")]})
        try:
            opened = await t.open()
            await t.say(opened["session_id"], "Where should I start today?")  # not small talk, which a template answers
            await t.say(opened["session_id"], "What now?")
            conn = t.r.core.records.learner.conn  # type: ignore[union-attr]
            conn.execute("INSERT INTO review_cards (kc_id, state, stability, difficulty, due_at, last_event_seq)"
                         " VALUES ('kc.phy.o.motion.average_speed', 'review', 3, 5, 0, 0)")  # fmt: skip
            await t.say(opened["session_id"], "Anything due?")
            first, second, third = (_user(q) for q in t.companion_requests())
            assert "Status: cards due 0" in first
            assert "Status:" not in second  # the same key: not repeated
            assert "Status: cards due 1" in third  # a changed number changes the key
        finally:
            await stop_core(t.r)

    run(go())


def test_fact_binding_rejects_a_number_with_the_wrong_label(tmp_path: Path) -> None:
    status = "cards due 12; exam in 19 days"
    assert fact_binding_errors("You have 12 cards due and 19 days to go.", [status]) == []
    assert fact_binding_errors("You have 12 days left.", [status])  # 12 is cards, not days
    assert fact_binding_errors("You have 13 cards due.", [status])  # 13 is in no tool result
    assert fact_binding_errors("Streak: 4 days.", [{"streak_days": 4}]) == []
    assert fact_binding_errors("4 cards to go.", [{"streak_days": 4}])

    async def go() -> None:
        t = await thread(
            tmp_path, {"companion": [turn("You have 5 days of cards due."), turn("Nothing is due today.")]}
        )
        try:
            opened = await t.open()
            await t.say(opened["session_id"], "How much is due?")
            requests = t.companion_requests()
            assert len(requests) == 2  # the draft with an unbound number was nudged once
            assert "broke these rules" in _user(requests[1])
            snap = await t.snapshot(opened["session_id"])
            assert [p["text"] for p in snap["parts"].values() if p.get("kind") == "text"] == ["Nothing is due today."]
        finally:
            await stop_core(t.r)

    run(go())


def test_make_aid_creates_a_study_job_and_a_durable_action(tmp_path: Path) -> None:
    script = {"companion": [calls(("study_search", {"query": "uniform acceleration"})),
                            calls(("make_aid", {"kind": "flashcards", "source_ref": 1, "count": 5})),
                            turn("I've started your flashcards on uniform acceleration.")]}  # fmt: skip

    async def go() -> None:
        t = await thread(tmp_path, script)
        try:
            source = _source(t)
            opened = await t.open()
            await t.say(opened["session_id"], "Make me 5 flashcards on uniform acceleration")
            conn = t.r.core.records.learner.conn  # type: ignore[union-attr]
            jobs = [json.loads(r[0]) for r in conn.execute("SELECT body FROM study_jobs")]
            assert [(j["kind"], j["sources"][0]["source_id"]) for j in jobs] == [("flashcards", source["source_id"])]
            actions = list((await t.snapshot(opened["session_id"]))["actions"].values())
            assert [(a["action"], a["payload"]) for a in actions] == [("open_study_job", {"job_id": jobs[0]["job_id"]})]
            assert actions[0]["label_key"] == "study.companion.action.open_study_job"
        finally:
            await stop_core(t.r)

    run(go())


def test_actions_survive_snapshot_hydration_and_restart(tmp_path: Path) -> None:
    script = {"companion": [calls(("start_research", {"topic": "projectile motion"})), turn("Let's research it.")]}

    async def go() -> None:
        t = await thread(tmp_path, script)
        opened = await t.open()
        await t.say(opened["session_id"], "I want to learn about projectile motion from the web")
        before = (await t.snapshot(opened["session_id"]))["actions"]
        assert [a["action"] for a in before.values()] == ["open_research"]
        t = await reopen(t, {})
        try:
            again = await t.open()
            assert again["session_id"] == opened["session_id"] and again["resumed"]
            after = (await t.snapshot(opened["session_id"]))["actions"]
            assert after == before  # the button is still there after a restart
        finally:
            await stop_core(t.r)

    run(go())


def test_start_research_never_skips_the_conversation(tmp_path: Path) -> None:
    script = {"companion": [calls(("start_research", {"topic": "projectile motion"})), turn("Opening research.")]}

    async def go() -> None:
        t = await thread(tmp_path, script)
        try:
            opened = await t.open()
            await t.say(opened["session_id"], "Research projectile motion for me")
            conn = t.r.core.records.learner.conn  # type: ignore[union-attr]
            assert conn.execute("SELECT count(*) FROM study_research").fetchone()[0] == 0  # no job from here
            actions = list((await t.snapshot(opened["session_id"]))["actions"].values())
            assert [(a["action"], a["payload"]) for a in actions] == [
                ("open_research", {"question": "projectile motion"})
            ]
        finally:
            await stop_core(t.r)

    run(go())


# --- the study tools (§19.3.3, MEM-05 amendment) ------------------------------------------------------------------


def test_study_search_uses_the_literal_matcher_and_integer_refs(tmp_path: Path) -> None:
    script = {"companion": [calls(("study_search", {"query": "u + at"}), ("study_search", {"query": "u.+at"})),
                            turn("Found it in your notes.")]}  # fmt: skip

    async def go() -> None:
        t = await thread(tmp_path, script)
        try:
            source = _source(t)
            opened = await t.open()
            await t.say(opened["session_id"], "Where do my notes give the final velocity?")
            found, regex = _tool_results(t.companion_requests()[-1])
            # Refs continue this turn's table (recall by code took the first), so make_aid can name any of them.
            assert all(type(i["ref"]) is int for i in found["items"]) and "u + at" in found["items"][0]["text"]
            assert found["items"][0]["source_label"] == "Kinematics notes"
            assert regex["items"] == []  # "." and "+" are literal: never a regular expression
            wire = json.dumps(found)
            assert source["source_id"] not in wire and "src_" not in wire  # integer refs, never a stored id
        finally:
            await stop_core(t.r)

    run(go())


def test_progress_read_is_a_fixed_query(tmp_path: Path) -> None:
    script = {"companion": [calls(("progress_read", {})), turn("Here is where you are.")]}

    async def go() -> None:
        t = await thread(tmp_path, script)
        try:
            opened = await t.open()
            await t.say(opened["session_id"], "How am I doing?")
            (result,) = _tool_results(t.companion_requests()[-1])
            assert set(result) == {"marker", "bands", "due", "exam_distance_days", "streak_days"}
            assert set(result["due"]) == {"learner_cards", "study_cards"}
            assert all(set(b) == {"ref", "skill", "band"} for b in result["bands"])
            assert "kc." not in json.dumps(result)
            assert t.r.runtime.providers["local"].requests  # the tool took no query text: the arguments are {}
        finally:
            await stop_core(t.r)

    run(go())


def test_session_recall_past_scope_stays_in_the_profile(tmp_path: Path) -> None:
    script = {
        "companion": [
            calls(("session_recall", {"pattern": "projectile", "scope": "past"})),
            turn("Found it."),
            calls(("session_recall", {"pattern": "projectile", "scope": "past"})),
            turn("Nothing."),
        ]
    }

    async def go() -> None:
        t = await thread(tmp_path, script)
        try:
            records = t.r.core.records
            assert records is not None
            # A past tutoring session of this profile, with its stored transcript.
            sid = new_ulid()
            records.learner.conn.execute(  # type: ignore[union-attr]
                "INSERT INTO sessions (session_id, mode, subject, started_at, ended_at) VALUES (?, 'guided', 'physics',"
                " 1, 2)", (sid,))  # fmt: skip
            records.learner.conn.execute(  # type: ignore[union-attr]
                "INSERT INTO turns (turn_id, session_id, idx, speaker, status, student_text, started_at) VALUES (?, ?,"
                " 0, 'student', 'complete', 'a projectile launched at 30 degrees', 1)", (new_ulid(), sid))  # fmt: skip
            opened = await t.open()
            await t.say(opened["session_id"], "What did we say about projectiles?")
            (found,) = _tool_results(t.companion_requests()[-1])
            assert [m["text"] for m in found["matches"]] == ["a projectile launched at 30 degrees"]
            # Another profile's thread finds nothing of it.
            other = await t.api.add(student("Ben"))
            token = (await t.api.unlock(other)).json()["profile_token"]
            mine = Thread(t.r, t.api, token)
            theirs = await mine.open()
            await mine.say(theirs["session_id"], "What did we say about projectiles?")
            (nothing,) = _tool_results(t.companion_requests()[-1])
            assert nothing["matches"] == []
        finally:
            await stop_core(t.r)

    run(go())


def _tools(cloud: bool, share: bool) -> tuple[MemoryTools, StudyTools]:
    held = store()
    memory = SessionMemory(MemoryAccess(PROFILE_A, held.source), Settings(), "ses_" + "0" * 26)
    return (MemoryTools(memory, Settings(), lambda: cloud),
            StudyTools(memory, Settings(), lambda: cloud, share=lambda: share))  # fmt: skip


class _Context:
    class session:
        session_id = "ses_" + "0" * 26
        subject = "physics"


def test_a_cloud_call_is_never_offered_past_scope_recall() -> None:
    names = ["memory_recall", "session_recall", "study_search", "progress_read", "plan", "make_aid", "start_research"]
    assert "memory_recall" not in cloud_tools(names, True)  # notes never ride a cloud call (MDL-25)
    memory, _ = _tools(cloud=True, share=True)
    with pytest.raises(InvalidArguments, match="this computer"):
        asyncio.run(memory.search({"pattern": "projectile", "scope": "past"}, _Context()))  # type: ignore[arg-type]
    local, _ = _tools(cloud=False, share=False)
    assert asyncio.run(local.search({"pattern": "projectile", "scope": "past"}, _Context()))["matches"] == []  # type: ignore[arg-type]


def test_a_cloud_call_gets_study_search_only_under_study_materials() -> None:
    names = ["session_recall", "study_search", "progress_read"]
    assert cloud_tools(names, share_materials=False) == ["progress_read"]
    assert cloud_tools(names, share_materials=True) == ["study_search", "progress_read"]
    _, off = _tools(cloud=True, share=False)
    with pytest.raises(InvalidArguments, match="Study online"):
        asyncio.run(off.search({"query": "acceleration"}, _Context()))  # type: ignore[arg-type]
    _, on = _tools(cloud=True, share=True)
    assert asyncio.run(on.search({"query": "acceleration"}, _Context()))["items"] == []  # type: ignore[arg-type]
    text = (
        "<own-materials>\nExcerpt</own-materials>\n<learner-notes>\n[1] a note\n</learner-notes>\n<student>hi</student>"
    )
    assert strip_for_cloud(text, share_materials=False) == "<student>hi</student>"
    assert "<own-materials>" in strip_for_cloud(text, share_materials=True)
    assert "<learner-notes>" not in strip_for_cloud(text, share_materials=True)


def test_a_profile_switch_shows_nothing_of_the_first(tmp_path: Path) -> None:
    async def go() -> None:
        t = await thread(tmp_path, {"companion": [turn("Hi Ada.")]})
        try:
            opened = await t.open()
            await t.say(opened["session_id"], "Hello")
            other = await t.api.add(student("Ben"))
            token = (await t.api.unlock(other)).json()["profile_token"]
            ben = Thread(t.r, t.api, token)
            theirs = await ben.open()
            assert theirs["session_id"] != opened["session_id"] and theirs["thread_id"] != opened["thread_id"]
            assert not theirs["resumed"]
            hidden = await t.api.call("GET", f"/v1/sessions/{opened['session_id']}/snapshot", profile=token)
            assert hidden.status_code == 404  # Ada's thread is not Ben's to read
        finally:
            await stop_core(t.r)

    run(go())


def test_model_unavailable_is_raised_before_the_companion_branch(tmp_path: Path) -> None:
    async def go() -> None:
        t = await thread(tmp_path, {})
        try:
            opened = await t.open()
            t.r.core.tutor_unavailable = lambda: True
            from api_harness import ask

            sent = await t.api.call("POST", f"/v1/sessions/{opened['session_id']}/turns", ask("Hello"), profile=t.token)
            assert sent.status_code in (409, 422, 503) and sent.json()["error"]["code"] == "model_unavailable"
            assert t.companion_requests() == []
            refused = await t.api.call("POST", "/v1/companion", {}, profile=t.token)
            assert refused.status_code == 200 and refused.json()["can_reply"] is False
        finally:
            await stop_core(t.r)

    run(go())
