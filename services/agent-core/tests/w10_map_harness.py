"""The W10 learner's map tests' world (SPEC §21): the real core with development-signed Physics and Maths packs, a
clock the test moves (the learner's event clock, the API's and the map's), and a synthetic learner "Ada" whose
practice, mastery checks, Study activity, materials, recordings, cards, notes and tutor summary are written through
the same paths the app uses where one exists (learning events through `Learner.record`), and as the Study desk
stores them where the test needs a Study row. Every learner, title and note here is invented test data."""

from __future__ import annotations

import contextlib
import json
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent_core.engine.study_session import _payload
from agent_core.learner.mastery import DAY_MS
from agent_core.memory.write import NOTES_WRITER
from agent_core.store.sqlite import transaction
from agent_core.trace.ids import new_ulid
from api_harness import Running, start_core, stop_core
from test_m13g_learn import SETTINGS, Client, install

V_T = "kc.phy.o.motion.velocity_time_gradient"
SPEED = "kc.phy.o.motion.average_speed"
DISTANCE = "kc.phy.o.motion.distance_or_displacement"
AREA = "kc.phy.o.motion.velocity_time_area"
FREE_FALL = "kc.phy.o.motion.free_fall"
MOTION = "cur.phy.o.motion_forces_and_energy.motion"
SINGLE_POINT = "mc.phy.o.vt_gradient_from_one_point"
# Words that tag a text to the v-t gradient skill: the topic's title phrase and the skill's own statement words.
ABOUT_V_T = "Motion in a straight line: find acceleration from the gradient of a velocity-time graph"
CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def ident(prefix: str, n: int) -> str:
    """A `<prefix>_` id with 26 Crockford characters, numbered so a test reads it back."""
    body = ""
    for _ in range(26):
        body = CROCKFORD[n % 32] + body
        n //= 32
    return f"{prefix}_{body}"


@dataclass
class World:
    r: Running
    c: Client
    now: int

    @property
    def learner(self) -> Any:
        return self.r.runtime.learner

    @property
    def conn(self) -> Any:
        return self.r.runtime.learner.conn

    @property
    def device(self) -> Any:
        return self.r.runtime.stores.device

    def at(self, ms: int) -> None:
        """Move every clock to `ms` (forward only: the event log's hybrid clock never goes back)."""
        self.now = max(self.now, ms)

    def days(self, n: float) -> None:
        self.at(self.now + int(n * DAY_MS))

    def record(self, type_: str, payload: dict[str, Any], **envelope: Any) -> Any:
        return self.learner.record(type_, payload, **envelope)

    def practise(self, kc: str, outcome: str = "correct", times: int = 1) -> list[Any]:
        """A guided session with `times` closed opportunities on `kc`: attempts and the verdicts that close them."""
        sid = new_ulid(self.now)
        stored = [
            self.record(
                "session_started",
                {"session_id": sid, "mode": "guided", "entry": "question", "hardware_class": "mid"},
                source="engine",
                session_id=sid,
            )
        ]
        for n in range(times):
            attempt = new_ulid(self.now)
            stored.append(
                self.record(
                    "attempt",
                    {
                        "attempt_id": attempt,
                        "session_id": sid,
                        "mode": "guided",
                        "item_id": f"itm.phy.o.motion.{n:04d}",
                        "problem_ref": f"prob_{n}",
                        "step_index": 0,
                        "kc_ids": [{"kc_id": kc, "weight": 1.0}],
                        "kc_source": "pack",
                        "attempt_index": 1,
                        "response_kind": "typed",
                        "normalised_response": "2 m/s^2",
                        "time_ms": 20_000,
                    },
                    source="student",
                    session_id=sid,
                )
            )
            stored.append(
                self.record(
                    "verdict",
                    {
                        "verdict_id": new_ulid(self.now),
                        "attempt_id": attempt,
                        "outcome": outcome,
                        "check_ids": ["chk_0000000a"],
                        "closes_opportunity": True,
                        "marker_version": "numeric.1",
                    },
                    source="checker",
                    session_id=sid,
                )
            )
        stored.append(
            self.record(
                "session_ended",
                {"session_id": sid, "reason": "completed", "active_ms": 60_000},
                source="engine",
                session_id=sid,
            )
        )
        return stored

    def secure(self, kc: str) -> None:
        """Practice then a passed mastery check: the skill is Secure with a review card."""
        self.practise(kc, times=4)
        for item in (1, 2, 3):
            self.record(
                "mastery_check",
                {
                    "kc_id": kc,
                    "item_index": item,
                    "attempt_id": new_ulid(self.now),
                    "item_result": "pass",
                    "check_state": "passed" if item == 3 else "in_progress",
                },
                source="checker",
            )

    def study(self, kc: str, ref: str, activity: str = "quiz_item", **fields: Any) -> Any:
        """A Study activity tagged to `kc` (never mastery evidence)."""
        payload = _payload(activity, ref, [{"kc_id": kc, "weight": 1.0}], **fields)
        return self.record("study_activity", payload, source="engine")

    def note(self, text: str, cites: list[Any]) -> str:
        note_id = new_ulid(self.now)
        self.learner.record(
            "note_written",
            {
                "note_id": note_id,
                "text": text,
                "status": "active",
                "subject": "physics",
                "source_event_ids": [e.event_id for e in cites],
            },
            source="reflector",
            writer=NOTES_WRITER,
        )
        return f"mem_{note_id}" if not note_id.startswith("mem_") else note_id

    # --- Study rows, as the Study desk stores them ---------------------------------------------------------

    def source(self, n: int, kind: str, title: str, chunks: list[tuple[int, str]] = ()) -> str:
        sid = ident("src", n)
        body = {
            "source_id": sid,
            "revision": 1,
            "kind": kind,
            "title": title,
            "state": "ready",
            "created_at": "x",
            "updated_at": "x",
            "private": False,
            "readable_units": len(chunks),
            "unreadable_units": [],
            "sha256": "0" * 64,
        }
        with transaction(self.conn):
            self.conn.execute(
                "INSERT INTO study_sources VALUES (?,?,?,?,?,?)", (sid, 1, 0, json.dumps(body), self.now, self.now)
            )
            self.conn.execute("INSERT INTO study_revisions VALUES (?,?,?,?,?,?)", (sid, 1, "0" * 64, None, 0, self.now))
            for i, (start, text) in enumerate(chunks):
                chunk = {
                    "chunk_id": ident("sck", n * 100 + i),
                    "source_id": sid,
                    "revision": 1,
                    "ordinal": i,
                    "locator": {"kind": "time", "start_ms": start, "end_ms": start + 30_000},
                    "text": text,
                    "sha256": "0" * 64,
                }
                self.conn.execute(
                    "INSERT INTO study_chunks VALUES (?,?,?,?,?)", (chunk["chunk_id"], sid, 1, i, json.dumps(chunk))
                )
        return sid

    def aid(self, n: int, kind: str, title: str, source_id: str) -> str:
        aid_id = ident("aid", n)
        body = {
            "aid_id": aid_id,
            "job_id": ident("job", n),
            "kind": kind,
            "title": title,
            "status": "ready",
            "sources": [{"source_id": source_id, "revision": 1}],
            "claims": [],
            "created_at": "x",
        }
        with transaction(self.conn):
            self.conn.execute("INSERT INTO study_aids VALUES (?,?,?)", (aid_id, json.dumps(body), self.now))
        return aid_id

    def deck(self, n: int, aid_id: str, source_id: str, cards: list[str]) -> None:
        with transaction(self.conn):
            self.conn.execute(
                "INSERT INTO study_decks VALUES (?,?,?,?,?)", (ident("dck", n), aid_id, source_id, 1, "fsrs")
            )
            for card in cards:
                self.conn.execute(
                    "INSERT INTO study_flashcards VALUES (?,?,?,?,?,?)",
                    (card, ident("dck", n), 1, "{}", "{}", self.now + 365 * DAY_MS),
                )

    def review(self, card: str, due_ms: int, n: int) -> None:
        from agent_core.store.events import iso_ms

        with transaction(self.conn):
            self.conn.execute(
                "INSERT INTO study_reviews VALUES (?,?,?,?)",
                (ident("rvw", n), card, json.dumps({"due_at": iso_ms(due_ms)}), self.now),
            )

    def summary(self, kcs: list[str]) -> None:
        from agent_core.store.events import iso_ms

        topics = [{"kc_id": k, "label": k, "sessions": 1, "last_at": iso_ms(self.now)} for k in kcs]
        body = {
            "version": 1,
            "cursor_seq": 0,
            "updated_at": None,
            "topics": topics,
            "misconceptions": [],
            "next_step": None,
            "episodes": [],
        }
        with transaction(self.conn):
            self.conn.execute(
                "INSERT OR REPLACE INTO companion_summary VALUES (?,?,?,?,?)",
                ("cth_" + "0" * 26, 1, 0, self.now, json.dumps(body)),
            )

    def misconception(self, mc_id: str, kc_id: str, status: str, count: int = 2) -> None:
        with transaction(self.conn):
            self.conn.execute(
                "INSERT OR REPLACE INTO learner_misconceptions (misconception_id, kc_id, status,"
                " evidence_count, first_seen_at, last_seen_at, last_event_seq) VALUES (?,?,?,?,?,?,0)",
                (mc_id, kc_id, status, count, self.now, self.now),
            )

    # --- reads ---------------------------------------------------------------------------------------------

    async def map(self, subject: str = "phy", as_of: str | None = None) -> dict[str, Any]:
        query = f"?as_of={as_of}" if as_of else ""
        return await self.c.ok("GET", f"/v1/curriculum/cur.{subject}.o/concept-map{query}", definition="ConceptMap")

    async def overview(self) -> dict[str, Any]:
        return await self.c.ok("GET", "/v1/curriculum/overview", definition="CurriculumOverview")

    async def links(self, kc: str) -> dict[str, Any]:
        return await self.c.ok("GET", f"/v1/curriculum/kcs/{kc}/links", definition="KcLinks")

    def new_visit(self) -> None:
        """The app restarted: the next live read takes the stored bands as its baseline."""
        self.r.runtime._map_states.clear()

    def events(self) -> int:
        return int(self.conn.execute("SELECT count(*) FROM events").fetchone()[0])


def node(reply: dict[str, Any], kc: str) -> dict[str, Any]:
    return next(n for n in reply["nodes"] if n["kc_id"] == kc)


@contextlib.asynccontextmanager
async def world(tmp: Path) -> AsyncIterator[World]:
    install(tmp, "phy")
    install(tmp, "mth")
    r = await start_core(tmp, settings=SETTINGS, worker=False)
    # A day after the real clock, so every clock only moves forward from what the profile's setup stamped.
    w = World(r, Client(r), int(time.time() * 1000) + DAY_MS)
    r.core.clock_ms = lambda: w.now
    r.runtime.learner.log.clock.wall_ms = lambda: w.now
    try:
        yield w
    finally:
        await stop_core(r)
