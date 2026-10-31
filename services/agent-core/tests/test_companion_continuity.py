"""Thread history remains readable offline and supplies bounded local context across daily episodes."""

from __future__ import annotations

import json
from pathlib import Path

from api_harness import ask
from w8_companion_harness import reopen, run, stop_core, thread, turn


def test_returning_learner_reads_history_offline_and_continues_next_day(tmp_path: Path) -> None:
    async def go() -> None:
        t = await thread(tmp_path, {"companion": [turn("We can revisit your momentum example next time.")]})
        try:
            opened = await t.open()
            await t.say(opened["session_id"], "Next time, can we revisit my momentum example?")
            first_day = t.r.core.companion.clock()
            t = await reopen(t, {"companion": [turn("Let's return to that example.")]})
            t.r.core.companion.clock = lambda: first_day + 86_400_000
            t.r.core.tutor_unavailable = lambda: True
            returned = await t.open()
            assert returned["thread_id"] == opened["thread_id"]
            assert returned["session_id"] != opened["session_id"]
            assert returned["can_reply"] is False
            history = await t.api.call("GET", "/v1/companion/history?limit=1", profile=t.token)
            assert history.status_code == 200, history.text
            first = history.json()
            assert len(first["items"]) == 1 and first["next_cursor"]
            older = await t.api.call(
                "GET", "/v1/companion/history?limit=1&before=" + first["next_cursor"], profile=t.token
            )
            assert older.status_code == 200
            assert older.json()["items"][0]["text"] == "Next time, can we revisit my momentum example?"
            denied = await t.api.call(
                "POST", f"/v1/sessions/{returned['session_id']}/turns", ask("Continue"), profile=t.token
            )
            assert denied.json()["error"]["code"] == "model_unavailable"
            await t.say(returned["session_id"], "Remember that I prefer short explanations.")
            t.r.core.tutor_unavailable = lambda: False
            await t.say(returned["session_id"], "Can we continue our example?")
            assert "momentum example" in json.dumps(t.companion_requests()[-1]["messages"])
        finally:
            await stop_core(t.r)

    run(go())


def test_bounded_history_preserves_more_than_twenty_four_messages_and_obeys_forget() -> None:
    from agent_core.engine.companion_history import context_rows, public_page, record_context
    from agent_core.memory.visibility import advance
    from agent_core.store.sqlite import transaction
    from memory_harness import store

    held = store()
    sid = held.session("A" * 26)
    held.conn.execute(
        "INSERT INTO companion_episodes VALUES (?, ?, '2026-10-09', '{}', 1, NULL, NULL)", (sid, "cth_" + "A" * 26)
    )
    for i in range(30):
        held.conn.execute(
            "INSERT INTO turns (turn_id,session_id,idx,speaker,status,student_text,started_at)"
            " VALUES (?,?,?,'student','complete',?,?)",
            (str(i), sid, i, f"example {i}", i),
        )
        record_context(held.conn, str(i), "companion", {})
    assert len(context_rows(held.conn, "ses_" + sid)) == 30
    latest = public_page(held.conn, limit=7)
    older = public_page(held.conn, limit=7, before=latest["next_cursor"])
    assert not {x["id"] for x in latest["items"]} & {x["id"] for x in older["items"]}
    with transaction(held.conn):
        advance(held.conn, held.clock.now)
    assert context_rows(held.conn, "ses_" + sid) == []
    assert len(public_page(held.conn)["items"]) == 30  # visible history is not recalled memory
    held.conn.execute("DELETE FROM turns WHERE session_id = ?", (sid,))
    assert public_page(held.conn)["items"] == []
    assert held.conn.execute("SELECT count(*) FROM companion_turn_context").fetchone()[0] == 0


def test_restored_episode_can_continue_without_a_runtime_checkpoint(tmp_path: Path) -> None:
    async def go() -> None:
        t = await thread(tmp_path, {"companion": [turn("We can use your momentum example."), turn("Let us continue.")]})
        try:
            opened = await t.open()
            await t.say(opened["session_id"], "Use my momentum example next time.")
            # Imports keep the authorized transcript, but never an executable engine checkpoint.
            t.r.core.sessions.pop(opened["session_id"])
            returned = await t.open()
            assert returned["session_id"] == opened["session_id"]
            await t.say(returned["session_id"], "Continue our example.")
            assert "momentum example" in json.dumps(t.companion_requests()[-1]["messages"])
        finally:
            await stop_core(t.r)

    run(go())


def test_current_episode_history_preserves_local_only_provenance_for_learner_text() -> None:
    from agent_core.engine.companion_history import context_rows, record_context
    from memory_harness import store

    held = store()
    sid = held.session("A" * 26)
    held.conn.execute(
        "INSERT INTO companion_episodes VALUES (?, ?, '2026-10-09', '{}', 1, NULL, NULL)", (sid, "cth_" + "A" * 26)
    )
    held.conn.execute(
        "INSERT INTO turns (turn_id,session_id,idx,speaker,status,student_text,started_at)"
        " VALUES ('local',?,0,'student','complete','A private restored agreement',1)",
        (sid,),
    )
    record_context(held.conn, "local", "companion", {"local_only": True})
    rows = context_rows(held.conn, "ses_" + sid)
    assert len(rows) == 1
    assert rows[0]["companion_egress"] == {"local_only": True}


def test_forward_migration_preserves_old_transcripts_and_adds_provenance(tmp_path: Path) -> None:
    from agent_core.store.sqlite import MIGRATIONS, open_database

    path = tmp_path / "learner.db"
    old, _ = open_database(path, "learner", [m for m in MIGRATIONS["learner"] if m.version <= 21])
    old.execute("INSERT INTO sessions(session_id,mode,started_at) VALUES ('old','study_companion',1)")
    old.close()
    upgraded, applied = open_database(path, "learner")
    assert [step.version for step in applied] == [22, 23]  # v23 (W9, SPEC §20.3) follows; the transcript stays
    assert upgraded.execute("SELECT session_id FROM sessions").fetchall() == [("old",)]
    fresh, _ = open_database(tmp_path / "fresh.db", "learner")
    query = "SELECT sql FROM sqlite_schema WHERE name='companion_turn_context'"
    assert fresh.execute(query).fetchone() == upgraded.execute(query).fetchone()
    upgraded.close()
    fresh.close()


def test_audit_retention_never_removes_the_latest_forget_boundary(tmp_path: Path) -> None:
    from agent_core.memory.visibility import advance, revision
    from agent_core.store.sqlite import transaction
    from test_m10d_retention import FAR, B, World

    world = World(tmp_path)
    with transaction(world.L):
        advance(world.L, B)
        advance(world.L, B + 1)
    latest = revision(world.L)
    world.run(FAR)
    assert revision(world.L) == latest
    assert world.L.execute("SELECT count(*) FROM audit_log WHERE action='memory_context_changed'").fetchone()[0] == 1


def test_clock_rollback_cannot_weaken_the_retained_forget_cutoff(tmp_path: Path) -> None:
    from agent_core.memory.visibility import advance, cutoff, revision
    from agent_core.store.sqlite import transaction
    from test_m10d_retention import FAR, B, World

    world = World(tmp_path)
    with transaction(world.L):
        advance(world.L, B + 1000)
        advance(world.L, B)  # a later edit after a device clock correction
    latest = revision(world.L)
    world.run(FAR)
    assert revision(world.L) == latest
    assert cutoff(world.L) == B + 1000


def test_first_forget_after_clock_rollback_excludes_all_existing_dialogue() -> None:
    from agent_core.memory.queries import session_history
    from agent_core.memory.visibility import advance
    from agent_core.store.sqlite import transaction
    from memory_harness import store

    held = store()
    sid = held.session("A" * 26)
    held.conn.execute(
        "INSERT INTO turns (turn_id,session_id,idx,speaker,status,student_text,started_at)"
        " VALUES ('future',?,0,'student','complete','Forget this old private preference',?)",
        (sid, held.clock.now + 1000),
    )
    with transaction(held.conn):
        advance(held.conn, held.clock.now)
    assert session_history(held.conn, "ses_" + sid) == []
