"""Explicit companion memory operations, including restart durability and truthful acknowledgements."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from w8_companion_harness import reopen, run, stop_core, thread, turn


def test_preference_commands_survive_restart_and_do_not_call_a_model(tmp_path: Path) -> None:
    async def go() -> None:
        t = await thread(tmp_path, {})
        try:
            opened = await t.open()
            await t.say(opened["session_id"], "Remember that I prefer a worked example before practice.")
            conn = t.r.core.records.learner.conn
            assert conn.execute("SELECT value FROM preferences WHERE key = 'start_style'").fetchone() == (
                json.dumps({"override": "worked_example"}, separators=(",", ":")),
            )
            assert t.companion_requests() == []
            snap = await t.snapshot(opened["session_id"])
            assert any("saved" in p.get("text", "").lower() for p in snap["parts"].values())
            t = await reopen(t, {})
            opened = await t.open()
            await t.say(opened["session_id"], "Actually, I prefer a hint first.")
            conn = t.r.core.records.learner.conn
            saved = conn.execute("SELECT value FROM preferences WHERE key = 'start_style'").fetchone()
            assert json.loads(saved[0]) == {"override": "hint"}
            t = await reopen(t, {})
            opened = await t.open()
            await t.say(opened["session_id"], "Forget my preference for a hint first.")
            assert t.r.core.records.learner.conn.execute("SELECT count(*) FROM preferences").fetchone()[0] == 0
            t = await reopen(t, {})
            assert t.r.core.records.learner.conn.execute("SELECT count(*) FROM preferences").fetchone()[0] == 0
        finally:
            await stop_core(t.r)

    run(go())


def test_forgetting_a_note_excludes_earlier_derived_dialogue_from_model_context(tmp_path: Path) -> None:
    from test_w8_companion import _note

    async def go() -> None:
        note = "Mixes up distance and displacement in speed questions"
        t = await thread(tmp_path, {"companion": [turn(note), turn("What would you like to practise?")]})
        try:
            _note(t, note)
            opened = await t.open()
            await t.say(opened["session_id"], "What did I find difficult?")
            await t.say(opened["session_id"], "Forget " + note)
            await t.say(opened["session_id"], "What should I practise?")
            assert note not in json.dumps(t.companion_requests()[-1]["messages"])
            assert (
                t.r.core.records.learner.conn.execute("SELECT count(*) FROM notes WHERE status = 'active'").fetchone()[
                    0
                ]
                == 0
            )
        finally:
            await stop_core(t.r)

    run(go())


def test_model_cannot_claim_a_memory_write_without_the_command_handler() -> None:
    from agent_core.engine.companion import _critic_errors

    assert _critic_errors(None, "I've saved your preference for diagrams.")


def test_explicit_note_has_self_report_evidence_without_fabricated_practice(tmp_path: Path) -> None:
    from memory_harness import note, reflection

    async def go() -> None:
        t = await thread(tmp_path, {}, reflector_idle_delay_s=0)
        t.r.core.attach_reflector(t.r.runtime.reflector())
        try:
            statement = "Benefits from drawing labelled force diagrams"
            t.r.runtime.providers["local"].script["reflector"] = [
                reflection(note(statement, [1], date=t.r.core._today())),
            ]
            opened = await t.open()
            await t.say(opened["session_id"], "Remember that I learn physics better when I sketch the forces first.")

            assert (
                t.r.core.records.learner.conn.execute(
                    "SELECT count(*) FROM events WHERE type = 'memory_requested'"
                ).fetchone()[0]
                == 1
            ), await t.snapshot(opened["session_id"])

            async def settled() -> None:
                while not t.r.core.reflector.outcomes:
                    await asyncio.sleep(0.02)

            await asyncio.wait_for(settled(), 15)
            conn = t.r.core.records.learner.conn
            assert conn.execute("SELECT text FROM notes WHERE status = 'active'").fetchall() == [(statement,)]
            assert conn.execute("SELECT count(*) FROM events WHERE type = 'memory_requested'").fetchone()[0] == 1
            assert (
                conn.execute("SELECT count(*) FROM events WHERE type IN ('attempt','verdict','hint')").fetchone()[0]
                == 0
            )
        finally:
            await stop_core(t.r)

    run(go())


def test_ambiguous_forget_does_not_delete_a_preference(tmp_path: Path) -> None:
    async def go() -> None:
        t = await thread(tmp_path, {})
        try:
            opened = await t.open()
            await t.say(opened["session_id"], "Remember that I prefer short explanations.")
            await t.say(opened["session_id"], "Forget that.")
            assert t.r.core.records.learner.conn.execute("SELECT count(*) FROM preferences").fetchone()[0] == 1
            snap = await t.snapshot(opened["session_id"])
            assert any("which" in p.get("text", "").lower() for p in snap["parts"].values())
            assert t.companion_requests() == []
        finally:
            await stop_core(t.r)

    run(go())


def test_memory_saving_off_does_not_acknowledge_a_save(tmp_path: Path) -> None:
    async def go() -> None:
        t = await thread(tmp_path, {})
        try:
            conn = t.r.core.records.learner.conn
            conn.execute(
                "INSERT OR REPLACE INTO settings (key,value,source,hlc,updated_at)"
                " VALUES ('memory_saving','false','student','0',0)"
            )
            opened = await t.open()
            await t.say(opened["session_id"], "Remember that I prefer short explanations.")
            assert conn.execute("SELECT count(*) FROM preferences").fetchone()[0] == 0
            snap = await t.snapshot(opened["session_id"])
            assert any(
                "saving" in p.get("text", "").lower() and "off" in p.get("text", "").lower()
                for p in snap["parts"].values()
            )
            assert t.companion_requests() == []
        finally:
            await stop_core(t.r)

    run(go())


def test_explicit_note_correction_is_version_pinned_and_student_owned(tmp_path: Path) -> None:
    from memory_harness import note, reflection, wait_for
    from test_w8_companion import _note

    async def go() -> None:
        t = await thread(tmp_path, {}, reflector_idle_delay_s=0)
        t.r.core.attach_reflector(t.r.runtime.reflector())
        try:
            _note(t, "Benefits from drawing force diagrams")
            conn = t.r.core.records.learner.conn
            note_id = conn.execute("SELECT note_id FROM notes WHERE status = 'active'").fetchone()[0]
            replacement = "Prefers explaining forces aloud before sketching"
            t.r.runtime.providers["local"].script["reflector"] = [
                reflection(note(replacement, [1], date=t.r.core._today())),
            ]
            opened = await t.open()
            await t.say(opened["session_id"], f"Correct memory mem_{note_id} to I prefer talking through forces aloud.")
            await wait_for(lambda: bool(t.r.core.reflector.outcomes))
            assert conn.execute("SELECT text FROM notes WHERE status = 'active'").fetchall() == [(replacement,)]
            assert conn.execute(
                "SELECT source FROM events WHERE type = 'note_written' AND erased_at IS NULL"
            ).fetchone() == ("student",)
            assert conn.execute("SELECT count(*) FROM notes WHERE status = 'pending_review'").fetchone()[0] == 0
        finally:
            await stop_core(t.r)

    run(go())


def test_stale_note_correction_cannot_overwrite_or_resurrect() -> None:
    from agent_core.memory.policy import content_hash
    from agent_core.memory.write import NoteAction, apply_reflection, forget
    from memory_harness import CAPTURE, DAY, settings, store

    held = store()
    sid = held.session("A" * 26)
    note_id = held.note("Benefits from drawing force diagrams", sid)
    evidence = held.learner.record("memory_requested", {"request_id": "request-test"}, source="student", session_id=sid)
    action = NoteAction(
        "update", "Prefers explaining forces aloud before sketching", DAY, (evidence.event_id,), target_note_id=note_id
    )
    options = dict(
        session_id=sid, session_date=DAY, summary=None, settings=settings(), role="student_request", capture=CAPTURE
    )
    refused = apply_reflection(held.learner, [action], **options, explicit_correction=(note_id, "stale"))
    assert refused.refused == "correction_changed"
    original = held.conn.execute("SELECT text FROM notes WHERE note_id = ?", (note_id,)).fetchone()[0]
    forget(held.learner, note_id, "student")
    refused = apply_reflection(held.learner, [action], **options, explicit_correction=(note_id, content_hash(original)))
    assert refused.refused == "correction_changed"
    assert held.conn.execute("SELECT count(*) FROM notes WHERE status = 'active'").fetchone()[0] == 0


def test_only_explicit_enum_preferences_can_join_consented_cloud_memory() -> None:
    from agent_core.memory.render import fit_block
    from agent_core.memory.snapshot import freeze
    from agent_core.memory.write import correct_preference
    from memory_harness import CAPTURE, DAY, PACK, settings, store

    held = store()
    correct_preference(held.learner, "start_style", "worked_example", "student")
    snapshot = freeze(held.conn, PACK, settings(), subject="physics", topic_id=None, session_date=DAY)
    plain = fit_block(snapshot, variant="cloud", allowance_chars=4000, settings=settings(), capture=CAPTURE)
    consented = fit_block(snapshot, variant="cloud_notes", allowance_chars=4000, settings=settings(), capture=CAPTURE)
    assert "worked_example" not in plain.text
    assert "worked_example" in consented.text


def test_only_the_current_explicit_request_can_be_used_as_self_report_evidence() -> None:
    from agent_core.config import Settings
    from agent_core.memory.reflect_input import JobKey, build_input
    from agent_core.store.ids import new_ulid
    from memory_harness import store

    held = store()
    sid = held.session("A" * 26)
    old = held.learner.record("memory_requested", {"request_id": new_ulid()}, source="student", session_id=sid)
    new = held.learner.record("memory_requested", {"request_id": new_ulid()}, source="student", session_id=sid)
    automatic = build_input(
        held.conn,
        held.source().content,
        JobKey(held.profile, sid, "idle", new.seq),
        Settings(),
        session_date="2026-10-09",
        subject="physics",
    )
    explicit = build_input(
        held.conn,
        held.source().content,
        JobKey(held.profile, sid, "explicit_request", new.seq),
        Settings(),
        session_date="2026-10-09",
        subject="physics",
        request_text="Remember my current preference",
    )
    assert old.event_id not in automatic.events.ids and new.event_id not in automatic.events.ids
    assert old.event_id not in explicit.events.ids and new.event_id in explicit.events.ids
