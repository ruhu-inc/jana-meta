"""The memory toolset's host handlers (TOL-23, MEM-05, MEM-08, MEM-18, LRN-04).

Each session binds the four handlers to its own profile (`MemoryAccess`): a read or write against a learner database
that is not the session's profile's is refused, so a session never sees another student's rows.

- `memory_recall` (Coach): one of the five fixed queries with integer refs, checked against the refs the Coach was
  shown; live values, a records-not-instructions marker, note text escaped and re-checked (MEM-27).
- `session_recall` (Coach): a literal search of this session's stored transcript (MEM-18).
- `memory_note` (Reflector only, applied by the engine): one Reflection's notes, refs mapped back with the job's ref
  tables; any ref outside them fails the whole call (MEM-08). A model is never offered it; a Coach call is refused
  by the register's grants before it gets here (`policy_denied`).
- `progress_update` (engine only): after a verdict is committed, which band each KC is in and which way it moved.
  It reads; it writes nothing.

Every refusal is `invalid_args` with a message that names the rule, never the student's text. `items_read` gives the
number of records a read returned, from which the engine's memory-use line is made (MEM-28).
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from agent_core.config import Settings
from agent_core.engine.memory_session import SessionMemory
from agent_core.learner.service import Learner
from agent_core.memory.capture import CaptureFilter
from agent_core.memory.recall import (
    RECALL_MARKER,
    QueryId,
    RecallRefused,
    memory_recall,
    session_recall,
    session_recall_past,
)
from agent_core.memory.reflect_input import ReflectionInvalid, ReflectorInput, actions_from_reflection
from agent_core.memory.refs import RefOutOfRange, RefTable
from agent_core.memory.render import BANDS, escape_note
from agent_core.memory.write import Applied, NoteAction, WriterRole, apply_reflection, summary_text
from agent_core.tools.spec import CallContext, InvalidArguments

READ_TOOLS = frozenset({"memory_recall", "session_recall"})
MEMORY_TOOLS = frozenset({*READ_TOOLS, "memory_note", "progress_update"})
OFF_PROFILE = "this session can read only its own student's records"


def items_read(name: str, data: Any) -> int | None:
    """How many records a completed memory read returned (MEM-28), from the handler's own result; None for any other
    tool."""
    if name not in READ_TOOLS or not isinstance(data, dict):
        return None
    if name == "memory_recall":
        count = data.get("count")
        return count if type(count) is int and count >= 0 else 0
    found = data.get("matches")
    return len(found) if isinstance(found, list) else 0


@dataclass
class NoteJob:
    """One Reflector job's context for `memory_note`: the ref tables the Reflector was shown, and where and how its
    notes are applied. `applied` holds the outcome once the call ran."""

    learner: Learner
    given: ReflectorInput
    session_id: str
    subject: str | None
    role: WriterRole
    capture: CaptureFilter | None
    fallback_summary: str | None = None
    consolidation: Sequence[NoteAction] = ()
    student_texts: Collection[str] = ()
    forgotten_hashes: Collection[str] = ()  # notes deleted after the job's input was built (never written back)
    also: Callable[[sqlite3.Connection], object] | None = None
    now_ms: int | None = None
    applied: Applied | None = None


def apply_notes(job: NoteJob, args: dict[str, Any], settings: Settings) -> dict[str, Any]:
    """`memory_note` for one Reflection: refs mapped back, then one atomic apply (AGT-26). A ref outside the lists
    shown, or a malformed action, fails the whole call and nothing is applied (MEM-08)."""
    try:
        actions = actions_from_reflection({"notes": args.get("actions") or []}, job.given, subject=job.subject)
    except (RefOutOfRange, ReflectionInvalid) as error:
        raise InvalidArguments(f"{type(error).__name__}: {error}") from None
    summary = summary_text(args.get("summary"), job.capture) if job.capture is not None else None
    applied = apply_reflection(job.learner, actions, session_id=job.session_id, session_date=job.given.session_date,
                               summary=summary or job.fallback_summary, settings=settings, role=job.role,
                               capture=job.capture, consolidation=job.consolidation, student_texts=job.student_texts,
                               forgotten_hashes=job.forgotten_hashes, now_ms=job.now_ms, also=job.also)  # fmt: skip
    job.applied = applied
    return {"applied": len(applied.applied), "blocked": applied.blocked,
            "rejected": [r.code for r in applied.rejected], "pending_review": len(applied.pending_review),
            "dropped": len(applied.dropped), "expired": len(applied.expired), "over_bound": applied.over_bound,
            "summary_stored": applied.summary_stored, "refused": applied.refused}  # fmt: skip


@dataclass
class MemoryTools:
    """The handlers of one session, bound to its memory and profile."""

    memory: SessionMemory
    settings: Settings
    cloud: Callable[[], bool]  # the call is served by a cloud candidate: memory_recall is never answered (MEM-13)
    job: NoteJob | None = None  # set only while the engine applies a Reflection
    reads: list[int] = field(default_factory=list)  # records returned per read, in order (evidence for tests)

    def bind(self, executors: dict[str, Any]) -> None:
        executors.update({"memory_recall": self.recall, "session_recall": self.search, "memory_note": self.note,
                          "progress_update": self.progress})  # fmt: skip

    def _conn(self) -> tuple[sqlite3.Connection, Any]:
        source = self.memory.source()
        if source is None:
            raise InvalidArguments(OFF_PROFILE)
        return source.conn, source

    async def recall(self, args: dict[str, Any], context: CallContext) -> dict[str, Any]:
        online = self.cloud() and self.memory.memory_online()  # SPEC §19.6: under tutor_memory_online, scrubbed
        if self.cloud() and not online:
            raise InvalidArguments("notes are not read for a cloud model")
        conn, source = self._conn()
        frozen = self.memory.frozen
        try:
            result = memory_recall(conn, source.content, cast(QueryId, args["query_id"]), args.get("refs") or [],
                                   self.memory.refs, self.settings, subject=_subject(context.session.subject),
                                   topic_id=self.memory.topic,
                                   session_date=frozen.session_date if frozen else None,
                                   expect_profile=self.memory.access.profile_id,
                                   capture=source.capture,
                                   egress_terms=tuple(self.memory.terms()) if online else None,
                                   recalled_in=(self.memory.session_id, frozen.session_date) if frozen else None,
                                   )  # fmt: skip
        except RecallRefused as refused:
            raise InvalidArguments(str(refused)) from None
        out = result.as_tool_result()
        self.reads.append(len(result.items))
        return out

    async def search(self, args: dict[str, Any], context: CallContext) -> dict[str, Any]:
        conn, _ = self._conn()
        if args.get("scope") == "past":
            # SPEC §19.6: past-conversation excerpts never ride a cloud call, whatever the consents.
            if self.cloud():
                raise InvalidArguments("past conversations are searched only on this computer's own model")
            try:
                past = session_recall_past(conn, context.session.session_id, str(args["pattern"]), self.settings,
                                           int(args.get("limit") or 8))  # fmt: skip
            except RecallRefused as refused:
                raise InvalidArguments(str(refused)) from None
            self.reads.append(len(past))
            return {"marker": RECALL_MARKER, "matches": [{"date": m.session_date, "subject": m.subject,
                                                          "from": m.source, "text": m.text} for m in past]}  # fmt: skip
        try:
            found = session_recall(conn, context.session.session_id, str(args["pattern"]), self.settings)
        except RecallRefused as refused:
            raise InvalidArguments(str(refused)) from None
        self.reads.append(len(found))
        return {"marker": RECALL_MARKER, "matches": [{"turn": m.turn_ref, "from": m.source, "text": m.text}
                                                     for m in found]}  # fmt: skip

    async def note(self, args: dict[str, Any], context: CallContext) -> dict[str, Any]:
        if self.job is None:
            raise InvalidArguments("there is no Reflection to apply")
        if self.job.learner.log.profile_id != self.memory.access.profile_id:
            raise InvalidArguments(OFF_PROFILE)
        return apply_notes(self.job, args, self.settings)

    async def progress(self, args: dict[str, Any], context: CallContext) -> dict[str, Any]:
        conn, _ = self._conn()
        return progress_of(conn, str(args["attempt_id"]), list(args["kc_ids"]), self.memory.progress_seen)


def progress_of(
    conn: sqlite3.Connection, attempt_id: str, kc_ids: Sequence[str], before: dict[str, float]
) -> dict[str, Any]:
    """Band and direction per KC after a committed verdict (LRN-04: read only). The attempt must have a verdict in
    this student's log; the direction compares the KC's probability now with the one taken before the verdict."""
    checked = conn.execute(
        "SELECT 1 FROM events WHERE type = 'verdict' AND erased_at IS NULL"
        " AND json_extract(payload, '$.attempt_id') = ?",
        (attempt_id,),
    ).fetchone()
    if checked is None:
        raise InvalidArguments("that attempt has no committed verdict")
    out = []
    for kc in dict.fromkeys(kc_ids):
        row = conn.execute("SELECT status, p_mastery FROM kc_mastery WHERE kc_id = ?", (kc,)).fetchone()
        status, p = (str(row[0]), float(row[1])) if row is not None else ("not_started", -1.0)
        earlier = before.get(kc)
        direction = "same" if earlier is None or abs(p - earlier) < 1e-9 else "up" if p > earlier else "down"
        out.append({"kc_id": kc, "mastery_band": BANDS.get(status, "not_started"), "direction": direction})
    return {"attempt_id": attempt_id, "kcs": out}


def _subject(subject: str) -> str | None:
    return subject if subject in ("mathematics", "physics", "chemistry", "biology", "accounting") else None


# --- the companion's study toolset (SPEC §19.3.3, W8 phase 2) --------------------------------------------------


@dataclass
class StudyTools:
    """`study_search`, `progress_read`, `plan`, `make_aid` and `start_research`, bound to the session's profile
    through its `MemoryAccess` as the four memory handlers are. Every result is a records-not-instructions list with
    per-call integer refs (`RefTable`), never a stored id; a ref the model returns is resolved here. Granted to the
    `companion` role only (the register's roleGrants)."""

    memory: SessionMemory
    settings: Settings
    cloud: Callable[[], bool]  # the call is served by a cloud candidate
    share: Callable[[], bool] = lambda: False  # `study_materials` effective (§19.6): study_search on a cloud call
    planner: Callable[[], Any] = lambda: None  # the plan desk of the open learner database
    make_job: Callable[[dict[str, Any]], dict[str, Any]] | None = None  # the Study desk's create_job, then a poll
    clock: Callable[[], int] = lambda: 0
    refs: dict[int, tuple[str, str, int]] = field(default_factory=dict)  # this turn's study_search refs
    bands: dict[int, str] = field(default_factory=dict)  # this turn's progress_read refs -> KC ids

    def bind(self, executors: dict[str, Any]) -> None:
        executors.update({"study_search": self.search, "progress_read": self.progress, "plan": self.plan,
                          "make_aid": self.make_aid, "start_research": self.start_research})  # fmt: skip

    def new_turn(self) -> None:
        self.refs, self.bands = {}, {}

    def _conn(self) -> tuple[sqlite3.Connection, Any]:
        source = self.memory.source()
        if source is None:
            raise InvalidArguments(OFF_PROFILE)
        return source.conn, source

    def _items(self, found: Sequence[Any]) -> list[dict[str, Any]]:
        table = RefTable.of(f"{e.kind}:{e.record_id}:{e.revision}" for e in found)
        items = []
        for excerpt in found:
            key = f"{excerpt.kind}:{excerpt.record_id}:{excerpt.revision}"
            ref = len(self.refs) + table.ref_of(key)
            self.refs[ref] = (excerpt.kind, excerpt.record_id, excerpt.revision)
            items.append({"ref": ref, "source_label": escape_note(excerpt.label), "text": escape_note(excerpt.text)})
        return items

    def search_text(self, text: str) -> list[dict[str, Any]]:
        """Recall by code before the call (§19.5.1 step 3): the learner's own excerpts matching the message's words,
        with refs this turn's `make_aid` can name."""
        from agent_core.engine.ask_anything import own_evidence
        from agent_core.memory.queries import StudyExcerpt

        conn, _ = self._conn()
        found = [StudyExcerpt("source", str(e["source_id"]), self._revision(conn, str(e["source_id"])),
                              str(e.get("title", "")), str(e["text"]))
                 for e in own_evidence(conn, text, 3) if e.get("kind") == "own_source"]  # fmt: skip
        return self._items(found)

    @staticmethod
    def _revision(conn: sqlite3.Connection, source_id: str) -> int:
        row = conn.execute("SELECT current_revision FROM study_sources WHERE source_id = ?", (source_id,)).fetchone()
        return int(row[0]) if row else 1

    async def search(self, args: dict[str, Any], context: CallContext) -> dict[str, Any]:
        if self.cloud() and not self.share():
            raise InvalidArguments("the learner's materials are not searched for an online model without Study online")
        from agent_core.memory.queries import study_excerpts
        from agent_core.memory.recall import _segments

        query = str(args["query"])
        if len(query) > 200:
            raise InvalidArguments("the query is at most 200 characters")
        segments = _segments(query)
        if not segments or all(not piece.strip() for piece in segments):
            raise InvalidArguments("the query has no text to look for")
        conn, _ = self._conn()
        items = self._items(study_excerpts(conn, segments))
        return {"marker": RECALL_MARKER, "items": items}

    async def progress(self, args: dict[str, Any], context: CallContext) -> dict[str, Any]:
        from agent_core.memory.queries import progress_overview

        conn, source = self._conn()
        now = self.clock()
        today = datetime.fromtimestamp(now / 1000, UTC).date()
        end = int(datetime.combine(today + timedelta(days=1), datetime.min.time(), UTC).timestamp() * 1000)
        overview = progress_overview(conn, source.content, self.settings, today.isoformat(), end)
        bands = []
        for ref, (kc, statement, band) in enumerate(overview.bands, start=1):
            self.bands[ref] = kc
            bands.append({"ref": ref, "skill": escape_note(statement), "band": band})
        return {"marker": RECALL_MARKER, "bands": bands,
                "due": {"learner_cards": overview.learner_cards, "study_cards": overview.study_cards},
                "exam_distance_days": overview.exam_distance_days, "streak_days": overview.streak_days}  # fmt: skip

    async def plan(self, args: dict[str, Any], context: CallContext) -> dict[str, Any]:
        desk = self.planner()
        if desk is None:
            raise InvalidArguments("there is no plan on this computer yet")
        current = desk.current()
        return {"marker": RECALL_MARKER, "plan": current.get("plan") if isinstance(current, dict) else current}

    async def make_aid(self, args: dict[str, Any], context: CallContext) -> dict[str, Any]:
        kind = str(args["kind"])
        ref = args.get("source_ref")
        found = self.refs.get(ref) if type(ref) is int else None
        if found is None or found[0] != "source":
            raise InvalidArguments("source_ref must be a source's number from a study_search result of this turn")
        if self.make_job is None:
            raise InvalidArguments("Study is not available on this computer")
        execution = "local" if self.settings.study_offline_enabled else "prefer_cloud"
        body: dict[str, Any] = {"kind": kind, "execution": execution,
                                "sources": [{"source_id": found[1], "revision": found[2]}]}  # fmt: skip
        if args.get("count") is not None:
            body["count"] = int(args["count"])
        try:
            job = self.make_job(body)
        except ValueError as error:
            raise InvalidArguments(f"Study refused it: {getattr(error, 'reason', 'invalid_study_request')}") from None
        return {"job_id": job["job_id"], "action": {"action": "open_study_job", "payload": {"job_id": job["job_id"]}}}

    async def start_research(self, args: dict[str, Any], context: CallContext) -> dict[str, Any]:
        topic = " ".join(str(args["topic"]).split())[:200]
        if not topic:
            raise InvalidArguments("the topic is empty")
        # Never a research job from here: the research conversation opens with the topic (§18.1a still asks).
        return {"action": {"action": "open_research", "payload": {"question": topic}}}
