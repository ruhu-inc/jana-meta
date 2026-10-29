"""W8 phase 1 (SPEC §19.3.2, §19.4, §19.8): Study writes activity, not mastery. A Study quiz submission records one
`study_activity` per item after Study's own transaction, a repeat records nothing, the mastery, review and
misconception tables do not move, a card review and an aid are recorded at their own seams, the Study screen's
session opens once a day and ends at close or when idle, and its end queues one Reflector job whose evidence lines
name pack labels only. Every learner, source and answer here is synthetic."""

from __future__ import annotations

import asyncio
import json
import random
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agent_core.config import Settings
from agent_core.contracts import errors
from agent_core.engine.knows import KnowsDesk
from agent_core.engine.memory_session import MemorySource
from agent_core.engine.plans import PlanDesk
from agent_core.engine.reflection import ReflectorQueue, window_cursor
from agent_core.engine.study import SCHEDULER, StudyDesk, StudyQueue, atomic
from agent_core.engine.study_session import STUDY_IDLE_MS, StudyVisits
from agent_core.engine.study_topics import kc_tags
from agent_core.learner.mastery import MasteryParams
from agent_core.learner.service import Learner
from agent_core.memory.reflect_input import JobKey, build_input
from agent_core.store.generated.schema import LEARNER
from agent_core.store.sqlite import MIGRATIONS, connect, open_database, statements
from learner_harness import Clock, Session
from memory_harness import CAPTURE, PACK, PROFILE_A, at_ms

SOLVE = "kc.phy.o.motion.solve_with_equation"
TITLE = "Kinematics notes SECRET-TITLE"
TEXT = (
    "Motion in a straight line\n\nFor motion in a straight line with uniform acceleration, the equation v = u + at "
    "is used to solve for the final velocity.\n\nAverage speed is the total distance divided by the total time."
)
ATTEMPT = "sqa_" + "0" * 26


def _span(chunk: dict[str, Any], text: str) -> dict[str, Any]:
    quote = chunk["text"][:40]
    return {
        "text": text,
        "citations": [
            {
                "source_id": chunk["source_id"],
                "revision": chunk["revision"],
                "chunk_id": chunk["chunk_id"],
                "start": 0,
                "end": len(quote),
                "quote": quote,
            }
        ],
    }


class PhysicsModel:
    """A scripted local Study model: a three-question quiz on uniform acceleration, or two flashcards."""

    async def local_ready(self) -> bool:
        return True

    async def study_generate(self, identity: str, request: dict[str, Any], chunks: list[dict[str, Any]]):
        c = chunks[0]
        out: dict[str, Any] = {
            "request_id": identity,
            "kind": request["kind"],
            "claims": [_span(c, "The source links v, u, a and t.")],
        }
        if request["kind"] == "quiz":
            out["quiz"] = {
                "items": [
                    {
                        "item_id": "a",
                        "type": "choice",
                        "stem": _span(
                            c,
                            "For motion in a straight line, which equation of uniform acceleration do you "
                            "use to solve for the final velocity?",
                        ),
                        "options": [{"option_id": "x", "text": "v = u + at"}, {"option_id": "y", "text": "s = d / t"}],
                    },
                    {"item_id": "b", "type": "true_false", "stem": _span(c, "Average speed is distance over time.")},
                    {"item_id": "c", "type": "true_false", "stem": _span(c, "Acceleration has units of m/s.")},
                ],
                "keys": [
                    {
                        "item_id": "a",
                        "answer": "x",
                        "marking": "judged",
                        "explanation": _span(c, "Solve with the equation of uniform acceleration v = u + at."),
                    },
                    {"item_id": "b", "answer": "true", "marking": "judged", "explanation": _span(c, "It is.")},
                    {"item_id": "c", "answer": "false", "marking": "judged", "explanation": _span(c, "m/s².")},
                ],
            }
        if request["kind"] == "flashcards":
            out["flashcards"] = [
                {
                    "front": _span(c, "In motion in a straight line, which equation gives the final velocity?"),
                    "back": _span(c, "Solve with v = u + at, an equation of uniform acceleration."),
                },
                {"front": _span(c, "What is average speed?"), "back": _span(c, "Total distance over total time.")},
            ]
        return out, True

    async def study_support(self, request: Any, chunks: Any, output: dict[str, Any]):
        n = len(output["claims"]) + len(output.get("flashcards", [])) + len(output.get("quiz", {}).get("items", []))
        return [True] * n, True


@dataclass
class World:
    """One profile's learner database (migrated, v19) with the Study desk, its queue and the Study session."""

    conn: sqlite3.Connection
    clock: Clock
    learner: Learner
    visits: StudyVisits
    desk: StudyDesk
    queue: StudyQueue
    source: dict[str, Any]
    ended: list[tuple[str, str | None, str]] = field(default_factory=list)

    def make(self, kind: str) -> dict[str, Any]:
        job = self.desk.create_job(
            {
                "kind": kind,
                "execution": "local",
                "count": 3,
                "sources": [{"source_id": self.source["source_id"], "revision": 1}],
            }
        )
        asyncio.run(self.queue.run(self.desk, job["job_id"]))
        done = self.desk.job(job["job_id"])
        assert done["state"] == "completed", done
        return self.desk.aid(done["result_ids"][0])

    def activity(self) -> list[dict[str, Any]]:
        rows = self.conn.execute("SELECT payload, session_id FROM events WHERE type = 'study_activity' ORDER BY seq")
        return [{**json.loads(p), "_session": s} for p, s in rows]


def world(tmp_path: Path, day: str = "2026-11-04") -> World:
    conn, _ = open_database(tmp_path / "learner.db", "learner")
    clock = Clock(at_ms(day))
    conn.execute("INSERT INTO meta VALUES (1, ?, 19, ?, 'test', ?, 'test')", (PROFILE_A, clock.now, clock.now))
    conn.execute(
        "INSERT INTO profile (profile_id, display_name, avatar, age_band, level, subjects, exam_date, created_at,"
        " updated_at) VALUES (?, 'Ada', 'disc-teal', '18_plus', 'O', '[\"physics\"]', '2026-11-23', ?, ?)",
        (PROFILE_A, clock.now, clock.now),
    )
    learner = Learner.open(
        conn,
        profile_id=PROFILE_A,
        device_id="d" * 32,
        wall_ms=clock,
        max_skew_ms=86_400_000,
        params=MasteryParams(),
        content=PACK,
    )
    settings = Settings(study_workspace_enabled=True, study_offline_enabled=True)
    ended: list[tuple[str, str | None, str]] = []
    visits = StudyVisits(lambda: learner, clock, settings, content=lambda: PACK, on_end=lambda *a: ended.append(a))
    desk = StudyDesk(conn, clock, settings)
    desk.activity = visits
    queue = StudyQueue(lambda: conn, lambda: PhysicsModel(), lambda: False, clock, settings)
    queue.activity = visits
    source = desk.create({"kind": "text", "title": TITLE, "text": TEXT})
    return World(conn, clock, learner, visits, desk, queue, source, ended)


def _tables(conn: sqlite3.Connection) -> dict[str, list[tuple[Any, ...]]]:
    return {
        t: conn.execute(f"SELECT * FROM {t} ORDER BY 1").fetchall()  # noqa: S608 - fixed names
        for t in ("kc_mastery", "review_cards", "learner_misconceptions", "subject_ability")
    }


def _answers(w: World, quiz: dict[str, Any]) -> list[dict[str, str]]:
    items = w.desk.quiz(quiz["quiz_id"])["view"]["items"]
    # The first is missed (the wrong equation), the second right, the third left unanswered.
    return [{"item_id": items[0]["item_id"], "answer": "y"}, {"item_id": items[1]["item_id"], "answer": "true"}]


# --- the activity seams (§19.4 study.py) --------------------------------------------------------------------------


def test_a_submission_records_one_activity_per_item_after_the_study_transaction(tmp_path: Path) -> None:
    w = world(tmp_path)
    w.visits.open()
    quiz = w.make("quiz")
    seen: list[tuple[bool, int]] = []
    record = w.learner.record_batch

    def watched(events: Any, **kw: Any) -> Any:
        if any(e.type == "study_activity" and e.payload["activity"] == "quiz_item" for e in events):
            attempts = w.conn.execute("SELECT count(*) FROM study_attempts").fetchone()[0]
            seen.append((w.conn.in_transaction, attempts))
        return record(events, **kw)

    w.learner.record_batch = watched  # type: ignore[method-assign]
    w.desk.submit(quiz["quiz_id"], {"attempt_id": ATTEMPT, "quiz_revision": 1, "answers": _answers(w, quiz)})
    # One write, after Study's own transaction committed (the attempt is already stored, no transaction is open).
    assert seen == [(False, 1)]
    items = [a for a in w.activity() if a["activity"] == "quiz_item"]
    assert [a["ref"] for a in items] == [f"att:{ATTEMPT}:{i}" for i in range(3)]
    assert [a["outcome"] for a in items] == ["incorrect", "correct", "skipped"]
    assert {a["_session"] for a in items} == {w.visits.session_id.removeprefix("ses_")}  # type: ignore[union-attr]
    assert items[0]["kc_tags"][0]["kc_id"] == SOLVE  # topic-derived: the stem names "motion in a straight line"
    for event in w.conn.execute("SELECT payload FROM events WHERE type = 'study_activity'"):
        assert TITLE not in event[0] and "v = u + at" not in event[0] and "s = d / t" not in event[0]
    assert not w.conn.execute("SELECT 1 FROM events WHERE type IN ('attempt', 'verdict', 'review')").fetchone()


def test_a_repeat_submission_records_nothing(tmp_path: Path) -> None:
    w = world(tmp_path)
    quiz = w.make("quiz")
    body = {"attempt_id": ATTEMPT, "quiz_revision": 1, "answers": _answers(w, quiz)}
    first = w.desk.submit(quiz["quiz_id"], body)
    count = len(w.activity())
    assert w.desk.submit(quiz["quiz_id"], body) == first and len(w.activity()) == count
    # The queue's own submit delegates to the desk and records nothing of its own (one seam).
    assert asyncio.run(w.queue.submit_quiz(quiz["quiz_id"], body)) == first and len(w.activity()) == count
    # Even a ref already in the log asked for again (a retry after a crash) records nothing.
    assert w.visits.quiz(ATTEMPT, [(0, "anything", "correct")]) == 0


def test_a_preliminary_check_records_nothing(tmp_path: Path) -> None:
    w = world(tmp_path)
    quiz = w.make("quiz")
    before = len(w.activity())
    w.desk.submit(
        quiz["quiz_id"],
        {"attempt_id": ATTEMPT, "quiz_revision": 1, "answers": _answers(w, quiz), "submission_kind": "check"},
    )
    assert len(w.activity()) == before


def test_an_omitted_answer_is_skipped(tmp_path: Path) -> None:
    w = world(tmp_path)
    quiz = w.make("quiz")
    w.desk.submit(quiz["quiz_id"], {"attempt_id": ATTEMPT, "quiz_revision": 1, "answers": []})
    items = [a for a in w.activity() if a["activity"] == "quiz_item"]
    assert [a["outcome"] for a in items] == ["skipped", "skipped", "skipped"]


def test_kc_tags_weights_sum_to_one_and_cap_at_three() -> None:
    text = (
        "Motion in a straight line: solve with an equation of uniform acceleration. Mass and weight: how mass "
        "differs from weight. Momentum and collisions."
    )
    tags = kc_tags(PACK, text)
    assert 1 <= len(tags) <= 3
    assert abs(sum(t["weight"] for t in tags) - 1) < 1e-9 and all(t["weight"] > 0 for t in tags)
    assert all(re.match(r"^kc\.(mth|phy|chm|bio|acc)\.(o|a)\.[a-z0-9_]+\.[a-z0-9_]+$", t["kc_id"]) for t in tags)
    one = kc_tags(PACK, "For motion in a straight line, solve for v with an equation of uniform acceleration.")
    assert one[0]["kc_id"] == SOLVE and abs(sum(t["weight"] for t in one) - 1) < 1e-9
    assert kc_tags(PACK, "Enzymes are biological catalysts.") == []  # no pack topic named: no tag
    assert kc_tags(None, text) == [] and kc_tags(PACK, "  ") == []


def test_mastery_review_and_misconception_tables_are_unchanged_by_study_activity(tmp_path: Path) -> None:
    w = world(tmp_path)
    Session(random.Random(3), w.learner, w.clock).run(3)  # real tutoring evidence first, so the tables hold rows
    before = _tables(w.conn)
    assert before["kc_mastery"] and before["review_cards"]
    quiz = w.make("quiz")
    deck = w.make("flashcards")
    w.desk.submit(quiz["quiz_id"], {"attempt_id": ATTEMPT, "quiz_revision": 1, "answers": _answers(w, quiz)})
    card = next(c for c in w.desk.deck(deck["deck_id"])["cards"] if "straight line" in c["front"]["text"])
    w.desk.review(
        deck["deck_id"],
        {
            "client_review_id": "srv_" + "1" * 26,
            "card_id": card["card_id"],
            "card_revision": 1,
            "rating": "again",
            "revealed": True,
        },
    )
    w.visits.end("student_left")
    assert len(w.activity()) >= 5
    assert _tables(w.conn) == before  # byte-identical: Study activity is not evidence (JM-D26)
    w.learner.projector.replay_all(w.learner.projector.projections)  # and a replay of the whole log agrees
    assert _tables(w.conn) == before


def test_a_card_review_records_an_activity_and_keeps_the_study_scheduler(tmp_path: Path) -> None:
    w = world(tmp_path)
    deck = w.make("flashcards")
    card = next(c for c in w.desk.deck(deck["deck_id"])["cards"] if "straight line" in c["front"]["text"])
    cards_before = w.conn.execute("SELECT * FROM review_cards").fetchall()
    body = {
        "client_review_id": "srv_" + "2" * 26,
        "card_id": card["card_id"],
        "card_revision": 1,
        "rating": "hard",
        "revealed": True,
    }
    # Inside a command's transaction (the API's), the activity waits for the commit: never a nested write.
    with atomic(w.conn):
        result = w.desk.review(deck["deck_id"], body)
        assert not [a for a in w.activity() if a["activity"] == "card_review"]
    w.visits.flush()
    reviews = [a for a in w.activity() if a["activity"] == "card_review"]
    assert len(reviews) == 1 and reviews[0]["ref"] == f"card:{card['card_id']}" and reviews[0]["rating"] == "hard"
    assert reviews[0]["kc_tags"] and reviews[0]["kc_tags"][0]["kc_id"] == SOLVE
    # Study's own scheduler moved the card; the learner model's review cards did not.
    assert result["scheduler"] == SCHEDULER
    stored = json.loads(
        w.conn.execute("SELECT schedule FROM study_flashcards WHERE card_id = ?", (card["card_id"],)).fetchone()[0]
    )
    assert stored["reps"] == 1 and stored["last_review_at"] is not None
    assert w.conn.execute("SELECT * FROM review_cards").fetchall() == cards_before


def test_aid_made_is_recorded_at_completion_not_at_create_job(tmp_path: Path) -> None:
    w = world(tmp_path)
    w.visits.open()
    job = w.desk.create_job(
        {
            "kind": "quiz",
            "execution": "local",
            "count": 3,
            "sources": [{"source_id": w.source["source_id"], "revision": 1}],
        }
    )
    assert not w.activity(), "creating a job records nothing"
    asyncio.run(w.queue.run(w.desk, job["job_id"]))
    made = [a for a in w.activity() if a["activity"] == "aid_made"]
    aid_id = w.desk.job(job["job_id"])["result_ids"][0]
    assert [(a["ref"], a["aid_kind"], a["count"]) for a in made] == [(f"aid:{aid_id}", "quiz", 3)]
    # With the Study screen closed, an aid that finishes is recorded by the next open, at the time it was made.
    w.visits.end("student_left")
    w.clock.now += 60_000
    deck = w.make("flashcards")
    made_at = w.conn.execute("SELECT created_at FROM study_aids WHERE aid_id = ?", (deck["aid_id"],)).fetchone()[0]
    assert len([a for a in w.activity() if a["activity"] == "aid_made"]) == 1
    w.clock.now += 60_000
    w.visits.open()
    row = w.conn.execute(
        "SELECT occurred_at, payload FROM events WHERE type = 'study_activity' AND json_extract(payload, '$.ref') = ?",
        (f"aid:{deck['aid_id']}",),
    ).fetchone()
    assert row is not None and row[0] == made_at and json.loads(row[1])["count"] == 2


def test_a_study_session_opens_once_per_day_and_ends_on_idle(tmp_path: Path) -> None:
    w = world(tmp_path)
    first, resumed = w.visits.open()
    assert not resumed and w.visits.open() == (first, True)
    w.clock.now += STUDY_IDLE_MS - 1
    assert w.visits.idle_check() is None  # not yet
    last = w.clock.now
    w.visits.touch()  # a Study command keeps it open
    w.clock.now += STUDY_IDLE_MS
    assert w.visits.idle_check() == first
    row = w.conn.execute(
        "SELECT mode, ended_at, end_reason FROM sessions WHERE session_id = ?", (first.removeprefix("ses_"),)
    ).fetchone()
    assert row == ("study", last, "idle_timeout")  # ended at its last activity
    assert w.ended == [(first, None, "2026-11-04")]  # the study_end write point
    # The same day reopens the same row (a new learning session in it); the next day is a new one.
    assert w.visits.open() == (first, True)
    w.clock.now += 86_400_000
    second, resumed = w.visits.open()
    assert second != first and not resumed
    assert w.conn.execute("SELECT count(*) FROM sessions WHERE mode = 'study'").fetchone()[0] == 2
    started = w.conn.execute("SELECT payload FROM events WHERE type = 'session_started'").fetchall()
    assert [json.loads(p)["mode"] for (p,) in started] == ["study"] * 3


def test_study_end_queues_one_reflector_job(tmp_path: Path) -> None:
    w = world(tmp_path)
    queue = ReflectorQueue(
        Settings(),
        model=lambda: None,
        executor=None,  # type: ignore[arg-type]
        source=lambda: MemorySource(w.learner, PACK, CAPTURE),
    )
    w.visits.on_end = lambda sid, subject, day: (
        w.ended.append((sid, subject, day))
        or queue.trigger("study_end", "prf_test", sid, session_date=day, subject=subject)
    )
    quiz = w.make("quiz")
    w.visits.open()
    w.desk.submit(quiz["quiz_id"], {"attempt_id": ATTEMPT, "quiz_revision": 1, "answers": _answers(w, quiz)})
    sid = w.visits.end("student_left")
    assert sid is not None and len(queue.pending) == 1
    job = queue.pending[0]
    assert (job.key.point, job.key.session_id, job.subject) == ("study_end", sid.removeprefix("ses_"), "physics")
    # The same window queued again is the same job: nothing more.
    assert not queue.trigger("study_end", "prf_test", sid, session_date="2026-11-04", subject="physics")
    assert len(queue.pending) == 1


def test_reflector_lines_for_study_name_pack_labels_never_titles(tmp_path: Path) -> None:
    w = world(tmp_path)
    w.visits.open()
    quiz = w.make("quiz")
    w.desk.submit(quiz["quiz_id"], {"attempt_id": ATTEMPT, "quiz_revision": 1, "answers": _answers(w, quiz)})
    sid = w.visits.end("student_left")
    assert sid is not None
    key = JobKey(PROFILE_A, sid.removeprefix("ses_"), "study_end", window_cursor(w.conn, sid))
    given = build_input(w.conn, PACK, key, Settings(), session_date="2026-11-04", subject="physics")
    statement = PACK.kc_statement(SOLVE)
    assert f"study quiz: {statement}, incorrect" in given.task
    assert "study aid: quiz (3)" in given.task
    assert "the end of a visit to Study" in given.task
    assert "Notes kept: 0 of 50 notes; subject 0 of 40." in given.task
    for private in (TITLE, "SECRET", "v = u + at", "s = d / t", "Average speed is distance", w.source["source_id"]):
        assert private not in given.task, private


def test_study_activity_shows_on_progress_and_the_knows_page(tmp_path: Path) -> None:
    w = world(tmp_path)
    w.visits.open()
    quiz = w.make("quiz")
    w.desk.submit(quiz["quiz_id"], {"attempt_id": ATTEMPT, "quiz_revision": 1, "answers": _answers(w, quiz)})
    progress = PlanDesk(w.learner, PACK, Settings(), clock_ms=w.clock).progress()
    assert progress["study_activity"] == {"quiz_items": 2, "quiz_correct": 1, "cards_reviewed": 0, "aids_made": 1}
    assert errors("api/commands#/$defs/ProgressView", progress) == []
    view = KnowsDesk(MemorySource(w.learner, PACK, CAPTURE), Settings()).view()
    kinds = [a["activity"] for a in view["activity"]]
    assert sorted(kinds) == ["aid_made", "quiz_item", "quiz_item", "quiz_item"]
    missed = next(a for a in view["activity"] if a["activity"] == "quiz_item" and a["result"] == "incorrect")
    assert missed["statement"] == PACK.kc_statement(SOLVE) and missed["day"] == "2026-11-04"
    assert TITLE not in json.dumps(view["activity"])


# --- storage: the v19 migration (§19.3, DAT-12) ------------------------------------------------------------------


def _shape(conn: sqlite3.Connection, tables: set[str] | None = None) -> dict[str, object]:
    """A database's schema as data: per table its columns, foreign keys and CHECK enums, then indexes and triggers.
    Stored definitions differ in whitespace between a migrated and a fresh file; their meaning must not."""
    out: dict[str, object] = {}
    for name, sql in conn.execute(
        "SELECT name, sql FROM sqlite_schema WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ):
        if tables is not None and name not in tables:
            continue
        columns = [r[1:6] for r in conn.execute(f'PRAGMA table_xinfo("{name}")')]
        keys = sorted(r[2:] for r in conn.execute(f'PRAGMA foreign_key_list("{name}")'))
        checks = sorted(
            (m.group(1), tuple(sorted(re.findall(r"'([^']*)'", m.group(2)))))
            for m in re.finditer(r"(\w+)\s+IN\s*\(([^)]*)\)", sql or "")
        )
        out[name] = (columns, keys, checks)
    out["indexes"] = sorted(
        (n, t)
        for n, t in conn.execute("SELECT name, tbl_name FROM sqlite_schema WHERE type = 'index'")
        if not n.startswith("sqlite_") and (tables is None or t in tables)
    )
    out["triggers"] = sorted(
        (n, t)
        for n, t in conn.execute("SELECT name, tbl_name FROM sqlite_schema WHERE type = 'trigger'")
        if tables is None or t in tables
    )
    return out


def test_v18_profile_upgrades_to_v19_and_matches_a_fresh_schema(tmp_path: Path) -> None:
    path = tmp_path / "learner.db"
    v18 = tuple(m for m in MIGRATIONS["learner"] if m.version <= 18)
    conn, _ = open_database(path, "learner", v18)
    conn.execute("INSERT INTO sessions (session_id, mode, subject, started_at) VALUES ('S1', 'guided', 'physics', 1)")
    conn.execute(
        "INSERT INTO turns (turn_id, session_id, idx, speaker, status, student_text, started_at)"
        " VALUES ('T1', 'S1', 0, 'student', 'complete', 'synthetic', 1)"
    )
    conn.close()

    upgraded, applied = open_database(path, "learner")
    assert next(a.version for a in applied) == 19  # then any later ones (v20: the companion, phase 2)
    assert applied[0].backup_file == "learner.db.pre-v18.bak"  # the copy is kept until the next good open
    # Nothing that referenced the session went with the change: the turn is still there and still its child.
    assert upgraded.execute("SELECT session_id FROM turns").fetchall() == [("S1",)]
    assert [r[2] for r in upgraded.execute("PRAGMA foreign_key_list(turns)")] == ["sessions"]
    for mode in ("study", "study_companion"):
        upgraded.execute("INSERT INTO sessions (session_id, mode, started_at) VALUES (?, ?, 2)", (f"S_{mode}", mode))
    try:
        upgraded.execute("INSERT INTO sessions (session_id, mode, started_at) VALUES ('S_bad', 'chat', 3)")
        raise AssertionError("the CHECK still refuses an unknown mode")
    except sqlite3.IntegrityError:
        pass
    assert upgraded.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    assert upgraded.execute("PRAGMA foreign_key_check").fetchall() == []
    # A second connection reads the widened definition too (the schema version moved with the edit).
    other = connect(path)
    other.execute("INSERT INTO sessions (session_id, mode, started_at) VALUES ('S_other', 'study', 4)")
    other.close()

    fresh, _ = open_database(tmp_path / "fresh.db", "learner")
    assert _shape(upgraded) == _shape(fresh)
    # Every table the storage contract defines reads the same in the upgraded file as in the contract's own script.
    contract = connect(":memory:")
    for statement in statements(LEARNER):
        contract.execute(statement)
    defined = {r[0] for r in contract.execute("SELECT name FROM sqlite_schema WHERE type = 'table'")}
    assert _shape(upgraded, defined) == _shape(contract, defined)
    checks = dict(_shape(upgraded, {"sessions"})["sessions"][2])  # type: ignore[index]
    assert {"study", "study_companion"} <= set(checks["mode"])
    upgraded.close()
    fresh.close()


def test_the_study_routes_open_and_end_the_session_and_queue_study_end(tmp_path: Path) -> None:
    """The Study screen's open (POST /v1/study/session) opens the day's session once; its close (DELETE) ends it and
    queues the study_end Reflector job, through the app's own core."""
    from memory_harness import core_with_reflector
    from test_m10a_profiles import Api, student

    async def scenario() -> None:
        r = await core_with_reflector(tmp_path, None, worker=False, study_workspace_enabled=True)
        try:
            calls: list[tuple[str, str]] = []
            trigger = r.core.reflector.trigger  # type: ignore[union-attr]

            def watched(point: Any, profile: str, session_id: str, **kw: Any) -> bool:
                calls.append((point, session_id))
                return trigger(point, profile, session_id, **kw)

            r.core.reflector.trigger = watched  # type: ignore[union-attr,method-assign]
            api = Api(r)
            token = (await api.unlock(await api.add(student("Ada")))).json()["profile_token"]
            opened = await api.call("POST", "/v1/study/session", {}, profile=token)
            assert opened.status_code == 200, opened.text
            assert errors("api/commands#/$defs/StudyVisit", opened.json()) == [] and not opened.json()["resumed"]
            again = await api.call("POST", "/v1/study/session", {}, profile=token)
            assert again.json() == {"session_id": opened.json()["session_id"], "resumed": True}
            closed = await api.call("DELETE", "/v1/study/session", profile=token)
            assert closed.status_code == 204
            assert calls == [("study_end", opened.json()["session_id"])]
            conn = r.core.records.learner.conn  # type: ignore[union-attr]
            row = conn.execute(
                "SELECT mode, end_reason FROM sessions WHERE session_id = ?",
                (opened.json()["session_id"].removeprefix("ses_"),),
            ).fetchone()
            assert row == ("study", "student_left")
            # Session history lists tutoring sessions only: a Study visit has no conversation to read back.
            from agent_core.engine.history import HistoryDesk

            assert HistoryDesk(conn, None, 90).list()["sessions"] == []
        finally:
            from api_harness import stop_core

            await stop_core(r)

    asyncio.run(scenario())
