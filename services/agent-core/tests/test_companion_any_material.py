"""The tutor on a learner's own material, whatever the subject (rehearsal of 4 November 2026): a list's numbers are not
claims, a good reply that asks twice keeps its last question, and a question never starts a study tool. Every learner,
material and reply here is synthetic."""

from __future__ import annotations

import json
from pathlib import Path

from agent_core.engine.companion import fact_binding_findings, keep_last_question, without_list_numbers
from test_w8_companion import MOTION
from w8_companion_harness import calls, run, stop_core, thread, turn


def test_a_numbered_list_is_not_a_claim() -> None:
    listed = "1. Classical pairs a signal with a reflex.\n2. Operant follows a consequence."
    assert without_list_numbers(listed) == "Classical pairs a signal with a reflex.\nOperant follows a consequence."
    assert fact_binding_findings(listed, []) == []


def test_a_number_that_is_not_a_list_still_has_to_bind() -> None:
    assert fact_binding_findings("12. Review today.", []) == [("12", "none")]
    assert fact_binding_findings("2. First.\n3. Second.", []) != []
    assert fact_binding_findings("1. First.\n3. Second.", []) != []
    assert fact_binding_findings("There are 2 kinds here.", []) == [("2", "none")]


def test_a_number_word_in_plain_english_is_not_a_claim() -> None:
    assert fact_binding_findings("These are two kinds of learning. Which one fits your dog?", []) == []
    assert fact_binding_findings("You have two cards due.", []) == [("2", "card")]
    assert fact_binding_findings("Your exam is in nineteen days.", []) == [("19", "day")]
    assert fact_binding_findings("It peaks at seventy degrees.", []) == [("70", "none")]


def test_keep_last_question_keeps_the_words_and_one_question() -> None:
    assert keep_last_question("Why? Because of the treat. What comes next?") == "Because of the treat. What comes next?"
    assert keep_last_question("It follows a consequence.") == "It follows a consequence."


def test_a_reply_that_asks_twice_twice_is_trimmed_not_refused(tmp_path: Path) -> None:
    twice = turn("The behaviour comes first. Is that clear? What follows it?")
    script = {"companion": [twice, twice]}

    async def go() -> None:
        t = await thread(tmp_path, script)
        try:
            opened = await t.open()
            await t.say(opened["session_id"], "Why is that operant conditioning?")
            said = json.dumps(await t.snapshot(opened["session_id"]))
            assert "The behaviour comes first. What follows it?" in said
            assert "couldn't put that together" not in said
        finally:
            await stop_core(t.r)

    run(go())


def test_a_question_does_not_start_a_study_tool(tmp_path: Path) -> None:
    script = {
        "companion": [calls(("make_aid", {"kind": "summary"})), turn("It follows a consequence. What comes next?")]
    }

    async def go() -> None:
        t = await thread(tmp_path, script)
        try:
            t.r.core.study.desk().create({"kind": "text", "title": "Lecture", "text": MOTION})
            opened = await t.open()
            await t.say(opened["session_id"], "Help me understand operant conditioning from this lecture.")
            conn = t.r.core.records.learner.conn  # type: ignore[union-attr]
            assert [r for r in conn.execute("SELECT body FROM study_jobs") if "summary" in r[0]] == []
            assert "It follows a consequence" in json.dumps(await t.snapshot(opened["session_id"]))
        finally:
            await stop_core(t.r)

    run(go())


def test_a_number_in_a_material_title_is_the_learners_own(tmp_path: Path) -> None:
    script = {"companion": [turn("Your MIT 9.00 lecture says a consequence follows. What comes next?")]}

    async def go() -> None:
        t = await thread(tmp_path, script)
        try:
            t.r.core.study.desk().create({"kind": "text", "title": "MIT 9.00 Lecture", "text": MOTION})
            opened = await t.open()
            await t.say(opened["session_id"], "Why is that operant conditioning?")
            said = json.dumps(await t.snapshot(opened["session_id"]))
            assert "Your MIT 9.00 lecture says" in said
            assert "couldn't put that together" not in said
        finally:
            await stop_core(t.r)

    run(go())


def test_the_role_helps_with_any_subject_in_their_materials() -> None:
    role = Path(__file__).parents[3].joinpath("content/agent/roles/companion.md").read_text()
    assert "never say a subject is not supported" in role
