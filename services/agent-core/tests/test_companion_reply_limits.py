"""A local Companion reply stays bounded without losing its final sentence or its verified facts."""

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from agent_core.engine import companion, companion_facts
from agent_core.engine.companion import MAX_REPLY_CHARS, fit_reply, one_ask_errors, wanted_refs
from w8_companion_harness import calls, reply, run, stop_core, thread, turn


def test_a_complete_reply_at_the_character_cap_keeps_its_ending() -> None:
    text = "a" * (MAX_REPLY_CHARS - 1) + "."
    assert fit_reply(text, MAX_REPLY_CHARS) == text


def test_a_draft_that_hits_the_schema_cap_finishes_at_its_last_sentence() -> None:
    sentence = "The bell becomes a learned signal."
    text = sentence + " " + "a" * (MAX_REPLY_CHARS - len(sentence) - 1)
    assert fit_reply(text, MAX_REPLY_CHARS) == sentence


def test_reserving_room_for_a_fact_does_not_leave_a_dangling_sentence() -> None:
    first = "The treat follows the sitting behaviour."
    text = first + " " + "The dog then repeats the behaviour because of that consequence."
    assert fit_reply(text, len(first) + 15) == first
    assert fit_reply("A long sentence without a complete stop", 20) == "A long sentence…"


@pytest.mark.parametrize(("hardware", "cap"), [("low", 300), ("high", 400)])
def test_companion_requests_apply_the_role_output_budget(tmp_path: Path, hardware: str, cap: int) -> None:
    async def go() -> None:
        t = await thread(tmp_path, {"companion": [turn("The consequence follows the behaviour.")]})
        try:
            t.r.core.session_class = lambda: hardware
            opened = await t.open()
            await t.say(opened["session_id"], "Why is sitting for a treat operant conditioning?")
            requests = t.companion_requests()
            assert requests
            assert all(request["max_tokens"] == cap for request in requests)
        finally:
            await stop_core(t.r)

    run(go())


@pytest.mark.parametrize("complete", [True, False])
def test_visible_reply_keeps_a_complete_ending(tmp_path: Path, complete: bool) -> None:
    sentence = "The bell becomes a learned signal."
    text = (
        ("a" * (MAX_REPLY_CHARS - 1) + ".")
        if complete
        else (sentence + " " + "a" * (MAX_REPLY_CHARS - len(sentence) - 1))
    )

    async def go() -> None:
        t = await thread(tmp_path, {"companion": [turn(text)]})
        try:
            opened = await t.open()
            await t.say(opened["session_id"], "Explain the bell example.")
            snapshot = await t.snapshot(opened["session_id"])
            latest = [m for m in snapshot["messages"] if m["role"] == "tutor"][-1]
            shown = "".join(snapshot["parts"][pid].get("text", "") for pid in latest["part_ids"])
            assert shown == (text if complete else sentence)
        finally:
            await stop_core(t.r)

    run(go())


async def _shown(t: Any, session_id: str) -> str:
    snap = await t.snapshot(session_id)
    last = [m for m in snap["messages"] if m.get("role") == "tutor"][-1]
    return "\n".join(snap["parts"][p].get("text", "") for p in last["part_ids"])


def _fact(metric: str) -> companion_facts.Fact:
    return companion_facts.Fact("k" + metric, metric, 0, "cards", None, "2026-11-04", "review schedule", "Due: 0.")


@pytest.mark.parametrize(
    "text", ["Why does the bell work on its own after a while?", "What was the first thing I asked you about today?"]
)
def test_a_question_on_something_else_does_not_end_in_due_counts(text: str) -> None:
    facts = [_fact("due_cards"), _fact("streak_days"), _fact("moment")]
    assert wanted_refs(facts, [1, 2, 3], text, False) == [3]


@pytest.mark.parametrize("quote", ['"What is extinction?"', "“What is extinction?”"])
def test_a_question_quoted_back_is_not_a_second_question(quote: str) -> None:
    assert one_ask_errors(f"Your first question was {quote} Want to pick it up?") == []


def test_two_questions_of_its_own_are_still_refused() -> None:
    assert one_ask_errors("What is extinction? Want to pick it up?") == ["more than one question"]


@pytest.mark.parametrize("text", ["What is due today?", "How many cards do I have?", "How is my exam looking?"])
def test_a_question_about_the_schedule_keeps_its_facts(text: str) -> None:
    assert wanted_refs([_fact("due_cards")], [1], text, False) == [1]


def test_a_turn_that_read_progress_keeps_its_facts() -> None:
    assert wanted_refs([_fact("due_cards")], [1], "Where should I focus?", True) == [1]


def test_a_reference_that_was_never_supplied_is_still_left_for_the_gate() -> None:
    assert wanted_refs([_fact("due_cards")], [9], "Why does the bell work?", False) == [9]


def test_due_counts_do_not_reach_a_reply_to_a_lecture_question(tmp_path: Path) -> None:
    async def go() -> None:
        selected = reply(json.dumps({"text": "The pairing taught the dog a signal.", "action": None, "fact_refs": [1]}))
        t = await thread(tmp_path, {"companion": [selected]})
        try:
            opened = await t.open()
            await t.say(opened["session_id"], "Why does the bell work on its own?")
            shown = await _shown(t, opened["session_id"])
            assert "The pairing taught the dog a signal." in shown
            assert "due" not in shown.lower()
        finally:
            await stop_core(t.r)

    run(go())


def test_a_local_turn_past_its_limit_says_the_computer_is_slow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    async def slow(*_args: Any, **_kwargs: Any) -> None:
        await asyncio.sleep(30)

    async def go() -> None:
        t = await thread(tmp_path, {"companion": [turn("never shown")]}, companion_local_turn_s=1.0)
        try:
            monkeypatch.setattr(companion, "_call", slow)
            opened = await t.open()
            await t.say(opened["session_id"], "Explain the bell.")
            assert "taking too long" in await _shown(t, opened["session_id"])
            assert t.r.core.sessions[opened["session_id"]].engine.traces[-1]["degraded_reason"] == "local_time_limit"
        finally:
            await stop_core(t.r)

    run(go())


def test_a_recall_that_misses_points_at_the_conversation(tmp_path: Path) -> None:
    async def go() -> None:
        t = await thread(
            tmp_path,
            {
                "companion": [
                    turn("Hello."),
                    calls(("session_recall", {"pattern": "very first message"})),
                    turn("Fine."),
                ]
            },
        )
        try:
            opened = await t.open()
            await t.say(opened["session_id"], "Tell me about momentum.")
            await t.say(opened["session_id"], "What did I ask first?")
            sent = json.dumps(t.companion_requests()[-1]["messages"])
            assert "Their earlier messages are above in this conversation." in sent
            assert "Tell me about momentum." in sent
        finally:
            await stop_core(t.r)

    run(go())


def test_a_role_on_the_devices_own_model_gets_the_stretched_limit() -> None:
    from agent_core.engine.turn import Engine

    deps = SimpleNamespace(settings=SimpleNamespace(local_wall_clock_scale=3.0),
                           router=SimpleNamespace(serves_locally=lambda _role: True))  # fmt: skip
    limits = {"wall_clock_s": 10}
    assert Engine._wall_clock(SimpleNamespace(deps=deps), "checker", limits) == 30.0
    deps.router.serves_locally = lambda _role: False
    assert Engine._wall_clock(SimpleNamespace(deps=deps), "checker", limits) == 10.0
