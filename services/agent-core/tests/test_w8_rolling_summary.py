"""W8 phase 2 (SPEC §19.5.3, §19.5.4, §19.8): the companion thread's rolling summary is updated, never regenerated,
and written by code only; a replay from the event log reproduces it; a session counts once per topic; entries left
untouched for thirty days leave; a forget never touches it; compaction folds it first and summarises the dialogue;
a stale open episode is ended and reflected on restart; an episode's turns are purged at ninety days.
Every learner, note and message here is synthetic."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agent_core.config import Settings
from agent_core.contracts import errors
from agent_core.engine.companion import CompanionDesk
from agent_core.memory.write import fold_companion_summary
from agent_core.store import retention
from agent_core.store.ids import new_ulid
from memory_harness import PACK, Store, store

SPEED = "kc.phy.o.motion.average_speed"
SOLVE = "kc.phy.o.motion.solve_with_equation"
DAY = 86_400_000


def _desk(held: Store) -> CompanionDesk:
    return CompanionDesk(lambda: held.learner, held.clock, Settings(), content=lambda: PACK)


_SESSIONS: dict[str, str] = {}


def _attempt(held: Store, session: str, kc: str) -> None:
    """One attempt on `kc` in the named synthetic session (each name is one session id)."""
    sid = held.session(_SESSIONS.setdefault(session, new_ulid()))
    held.clock.now += 1000
    held.learner.record(
        "attempt",
        {
            "attempt_id": new_ulid(held.clock.now),
            "session_id": sid,
            "mode": "guided",
            "problem_ref": "prob_1",
            "kc_ids": [{"kc_id": kc, "weight": 1}],
            "kc_source": "pack",
            "attempt_index": 1,
            "response_kind": "typed",
            "time_ms": 1000,
        },
        source="engine",
        session_id=sid,
    )


class _Clock:
    now = 1_792_281_600_000


def _body(held: Store, thread: str) -> dict[str, Any]:
    row = held.conn.execute("SELECT body_json FROM companion_summary WHERE thread_id = ?", (thread,)).fetchone()
    return dict(json.loads(row[0]))


def test_the_fold_updates_sections_in_place_and_advances_the_cursor() -> None:
    held = store()
    desk = _desk(held)
    thread = desk.thread_id()
    _attempt(held, "S1", SPEED)
    first = fold_companion_summary(held.conn, thread, PACK, now_ms=held.clock.now)
    assert [t["kc_id"] for t in first["topics"]] == [SPEED] and first["cursor_seq"] > 0 and first["version"] == 1
    _attempt(held, "S2", SOLVE)
    second = fold_companion_summary(held.conn, thread, PACK, now_ms=held.clock.now)
    assert second["cursor_seq"] > first["cursor_seq"] and second["version"] == 2
    assert {t["kc_id"] for t in second["topics"]} == {SPEED, SOLVE}  # updated in place: the first topic stays
    assert errors("api/commands#/$defs/CompanionSummary", second) == []
    again = fold_companion_summary(held.conn, thread, PACK, now_ms=held.clock.now)
    assert again["cursor_seq"] == second["cursor_seq"] and again["version"] == second["version"]  # nothing new


def test_a_replay_from_the_event_log_reproduces_the_body() -> None:
    held = store()
    thread = _desk(held).thread_id()
    for session, kc in (("S1", SPEED), ("S1", SOLVE), ("S2", SPEED)):
        _attempt(held, session, kc)
        fold_companion_summary(held.conn, thread, PACK, now_ms=held.clock.now)
    folded = _body(held, thread)
    held.conn.execute(
        "UPDATE companion_summary SET cursor_seq = 0, version = 0, body_json = ?",
        (
            json.dumps(
                {
                    "version": 0,
                    "cursor_seq": 0,
                    "updated_at": None,
                    "topics": [],
                    "misconceptions": [],
                    "next_step": None,
                    "episodes": 0,
                }
            ),
        ),
    )
    replayed = fold_companion_summary(held.conn, thread, PACK, now_ms=held.clock.now)
    keys = ("cursor_seq", "topics", "misconceptions", "next_step", "episodes")
    assert {k: replayed[k] for k in keys} == {k: folded[k] for k in keys}


def test_sessions_count_once_per_session_id() -> None:
    held = store()
    thread = _desk(held).thread_id()
    _attempt(held, "S1", SPEED)
    fold_companion_summary(held.conn, thread, PACK, now_ms=held.clock.now)
    _attempt(held, "S1", SPEED)  # the same session, after the cursor: not a second session
    _attempt(held, "S2", SPEED)
    body = fold_companion_summary(held.conn, thread, PACK, now_ms=held.clock.now)
    assert next(t for t in body["topics"] if t["kc_id"] == SPEED)["sessions"] == 2


def test_entries_untouched_for_thirty_days_leave() -> None:
    held = store()
    thread = _desk(held).thread_id()
    _attempt(held, "S1", SPEED)
    fold_companion_summary(held.conn, thread, PACK, now_ms=held.clock.now)
    held.clock.now += 31 * DAY
    _attempt(held, "S2", SOLVE)
    body = fold_companion_summary(held.conn, thread, PACK, now_ms=held.clock.now)
    assert [t["kc_id"] for t in body["topics"]] == [SOLVE]


def test_a_forget_never_touches_the_companion_summary() -> None:
    held = store()
    thread = _desk(held).thread_id()
    note = held.note("Divides distance by time correctly", _SESSIONS.setdefault("S1", new_ulid()))
    _attempt(held, "S1", SPEED)
    fold_companion_summary(held.conn, thread, PACK, now_ms=held.clock.now)
    before = held.conn.execute("SELECT * FROM companion_summary").fetchall()
    from agent_core.memory.write import forget

    forget(held.learner, note, "student")
    assert held.conn.execute("SELECT * FROM companion_summary").fetchall() == before
    assert "Divides distance" not in before[0][4]  # no free text was ever in it


def test_compaction_folds_the_summary_first_and_summarises_the_dialogue(tmp_path: Path) -> None:
    from w8_companion_harness import run, stop_core, thread, turn

    agreements = {"reply": {"model": "qwen3-vl-8b", "choices": [{"message": {"role": "assistant", "content": json.dumps(
        {"agreements": "The student wants to revise motion graphs first."})}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 10}}}  # fmt: skip

    async def go() -> None:
        t = await thread(tmp_path, {"companion": [turn("Let's keep going with graphs.")], "compaction": [agreements]})
        try:
            opened = await t.open()
            entry = t.r.core.sessions[opened["session_id"]]
            learner = t.r.core.records.learner  # type: ignore[union-attr]
            _attempt(Store(learner, _Clock(), "p"), "S1", SPEED)  # type: ignore[arg-type]
            long = "I would like to revise motion graphs and then velocity-time areas. " * 60
            for _ in range(12):  # a long day's dialogue: past the compaction threshold
                entry.engine_state.transcript += [
                    {"role": "user", "content": long, "kind": "companion"},
                    {"role": "assistant", "content": "Sure.", "kind": "companion"},
                ]
            await t.say(opened["session_id"], "Where were we?")
            (request,) = t.companion_requests()
            sent = "\n".join(str(m["content"]) for m in request["messages"])
            assert "<compaction-record>" in sent
            assert (
                "Agreements: Worked on: " in sent and "motion graphs first" in sent
            )  # seeded by code, then summarised
            summary = t.r.core.companion.summary()
            assert summary["cursor_seq"] > 0 and [t_["kc_id"] for t_ in summary["topics"]] == [SPEED]  # folded first
            assert len(entry.engine_state.transcript) >= 24  # compaction changes what is sent, never what is stored
        finally:
            await stop_core(t.r)

    run(go())


def test_a_stale_open_episode_is_ended_and_reflected_on_restart(tmp_path: Path) -> None:
    from w8_companion_harness import reopen, run, stop_core, thread

    async def go() -> None:
        t = await thread(tmp_path, {})
        opened = await t.open()
        conn = t.r.core.records.learner.conn  # type: ignore[union-attr]
        conn.execute("UPDATE companion_episodes SET profile_day = '2026-01-01', opened_at = 0")  # yesterday's, open
        t = await reopen(t, {})
        try:
            t.r.core.attach_reflector(t.r.runtime.reflector())
            triggered: list[tuple[str, str]] = []
            original = t.r.core.reflector.trigger  # type: ignore[union-attr]

            def watched(point: Any, profile: str, session_id: str, **kw: Any) -> bool:
                triggered.append((point, session_id))
                return bool(original(point, profile, session_id, **kw))

            t.r.core.reflector.trigger = watched  # type: ignore[union-attr,method-assign]
            ended = t.r.core.idle_check()  # the first check after the start (as the retention pass's first run)
            assert opened["session_id"] in ended
            conn = t.r.core.records.learner.conn  # type: ignore[union-attr]
            assert conn.execute("SELECT ended_at IS NOT NULL FROM companion_episodes").fetchone() == (1,)
            assert ("session_end", opened["session_id"]) in triggered
            today = await t.open()
            assert today["session_id"] != opened["session_id"] and not today["resumed"]
        finally:
            await stop_core(t.r)

    run(go())


def test_episode_turns_are_purged_at_ninety_days(tmp_path: Path) -> None:
    held = store()
    desk = _desk(held)
    thread_id = desk.thread_id()
    sid = new_ulid(held.clock.now)
    held.conn.execute("INSERT INTO sessions (session_id, mode, started_at, ended_at) VALUES (?, 'study_companion', ?,"
                      " ?)", (sid, held.clock.now, held.clock.now + 1000))  # fmt: skip
    held.conn.execute("INSERT INTO companion_episodes (session_id, thread_id, profile_day, opener_json, opened_at,"
                      " ended_at) VALUES (?, ?, '2026-10-09', '{}', ?, ?)",
                      (sid, thread_id, held.clock.now, held.clock.now + 1000))  # fmt: skip
    held.conn.execute(
        "INSERT INTO turns (turn_id, session_id, idx, speaker, status, student_text, started_at) VALUES"
        " (?, ?, 0, 'student', 'complete', 'how am I doing', ?)",
        (new_ulid(), sid, held.clock.now),
    )
    job = retention.Job(
        held.conn,
        None,
        Settings(),
        held.clock.now + 89 * DAY,
        Path("."),
        held.learner.log,  # type: ignore[arg-type]
        lambda e: None,
    )
    retention._transcripts(job)
    assert held.conn.execute("SELECT count(*) FROM turns").fetchone()[0] == 1  # not yet
    job = retention.Job(
        held.conn,
        None,
        Settings(),
        held.clock.now + 91 * DAY,
        Path("."),
        held.learner.log,  # type: ignore[arg-type]
        lambda e: None,
    )
    retention._transcripts(job)
    assert (
        held.conn.execute("SELECT count(*) FROM turns").fetchone()[0] == 0
    )  # an episode ends daily: purged at 90 days
    assert held.conn.execute("SELECT count(*) FROM companion_episodes").fetchone()[0] == 1  # the row stays
    rules = [r for r in retention.RULES if {"companion_episodes", "companion_summary"} & set(r.tables)]
    assert len(rules) == 2
