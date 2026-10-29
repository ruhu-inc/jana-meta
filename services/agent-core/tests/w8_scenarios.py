"""The W8 Study-memory scenarios (SPEC §19.9): the `companion` suite in evals/suites.toml.

The memory harness loads tutoring-session fixtures and cannot run these, so each case is a YAML file under
`tests/scenarios/w8/` with its rubric written before any run, and this loader runs it against the real engine pieces
(the Study desk and queue, the Study session, the opener, the research conversation) with scripted models, then
checks the rubric by code. `run(case, tmp)` returns the rubric's failures: an empty list is a pass."""

from __future__ import annotations

import asyncio
import json
import random
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml
from agent_core.config import Settings
from agent_core.engine.companion_opener import OpenerDesk
from agent_core.engine.research_chat import Start, learner_profile, next_turn
from jana_tools import REPO_ROOT

CASES = Path(__file__).parent / "scenarios" / "w8"
PERSONAS = REPO_ROOT / "evals" / "memory" / "personas.yaml"


def cases() -> list[dict[str, Any]]:
    return [yaml.safe_load(path.read_text()) for path in sorted(CASES.glob("*.yaml"))]


def _ms(stamp: str) -> int:
    return int(datetime.fromisoformat(stamp.replace("Z", "+00:00")).timestamp() * 1000)


def _profile(held: Any, profile: dict[str, Any]) -> None:
    held.conn.execute(
        "UPDATE profile SET level = ?, subjects = ?, exam_date = ?, age_band = '18_plus'",
        (profile["level"], json.dumps(profile["subjects"]), profile.get("exam_date")),
    )


def _study_quiz_activity(case: dict[str, Any], tmp: Path) -> list[str]:
    from learner_harness import Session
    from test_w8_study_activity import _span, world

    class Scripted:
        async def local_ready(self) -> bool:
            return True

        async def study_generate(self, identity: str, request: dict[str, Any], chunks: list[dict[str, Any]]):
            c = chunks[0]
            items, keys = [], []
            for n, q in enumerate(case["quiz"]):
                options = [{"option_id": k, "text": v} for k, v in q["options"].items()]
                items.append({"item_id": f"i{n}", "type": "choice", "stem": _span(c, q["stem"]), "options": options})
                keys.append(
                    {
                        "item_id": f"i{n}",
                        "answer": q["key"],
                        "marking": "judged",
                        "explanation": _span(c, q["explanation"]),
                    }
                )
            return {
                "request_id": identity,
                "kind": "quiz",
                "claims": [_span(c, "From the notes.")],
                "quiz": {"items": items, "keys": keys},
            }, True

        async def study_support(self, request: Any, chunks: Any, output: dict[str, Any]):
            return [True] * (len(output["claims"]) + len(output["quiz"]["items"])), True

    w = world(tmp, case["profile"]["day"])
    _profile(w, case["profile"])
    Session(random.Random(3), w.learner, w.clock).run(case.get("seed_sessions", 0))
    w.queue.model = lambda: Scripted()
    w.source = w.desk.create({"kind": "text", "title": case["source"]["title"], "text": case["source"]["text"]})
    tables = case["expect"]["unchanged"]
    before = {t: w.conn.execute(f"SELECT * FROM {t} ORDER BY 1").fetchall() for t in tables}  # noqa: S608
    w.visits.open()
    quiz = w.make("quiz")
    items = w.desk.quiz(quiz["quiz_id"])["view"]["items"]
    answers = [{"item_id": i["item_id"], "answer": q["answer"]} for i, q in zip(items, case["quiz"], strict=True)]
    w.desk.submit(quiz["quiz_id"], {"attempt_id": "sqa_" + "1" * 26, "quiz_revision": 1, "answers": answers})
    expect, failures = case["expect"], []
    recorded = [a for a in w.activity() if a["activity"] == expect["activity"]]
    if not recorded:
        return ["no quiz_item was recorded"]
    first = recorded[0]
    if first["outcome"] != expect["outcome"]:
        failures.append(f"outcome {first['outcome']!r}, expected {expect['outcome']!r}")
    if not first["kc_tags"] or first["kc_tags"][0]["kc_id"] != expect["tag"]:
        failures.append(f"tags {first['kc_tags']!r} do not lead with {expect['tag']}")
    for t in tables:
        if w.conn.execute(f"SELECT * FROM {t} ORDER BY 1").fetchall() != before[t]:  # noqa: S608
            failures.append(f"{t} changed")
    return failures


def _last_time_card(case: dict[str, Any], tmp: Path) -> list[str]:
    from memory_harness import store

    held = store(day=case["profile"]["day"])
    _profile(held, case["profile"])
    for n, s in enumerate(case["sessions"]):
        held.conn.execute(
            "INSERT INTO sessions (session_id, mode, subject, started_at, ended_at) VALUES (?, ?, ?, ?, ?)",
            (f"S{n}", s["mode"], s["subject"], _ms(s["started"]), _ms(s["ended"])),
        )
    text = OpenerDesk(held.learner, Settings(), held.clock).opener()["text"]
    failures = [f"the card does not name {name!r}: {text!r}" for name in case["expect"]["names"] if name not in text]
    dates = re.findall(r"\d{4}-\d{2}-\d{2}", text)
    numbers = re.findall(r"\d+", re.sub(r"\d{4}-\d{2}-\d{2}", "", text))
    if dates + numbers != case["expect"]["numbers"]:
        failures.append(f"the card holds other dates or numbers: {text!r}")
    return failures


def _research_level_known(case: dict[str, Any], tmp: Path) -> list[str]:
    from memory_harness import PACK, store
    from test_research_chat import Router

    persona = next(p for p in yaml.safe_load(PERSONAS.read_text())["personas"] if p["id"] == case["persona"])
    held = store()
    _profile(held, {"level": persona["level"], "subjects": persona["subjects"]})
    profile = learner_profile(held.conn, PACK, Settings(), "2026-11-04")
    replies = [{"chips": [], "asks": None, "question": None, "brief": None, **r} for r in case["model"]]
    router = Router(replies)
    history: list[dict[str, Any]] = []
    answers = iter(["For my exam", "The basics", "20 minutes"])
    failures: list[str] = []
    for _ in range(4):
        turn = asyncio.run(next_turn(router, Start(topic=case["topic"]), history, None, profile=profile))
        if turn["kind"] == "question":
            shown = " ".join([turn["question"], *turn["chips"]])
            if re.search(rf"\b{case['expect']['never_ask']}\b", shown, re.IGNORECASE):
                failures.append(f"a turn asks the level: {shown!r}")
            history += [
                {"role": "jana", "text": turn["question"], "asks": turn["asks"]},
                {"role": "learner", "text": next(answers)},
            ]
            continue
        if turn["kind"] != "brief" or turn["brief"]["level"] != case["expect"]["brief_level"]:
            failures.append(f"the brief's level is {turn.get('brief', {}).get('level')!r}")
        return failures
    return [*failures, "no brief was written"]


def _companion_recall_local(case: dict[str, Any], tmp: Path) -> list[str]:
    from agent_core.engine.companion import cloud_tools, strip_for_cloud
    from agent_core.engine.memory_session import MemoryAccess, SessionMemory
    from agent_core.engine.memory_tools import MemoryTools
    from agent_core.store.ids import new_ulid
    from agent_core.tools.spec import InvalidArguments
    from w8_companion_harness import calls, stop_core, thread, turn

    script = {"companion": [calls((m["tool"], m["args"])) if "tool" in m else turn(m["text"]) for m in case["model"]]}
    past = case["past_session"]
    failures: list[str] = []

    async def go() -> None:
        t = await thread(tmp, script)
        try:
            learner = t.r.core.records.learner  # type: ignore[union-attr]
            sid = new_ulid()
            learner.conn.execute("INSERT INTO sessions (session_id, mode, subject, started_at, ended_at) VALUES (?,"
                                 " 'guided', ?, 1, 2)", (sid, past["subject"]))  # fmt: skip
            learner.conn.execute("INSERT INTO turns (turn_id, session_id, idx, speaker, status, student_text,"
                                 " started_at) VALUES (?, ?, 0, 'student', 'complete', ?, 1)",
                                 (new_ulid(), sid, past["line"]))  # fmt: skip
            learner.record("attempt", {"attempt_id": new_ulid(), "session_id": sid, "mode": "guided",
                                       "problem_ref": "prob_1", "kc_ids": [{"kc_id": past["kc"], "weight": 1}],
                                       "kc_source": "pack", "attempt_index": 1, "response_kind": "typed",
                                       "time_ms": 1000}, source="engine", session_id=sid)  # fmt: skip
            opened = await t.open()
            await t.say(opened["session_id"], case["ask"])
            results = [m for q in t.companion_requests() for m in q["messages"] if m["role"] == "tool"]
            texts = [x["text"] for m in results for x in json.loads(m["content"]).get("matches", [])]
            if case["expect"]["local_match"] not in texts:
                failures.append(f"the local candidate did not recall the past line: {texts!r}")
            # A cloud candidate: past recall refused by the handler, never offered notes, and the summary answers.
            memory = SessionMemory(MemoryAccess(learner.log.profile_id, t.r.runtime.memory_source), t.r.core.settings,
                                   opened["session_id"])  # fmt: skip
            cloud = MemoryTools(memory, t.r.core.settings, lambda: True)

            class Context:
                class session:
                    session_id = opened["session_id"]
                    subject = "physics"

            try:
                await cloud.search({"pattern": "projectile", "scope": "past"}, Context())  # type: ignore[arg-type]
                failures.append("a cloud call was served past-scope recall")
            except InvalidArguments:
                pass
            if "memory_recall" in cloud_tools(["memory_recall", "session_recall"], True):
                failures.append("a cloud call was offered the notes")
            if "<learner-notes>" in strip_for_cloud("<learner-notes>\nx\n</learner-notes>", True):
                failures.append("notes rode a cloud call")
            summary = (await t.api.call("GET", "/v1/companion/summary", profile=t.token)).json()
            if case["expect"]["summary_topic"] not in [x["kc_id"] for x in summary["topics"]]:
                failures.append(f"the summary has no {case['expect']['summary_topic']}: {summary['topics']!r}")
        finally:
            await stop_core(t.r)

    asyncio.run(go())
    return failures


def _cloud_block_dat18(case: dict[str, Any], tmp: Path) -> list[str]:
    """Consent off: the cloud block is MDL-25's (profile line, KC ids with bands, misconception ids, no notes); on:
    §19.6's list with the notes the egress scrub passes. A Study request's learner block is MDL-25's either way."""
    from agent_core.engine.memory_session import MemoryAccess, SessionMemory
    from agent_core.memory.render import NOTES_OPEN, allowance
    from agent_core.memory.snapshot import freeze as _freeze
    from agent_core.memory.snapshot import learner_block_data
    from agent_core.store.ids import new_ulid
    from memory_harness import DAY, store

    failures: list[str] = []
    held = store()
    p = case["profile"]
    held.conn.execute("UPDATE profile SET display_name = ?, level = ?, subjects = ?, exam_date = ?",
                      (p["display_name"], p["level"], json.dumps(p["subjects"]), p["exam_date"]))  # fmt: skip
    sid = held.session(new_ulid())
    for text in case["notes"]:
        held.note(text, sid)
    held.conn.execute(
        "INSERT INTO turns (turn_id, session_id, idx, speaker, status, student_text, started_at) VALUES"
        " (?, ?, 0, 'student', 'complete', ?, 1)",
        (new_ulid(), sid, case["transcript_line"]),
    )
    settings = Settings()
    terms = (p["display_name"], case["term"])
    budget = allowance(settings, "full", "cloud")
    blocks = {}
    for state, online in (("off", False), ("on", True)):
        memory = SessionMemory(MemoryAccess(held.profile, held.source), settings, "ses_" + sid,
                               memory_online=lambda online=online: online, terms=lambda: terms)  # fmt: skip
        memory.freeze(subject="physics", focus=(), session_date=DAY)
        block = memory.block("cloud", budget)
        blocks[state] = block.text if block is not None else ""
    off, on = blocks["off"], blocks["on"]
    if (NOTES_OPEN in off) != case["expect"]["consent_off"]["notes"]:
        failures.append("the consent-off block carries notes")
    for line in off.splitlines():
        if not any(line.startswith(prefix) for prefix in case["expect"]["consent_off"]["lines"]):
            failures.append(f"a consent-off line outside MDL-25: {line[:40]!r}")
    for text in case["expect"]["consent_on"]["notes"]:
        if text not in on:
            failures.append(f"the consent-on block lacks a scrubbed note: {text[:30]!r}")
    for text in case["expect"]["consent_on"]["withheld"]:
        if text in on:
            failures.append("a note the scrub withholds was carried")
    study = json.dumps(learner_block_data(_freeze(held.conn, PACK_INDEX(), settings, subject="physics",
                                                  topic_id=None, session_date=DAY)))  # fmt: skip
    for state, text in (("off", off), ("on", on), ("study", study)):
        for word in case["expect"]["never"]:
            if word in text:
                failures.append(f"{word!r} left in the {state} request")
    if "notes" in study or NOTES_OPEN in study:
        failures.append("a Study request carried notes")
    return failures


def PACK_INDEX() -> Any:
    from memory_harness import PACK

    return PACK


def _checkin_sunday(case: dict[str, Any], tmp: Path) -> list[str]:
    """The extractor on the student's own words, kept by code: one event_checkin due Sunday 07:00 local, no quote."""
    from types import SimpleNamespace

    from agent_core.contracts import document, errors
    from agent_core.engine.checkins import CheckinDesk
    from memory_harness import CAPTURE, store

    failures: list[str] = []
    held = store()
    held.conn.execute("UPDATE profile SET subjects = '[\"physics\"]'")
    now = _ms(case["now"])
    schema = {k: v for k, v in document("agents/commitment").items() if k not in ("$schema", "$id")}
    desk = CheckinDesk(lambda: held.learner, lambda: now, Settings(), capture=lambda: CAPTURE, schema=lambda: schema)
    desk._offset = lambda: int(case["offset_minutes"])  # type: ignore[method-assign]  # the profile's timezone

    class Router:
        calls = 0

        async def complete(self, slot: str, messages: list[Any], **kw: Any) -> Any:
            Router.calls += 1
            return SimpleNamespace(structured=dict(case["model"]), schema_valid=True)

    made = asyncio.run(desk.extract(Router(), case["student"], "ses_scenario", local_only=True))
    rows = held.conn.execute("SELECT kind, due_from, due_until, text FROM commitments").fetchall()
    expect = case["expect"]
    if Router.calls != 1 or len(rows) != expect["count"] or made is None:
        return [f"expected one commitment from one extractor call, got {len(rows)} from {Router.calls}"]
    kind, start, until, text = rows[0]
    local = datetime.fromtimestamp((start + case["offset_minutes"] * 60_000) / 1000, UTC).strftime("%Y-%m-%dT%H:%M")
    if kind != expect["kind"]:
        failures.append(f"kind {kind}")
    if local != expect["due_from_local"]:
        failures.append(f"due_from {local} local")
    if until - start != expect["window_hours"] * 3_600_000:
        failures.append("the window is not 72 hours")
    if re.search(r"[\"\u201c\u201d]|'[^']+'", text):
        failures.append("the question quotes")
    if errors("api/commands#/$defs/Commitment", made):
        failures.append("the commitment breaks its contract")
    return failures


RUNNERS = {
    "study_quiz_activity": _study_quiz_activity,
    "last_time_card": _last_time_card,
    "research_level_known": _research_level_known,
    "companion_recall_local": _companion_recall_local,
    "cloud_block_dat18": _cloud_block_dat18,
    "checkin_sunday": _checkin_sunday,
}


def run(case: dict[str, Any], tmp: Path) -> list[str]:
    return RUNNERS[case["case"]](case, tmp)
