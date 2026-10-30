"""Follow-ups from the second live run of the §19.10 demo path (SPEC §19 status, 2026-10-30): a confirmed study aid is
made in the same turn, from the only ready material or one `study_search` lists by number; a correction never opens
a new tool round; a turn that used a study tool records a complete trace; and a reply may say it searched only when a
search ran. Every learner, material and reply here is synthetic."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent_core.contracts import errors
from agent_core.engine.companion import search_claim_errors
from test_w8_companion import MOTION
from w8_companion_harness import Thread, calls, run, stop_core, thread, turn


def _source(t: Thread, title: str) -> dict[str, Any]:
    return dict(t.r.core.study.desk().create({"kind": "text", "title": title, "text": MOTION}))


def _jobs(t: Thread) -> list[dict[str, Any]]:
    conn = t.r.core.records.learner.conn  # type: ignore[union-attr]
    return [json.loads(r[0]) for r in conn.execute("SELECT body FROM study_jobs")]


def _tool_results(request: dict[str, Any], name: str) -> list[str]:
    return [str(m.get("content")) for m in request["messages"] if m.get("role") == "tool" and m.get("name") == name]


def _companion_traces(t: Thread) -> list[dict[str, Any]]:
    assert t.r.runtime.traces is not None
    t.r.runtime.traces.flush()
    return [r for r in t.r.runtime.traces.records() if r.get("kind") == "turn" and r.get("mode") == "study_companion"]


def test_a_confirmed_aid_is_made_in_one_turn_from_the_only_ready_source(tmp_path: Path) -> None:
    script = {"companion": [calls(("make_aid", {"kind": "flashcards", "count": 10})),
                            turn("I've started your 10 flashcards.")]}  # fmt: skip  # 10 binds to the job

    async def go() -> None:
        t = await thread(tmp_path, script)
        try:
            source = _source(t, "Web research: Projectile Motion Lesson Prep")
            opened = await t.open()
            await t.say(opened["session_id"], "Yes please, build them.")
            made = [(j["kind"], j["sources"][0]["source_id"]) for j in _jobs(t)]
            assert made == [("flashcards", source["source_id"])]
            actions = list((await t.snapshot(opened["session_id"]))["actions"].values())
            assert [a["action"] for a in actions] == ["open_study_job"]
            assert len(t.companion_requests()) == 2, "one tool round and the reply: two calls"
            (trace,) = _companion_traces(t)
            assert trace["status"] == "complete" and len(trace["model_calls"]) == 2
        finally:
            await stop_core(t.r)

    run(go())


def test_an_unmatched_or_empty_search_lists_the_ready_materials_by_number(tmp_path: Path) -> None:
    script = {"companion": [calls(("study_search", {"query": "my projectile motion pack"})),
                            calls(("make_aid", {"kind": "flashcards", "source_ref": 2, "count": 10})),
                            turn("I've started your flashcards from your kinematics notes.")]}  # fmt: skip

    async def go() -> None:
        t = await thread(tmp_path, script)
        try:
            older = _source(t, "Kinematics notes")
            _source(t, "Web research: Projectile Motion Lesson Prep")  # newer: listed first
            opened = await t.open()
            await t.say(opened["session_id"], "Make me 10 flashcards from my projectile motion pack")
            requests = t.companion_requests()
            (listed,) = _tool_results(requests[1], "study_search")
            found = json.loads(listed[listed.index("{"):]) if listed.lstrip().startswith("{") is False else json.loads(
                listed)  # fmt: skip
            sources = found["sources"] if "sources" in found else found["data"]["sources"]
            assert [(s["ref"], s["title"]) for s in sources] == [
                (1, "Web research: Projectile Motion Lesson Prep"), (2, "Kinematics notes")]  # fmt: skip
            assert all(s["kind"] == "text" and len(s["ready"]) == 10 for s in sources)
            assert [j["sources"][0]["source_id"] for j in _jobs(t)] == [older["source_id"]]
        finally:
            await stop_core(t.r)

    run(go())


def test_with_several_ready_materials_make_aid_asks_for_a_number(tmp_path: Path) -> None:
    script = {"companion": [calls(("make_aid", {"kind": "quiz"})), turn("Which of your materials should I use?")]}

    async def go() -> None:
        t = await thread(tmp_path, script)
        try:
            _source(t, "Kinematics notes")
            _source(t, "Forces notes")
            opened = await t.open()
            await t.say(opened["session_id"], "Make me a quiz")
            assert _jobs(t) == []
            (refused,) = _tool_results(t.companion_requests()[1], "make_aid")
            assert "several sources are ready" in refused.lower() and "study_search with no query" in refused
        finally:
            await stop_core(t.r)

    run(go())


def test_a_correction_never_opens_a_new_tool_round(tmp_path: Path) -> None:
    two_asks = turn("Shall I make them now? Or would you like a quiz instead?")  # breaks the one-ask gate
    fixed = turn("I can make flashcards from your pack now.")
    script = {"companion": [calls(("study_search", {})), two_asks, fixed]}

    async def go() -> None:
        t = await thread(tmp_path, script)
        try:
            _source(t, "Web research: Projectile Motion Lesson Prep")
            opened = await t.open()
            await t.say(opened["session_id"], "Make me 10 flashcards on range and maximum height")
            requests = t.companion_requests()
            assert len(requests) == 3, "two calls of the turn, then one correction: never a fourth"
            correction = requests[2]
            assert correction.get("tool_choice") == "none" or not correction.get("tools")
            assert "broke these rules" in str(correction["messages"][-1]["content"])
            assert len(_tool_results(correction, "study_search")) == 1, "the correction saw the search, ran none"
            (trace,) = _companion_traces(t)
            assert trace["status"] == "complete" and len(trace["model_calls"]) == 3
        finally:
            await stop_core(t.r)

    run(go())


def test_a_turn_that_used_a_study_tool_records_a_complete_trace(tmp_path: Path) -> None:
    script = {"companion": [calls(("study_search", {"query": "acceleration"})),
                            turn("Your notes cover uniform acceleration.")]}  # fmt: skip

    async def go() -> None:
        t = await thread(tmp_path, script)
        try:
            _source(t, "Kinematics notes")
            opened = await t.open()
            await t.say(opened["session_id"], "What do my notes say about acceleration?")
            (trace,) = _companion_traces(t)
            assert trace["status"] == "complete" and trace["degraded"] is False
            assert [c["toolset"] for c in trace["tool_calls"]] == ["study"]
            assert errors("trace/turn-trace", trace) == []
        finally:
            await stop_core(t.r)

    run(go())


def test_a_reply_says_it_searched_only_when_a_search_ran(tmp_path: Path) -> None:
    assert search_claim_errors("I found your pack on motion.", searched=False)
    assert search_claim_errors("I looked for your pack but didn't find it.", searched=False)
    assert not search_claim_errors("I found your pack on motion.", searched=True)
    assert not search_claim_errors("Lovely effort asking for review!", searched=False)
    script = {"companion": [turn("I found your pack on motion."), turn("Your plan starts with a warm-up.")]}

    async def go() -> None:
        t = await thread(tmp_path, script)
        try:
            opened = await t.open()
            await t.say(opened["session_id"], "Can we review?")
            snapshot = await t.snapshot(opened["session_id"])
            said = json.dumps(snapshot)
            assert "Your plan starts with a warm-up." in said and "I found your pack" not in said
        finally:
            await stop_core(t.r)

    run(go())


# --- the third live re-test (2026-10-30): a made aid behind a refused reply --------------------------------------


def test_every_gate_decision_is_in_the_trace_with_a_code_never_the_text(tmp_path: Path) -> None:
    wrong = turn("I've started your 12 flashcards.")  # 12 is not what was asked: fact binding refuses it twice
    script = {"companion": [calls(("make_aid", {"kind": "flashcards", "count": 10})), wrong, wrong]}

    async def go() -> None:
        t = await thread(tmp_path, script)
        try:
            _source(t, "Kinematics notes")
            opened = await t.open()
            await t.say(opened["session_id"], "Make me 10 flashcards")
            (trace,) = _companion_traces(t)
            gates = {g["gate"]: g for g in trace["gates"]}
            expected = {"one_ask", "fact_binding", "search_claim", "model_claims", "output_critic", "fact_refs"}
            assert expected <= set(gates)
            binding = gates["fact_binding"]
            assert (binding["fired"], binding["outcome"], binding["nudges"], binding["detail"]) == (
                True, "exhausted_canned", 1, "number:12:unit:flashcard")  # fmt: skip
            assert gates["one_ask"] == {"gate": "one_ask", "fired": False, "nudges": 1, "attempt": 2,
                                        "outcome": "passed"}  # fmt: skip
            assert "started your 12" not in json.dumps(trace) and errors("trace/turn-trace", trace) == []
        finally:
            await stop_core(t.r)

    run(go())


def test_make_aid_carries_what_was_made_as_labelled_records(tmp_path: Path) -> None:
    script = {"companion": [calls(("make_aid", {"kind": "flashcards", "count": 10})),
                            turn("I've started your 10 flashcards.")]}  # fmt: skip

    async def go() -> None:
        t = await thread(tmp_path, script)
        try:
            _source(t, "Web research: Projectile Motion Lesson Prep")
            opened = await t.open()
            await t.say(opened["session_id"], "Yes please, build them.")
            (result,) = _tool_results(t.companion_requests()[1], "make_aid")
            made = json.loads(result[result.index("{") :])["made"] if "made" not in result[:1] else None
            assert made == {"kind": "flashcards", "title": "Web research: Projectile Motion Lesson Prep",
                            "from_pack": False, "flashcard_cards": 10}  # fmt: skip
            said = json.dumps(await t.snapshot(opened["session_id"]))
            assert "I've started your 10 flashcards." in said, "10 binds to the job's count"
        finally:
            await stop_core(t.r)

    run(go())


def test_a_refused_reply_after_a_made_aid_says_what_was_made(tmp_path: Path) -> None:
    wrong = turn("I've started your 12 flashcards.")
    script = {"companion": [calls(("make_aid", {"kind": "flashcards", "count": 10})), wrong, wrong]}

    async def go() -> None:
        t = await thread(tmp_path, script)
        try:
            _source(t, "Kinematics notes")
            opened = await t.open()
            await t.say(opened["session_id"], "Make me 10 flashcards")
            snapshot = await t.snapshot(opened["session_id"])
            said = json.dumps(snapshot)
            assert "I've started 10 flashcards from your material. Open them below." in said
            assert "couldn't put that together" not in said and "12 flashcards" not in said
            assert [a["action"] for a in snapshot["actions"].values()] == ["open_study_job"]
            (trace,) = _companion_traces(t)
            assert trace["degraded_reason"] == "companion_canned"  # still a refused reply, said honestly
        finally:
            await stop_core(t.r)

    run(go())
