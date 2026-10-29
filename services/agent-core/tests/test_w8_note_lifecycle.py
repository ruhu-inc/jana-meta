"""W8 phase 3 (SPEC §19.3.5, §19.5.6, §19.8; JM-D28): a note's standing is derived, never written by a model. It is
`supported` only when the evidence it cites (an update's included) spans two distinct sessions, and `fading` when its
last write and its newest cited evidence are both older than 90 days; fading notes are offered to consolidation first.
Recall counts (`note_recalls`) order notes within the block's allowance and never pin one. Retention and MEM-09 are
unchanged: a note the student asked for is never consolidated away yet still expires, and a contradiction still
creates a pending note beside the original. Every learner and note here is synthetic."""

from __future__ import annotations

import json
from pathlib import Path

from agent_core.config import Settings
from agent_core.contracts import errors
from agent_core.engine.knows import KnowsDesk
from agent_core.engine.memory_session import MemorySource
from agent_core.engine.reflection import CONSOLIDATE
from agent_core.learner.projections import FADING_MS, note_lifecycle
from agent_core.memory.reflect_input import FADING_TAG, JobKey, build_input, clean_note_text
from agent_core.memory.render import fit_block
from agent_core.memory.snapshot import _notes, freeze
from agent_core.store import retention
from agent_core.store.ids import new_ulid
from memory_harness import CAPTURE, PACK
from test_m15e_memory import DAY, PROFILE, SPEED, TOPIC, World, act, world

S = Settings()
DAY_MS = 86_400_000


def _new_session(w: World) -> str:
    """Move the world to a second session of the same profile."""
    w.tick()
    sid = new_ulid(w.clock.now)
    w.conn.execute("INSERT INTO sessions (session_id, mode, subject, topic_id, started_at) VALUES (?, 'practice',"
                   " 'physics', ?, ?)", (sid, TOPIC, w.clock.now))  # fmt: skip
    w.sid = sid
    return sid


def test_confidence_is_derived_from_two_distinct_session_ids() -> None:
    w = world()
    text = "Converts kilometres per hour to metres per second correctly"
    note_id = w.add(text)
    assert note_lifecycle(w.conn, [note_id], w.clock.now)[note_id].confidence == "tentative"
    w.reflect(act("update", text, w.practise(SPEED), target=note_id))  # more evidence, the same session
    assert note_lifecycle(w.conn, [note_id], w.clock.now)[note_id].confidence == "tentative"
    _new_session(w)
    applied = w.reflect(act("update", text + " every time", w.practise(SPEED), target=note_id))
    assert applied.applied == (note_id,)
    # Every write's cited evidence counts: the first session's and the update's.
    cited = set()
    for (payload,) in w.conn.execute("SELECT payload FROM events WHERE type = 'note_written'"):
        cited |= set(json.loads(payload).get("source_event_ids") or [])
    sessions = {r[0] for r in w.conn.execute(
        f"SELECT session_id FROM events WHERE event_id IN ({','.join('?' * len(cited))})", sorted(cited))}  # noqa: S608  # fmt: skip
    assert len(sessions) == 2
    assert note_lifecycle(w.conn, [note_id], w.clock.now)[note_id].confidence == "supported"
    # Carried, derived, in the learner model and on the knows page; nothing stored them.
    [item] = [n for n in _notes(w.conn, w.clock.now) if n["note_id"] == note_id]
    assert (item["confidence"], item["fading"]) == ("supported", False)
    assert errors("learning/learner-model#/$defs/note", item) == []
    view = KnowsDesk(MemorySource(w.learner, PACK, CAPTURE), S).view()
    shown = next(n for n in view["notes"] if n["note_id"].endswith(note_id))
    assert (shown["confidence"], shown["recall_sessions"]) == ("supported", 0)  # fading reads the wall clock
    columns = {r[1] for r in w.conn.execute("PRAGMA table_info(notes)")}
    assert not {"confidence", "fading"} & columns


def test_fading_at_ninety_days_is_derived_and_first_to_consolidate() -> None:
    w = world()
    note_id = w.add("Sets out each quantity with its unit before substituting")
    written = w.clock.now
    assert not note_lifecycle(w.conn, [note_id], written + FADING_MS - 60_000)[note_id].fading
    assert note_lifecycle(w.conn, [note_id], written + FADING_MS + 60_000)[note_id].fading
    assert FADING_MS == 90 * DAY_MS
    # The Reflector's input marks it once the log has moved on 90 days, and consolidation takes fading notes first.
    key = JobKey(PROFILE, w.sid, "session_end", 0)
    fresh = build_input(w.conn, PACK, key, S, session_date=DAY, subject="physics")
    assert FADING_TAG not in fresh.task
    w.clock.now = written + FADING_MS + DAY_MS
    w.practise(SPEED)
    later = build_input(w.conn, PACK, key, S, session_date=DAY, subject="physics")
    assert f"Sets out each quantity with its unit before substituting{FADING_TAG}" in later.task
    assert "(fading) first" in CONSOLIDATE
    # A model echoing the marker into a note's text has it removed.
    assert clean_note_text("[1] 2026-10-09 · Sets out each quantity (fading)") == "Sets out each quantity"
    # New evidence cited by an update ends the fading.
    w.reflect(act("update", "Sets out each quantity with its unit before substituting", w.practise(SPEED),
                  target=note_id))  # fmt: skip
    assert not note_lifecycle(w.conn, [note_id], w.clock.now)[note_id].fading


def test_recall_rows_order_notes_within_the_allowance() -> None:
    w = world()
    ids = [w.add(f"Works through exercise {i} with each quantity and unit named clearly") for i in range(12)]
    frozen = freeze(w.conn, PACK, S, subject="physics", topic_id=TOPIC, session_date=DAY)
    full = fit_block(frozen, variant="local", allowance_chars=100_000, settings=S, capture=CAPTURE)
    budget = len(full.text) - 300  # a few index lines must go
    plain = fit_block(frozen, variant="local", allowance_chars=budget, settings=S, capture=CAPTURE)
    oldest = ids[0]  # the oldest note: the first index line cut without recall counts
    assert oldest not in plain.shown_note_ids
    recalled = fit_block(frozen, variant="local", allowance_chars=budget, settings=S, capture=CAPTURE,
                         recalls={oldest: 3})  # fmt: skip
    assert oldest in recalled.shown_note_ids, "a note recalled in more sessions is kept before older ones"
    assert len(recalled.shown_note_ids) == len(plain.shown_note_ids), "the allowance is the same: a bounded priority"
    assert len(recalled.text) <= budget
    # Never pinned: with no room for index lines, even the most recalled one goes.
    tight = fit_block(frozen, variant="local", allowance_chars=len(full.text.split("<learner-notes>")[0]) + 10,
                      settings=S, capture=CAPTURE, recalls={i: 9 for i in ids})  # fmt: skip
    assert oldest not in tight.shown_note_ids
    # The render records which notes it carried, one row per note, session and day; a forget removes them.
    from agent_core.memory.recall import recall_sessions, record_recalls
    from agent_core.memory.write import forget

    record_recalls(w.conn, [oldest], "ses_" + w.sid, DAY)
    record_recalls(w.conn, [oldest], "ses_" + w.sid, DAY)
    record_recalls(w.conn, [oldest], new_ulid(), DAY)
    assert recall_sessions(w.conn)[oldest] == 2
    forget(w.learner, oldest, "student")
    assert oldest not in recall_sessions(w.conn)


def test_student_request_notes_are_never_consolidated_away_but_still_expire(tmp_path: Path) -> None:
    w = world()
    owned = w.add("Asked to keep practising projectile questions", role="student_request")
    other = w.add("Checks the sign of each acceleration before substituting")
    applied = w.reflect(consolidation=[act("drop", "", w.practise(SPEED), target=owned),
                                       act("drop", "", w.practise(SPEED), target=other)])  # fmt: skip
    status = dict(w.conn.execute("SELECT note_id, status FROM notes").fetchall())
    assert status[owned] == "active", "consolidation never drops a note the student asked for (MEM-09)"
    assert applied is not None
    # Fading changes nothing about retention: the owned note still expires at retention_note_days from creation.
    created = w.conn.execute("SELECT created_at FROM notes WHERE note_id = ?", (owned,)).fetchone()[0]
    job = retention.Job(w.conn, None, S, created + int(S.retention_note_days * DAY_MS) + 1, Path("."),
                        w.learner.log, w.learner.projector.apply)  # type: ignore[arg-type]  # fmt: skip
    retention._notes(job)
    assert w.conn.execute("SELECT status FROM notes WHERE note_id = ?", (owned,)).fetchone()[0] == "deleted"


def test_contradiction_still_creates_a_pending_note() -> None:
    w = world()
    old = w.add("Converts kilometres per hour to metres per second correctly")
    _new_session(w)
    applied = w.reflect(act("contradiction", "Divides by 36 instead of 3.6 when converting speeds",
                            w.practise(SPEED), target=old))  # fmt: skip
    assert applied.applied == () and len(applied.pending_review) == 1
    pending = applied.pending_review[0]
    status = dict(w.conn.execute("SELECT note_id, status FROM notes").fetchall())
    assert status == {old: "active", pending: "pending_review"}
    # Its standing is derived like any note's; nothing a model returned set it.
    derived = note_lifecycle(w.conn, [old, pending], w.clock.now)
    assert derived[old].confidence == "tentative" and derived[pending].confidence == "tentative"
