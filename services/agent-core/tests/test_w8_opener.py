"""W8 (SPEC §19.5.2, §19.8): the opener. Facts come by code from the learner database (the last ended session of any
mode, review cards due, the nearest exam, a research pack ready), at most three are chosen in §19.5.2's order. Phase
1's Last time card words them with the engine's templates and makes no model call. Phase 2's thread words them with
one fast-model call whose output must hold every chosen number beside its label and no other number, with one
correction, else the template; the wording is cached for the day and a changed fact invalidates it. Synthetic data."""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Any

from agent_core.config import Settings
from agent_core.contracts import errors
from agent_core.engine import companion_opener
from agent_core.engine.companion import CompanionDesk, opener_errors, word_opener
from agent_core.engine.companion_opener import Facts, OpenerDesk, chosen, facts, load_templates, word
from agent_core.store.ids import new_ulid
from memory_harness import Store, at_ms, store

DAY = 86_400_000


def _session(held: Store, sid: str, mode: str, subject: str | None, started: int, ended: int | None,
             learned: bool = True) -> str:  # fmt: skip
    """A session of the given mode; `learned` gives it one learning event (a hint), as any real session holds. `sid`
    is the test's label; the stored id is a ULID, as the event contract requires."""
    stored = new_ulid(started)
    held.conn.execute(
        "INSERT INTO sessions (session_id, mode, subject, started_at, ended_at) VALUES (?, ?, ?, ?, ?)",
        (stored, mode, subject, started, ended),
    )
    if learned:
        held.learner.record("hint", {"session_id": stored, "problem_ref": f"prob_{sid}", "step_index": 0, "rung": 1,
                                     "trigger": "student_request", "kc_ids": ["kc.phy.o.motion.average_speed"]},
                            source="engine", session_id=stored)  # fmt: skip
    return stored


def _due(held: Store, kc: str, due_at: int) -> None:
    held.conn.execute(
        "INSERT INTO review_cards (kc_id, state, stability, difficulty, due_at, last_event_seq)"
        " VALUES (?, 'review', 3.0, 5.0, ?, 0)",
        (kc, due_at),
    )


def _desk(held: Store) -> OpenerDesk:
    return OpenerDesk(held.learner, Settings(), held.clock)


def test_study_cards_count_with_the_learner_cards_on_home() -> None:
    """Home's card and the thread's opener count the same cards: the learner model's plus Study's own (2 November)."""
    held = store(day="2026-10-11")
    _due(held, "phy.o.kin.1", at_ms("2026-10-11") + 3_600_000)
    alone = _desk(held).opener()
    assert alone["facts"]["learner_cards_due"] == 1 and alone["facts"]["study_cards_due"] == 0
    assert "1 card is due" in alone["text"]
    both = OpenerDesk(held.learner, Settings(), held.clock, study_cards=lambda now: 10).opener()
    assert (both["facts"]["learner_cards_due"], both["facts"]["study_cards_due"]) == (1, 10)
    assert "11 cards are due" in both["text"] and "1 card is due" not in both["text"]


def test_facts_pick_the_last_ended_session_of_any_mode() -> None:
    held = store(day="2026-10-11")
    _session(held, "S1", "guided", "mathematics", at_ms("2026-10-08"), at_ms("2026-10-08") + 600_000)
    _session(held, "S2", "study", "physics", at_ms("2026-10-10"), at_ms("2026-10-10") + 900_000)
    _session(held, "S3", "practice", "chemistry", at_ms("2026-10-11") - 1000, None)  # still open: not "last time"
    found = facts(held.learner, Settings(), held.clock.now)
    assert (found.last_session_date, found.last_session_mode, found.last_subject) == ("2026-10-10", "study", "physics")
    opener = _desk(held).opener()
    assert opener["text"].startswith("Last time you worked on physics in Study on 2026-10-10")
    assert opener["opener_id"] == "2026-10-11" and errors("api/commands#/$defs/Opener", opener) == []


def test_at_most_three_facts_are_chosen_in_order() -> None:
    held = store(day="2026-11-04")
    held.conn.execute("UPDATE profile SET exam_date = '2026-11-23'")
    _session(held, "S1", "study", "physics", at_ms("2026-11-04") - 3_600_000, at_ms("2026-11-04") - 60_000)
    for n, kc in enumerate(("kc.phy.o.motion.average_speed", "kc.phy.o.motion.free_fall")):
        _due(held, kc, held.clock.now - n)
    research = {"status": "ready", "brief": {"title": "Projectile motion SECRET"}}
    held.conn.execute(
        "INSERT INTO study_research (research_id, body, created_at, updated_at) VALUES (?, ?, ?, ?)",
        ("rsr_" + "0" * 26, json.dumps(research), held.clock.now, held.clock.now),
    )
    found = facts(held.learner, Settings(), held.clock.now)
    assert found.pack_ready and found.learner_cards_due == 2 and found.exam_distance_days == 19
    assert chosen(found) == ["last_session", "due", "exam"]  # the ready pack is the fourth: left out
    text = _desk(held).opener()["text"]
    assert text == "Last time you worked on physics in Study today; 2 cards are due and your exam is in 19 days."
    assert "pack" not in text and "SECRET" not in text
    # Without the last session, the pack is third and is said.
    held.conn.execute("DELETE FROM sessions")
    assert chosen(facts(held.learner, Settings(), held.clock.now)) == ["due", "exam", "pack_ready"]


def test_the_template_is_used_offline_and_without_a_candidate(tmp_path: Path) -> None:
    """Phase 1 has no model call at all: the core's reply is the template's wording, whatever the network or the
    model runtime, and a first visit says so plainly."""
    held = store(day="2026-10-11")
    held.conn.execute("UPDATE profile SET exam_date = NULL")
    first = _desk(held).opener()
    assert first["text"] == load_templates().text("first_time")
    assert first["facts"]["last_session_date"] is None and first["facts"]["exam_distance_days"] is None

    from api_harness import start_core, stop_core
    from test_m10a_profiles import Api, student

    async def scenario() -> tuple[int, dict]:
        runtime = await start_core(tmp_path, worker=False)
        try:
            runtime.core.online = None  # nothing online, and the scripted provider is never asked
            api = Api(runtime)
            pid = await api.add(student("Ada"))
            token = (await api.unlock(pid)).json()["profile_token"]
            reply = await api.call("GET", "/v1/companion/opener", profile=token)
            assert (await api.call("GET", "/v1/companion/opener")).status_code in (401, 403, 404)
            return reply.status_code, reply.json()
        finally:
            await stop_core(runtime)

    status, opener = asyncio.run(scenario())
    assert status == 200 and errors("api/commands#/$defs/Opener", opener) == []
    assert opener["text"] == load_templates().text("first_time")


def test_wording_contains_every_chosen_number_beside_its_label() -> None:
    templates = load_templates()
    cases = [
        Facts("2026-10-10", "guided", "physics", 8, 19, True, "2026-10-11"),
        Facts("2026-10-11", "practice", "mathematics", 1, 1, False, "2026-10-11"),
        Facts(None, None, None, 12, 0, True, "2026-10-11"),
        Facts("2026-10-09", "study", None, 0, None, True, "2026-10-11"),
    ]
    for found in cases:
        picked = chosen(found)
        text = word(found, picked, templates)
        numbers = re.findall(r"\d+", re.sub(r"\d{4}-\d{2}-\d{2}", "", text))
        expected = []
        if "due" in picked:
            expected.append(str(found.learner_cards_due))
            label = "card is due" if found.learner_cards_due == 1 else "cards are due"
            assert f"{found.learner_cards_due} {label}" in text
        if "exam" in picked and (found.exam_distance_days or 0) > 1:
            expected.append(str(found.exam_distance_days))
            assert f"in {found.exam_distance_days} days" in text
        assert numbers == expected, (text, numbers)
        dates = re.findall(r"\d{4}-\d{2}-\d{2}", text)
        assert dates == (
            [found.last_session_date] if "last_session" in picked and found.last_session_date != found.today else []
        )
        assert len(text) <= 240


def test_a_changed_fact_invalidates_the_cached_wording() -> None:
    """The facts are recomputed on every open (§19.5.2): a fact that changes changes the card; nothing stale is kept."""
    held = store(day="2026-10-11")
    _session(held, "S1", "guided", "physics", at_ms("2026-10-10"), at_ms("2026-10-10") + 60_000)
    desk = _desk(held)
    before = desk.opener()
    assert desk.opener() == before  # the same facts give the same card
    _due(held, "kc.phy.o.motion.average_speed", held.clock.now)
    after = desk.opener()
    assert after["facts"]["learner_cards_due"] == 1 and after["text"] != before["text"]
    assert "1 card is due" in after["text"]


def test_the_opener_falls_back_to_the_template_after_one_correction(monkeypatch) -> None:
    """Phase 1 words every opener with the template: the fall-back is the only wording, so there is no model output
    to correct and no call is made (the phase 2 fast-model wording is not here)."""
    held = store(day="2026-10-11")
    _session(held, "S1", "study", "physics", at_ms("2026-10-10"), at_ms("2026-10-10") + 60_000)
    assert not any(name in dir(companion_opener) for name in ("router", "Router", "complete", "Message"))
    found = facts(held.learner, Settings(), held.clock.now)
    assert _desk(held).opener()["text"] == word(found, chosen(found), load_templates())


# --- phase 2: the thread's opener worded by the fast model (§19.5.2) -----------------------------------------------


class _Result:
    def __init__(self, text: str) -> None:
        self.schema_valid, self.structured = True, {"text": text, "action": None}


class _Router:
    """A scripted fast model: the wordings in order, and every prompt it was asked."""

    def __init__(self, *texts: str) -> None:
        self.texts, self.prompts = list(texts), []

    async def complete(self, role: str, messages: list[Any], **kw: Any) -> _Result:
        self.prompts.append(messages[-1].content)
        return _Result(self.texts.pop(0))


_SCHEMA = ("agents/companion-turn", {}, None)
_DEMO = Facts("2026-11-04", "study", "physics", 8, 19, False, "2026-11-04")


def test_wording_contains_every_chosen_number_beside_its_label_phase_2() -> None:
    picked = chosen(_DEMO)
    assert opener_errors("You worked on physics in Study today; 8 cards are due and the exam is in 19 days.", _DEMO,
                         picked) == []  # fmt: skip
    assert opener_errors("8 days to your exam, and 19 cards due.", _DEMO, picked)  # each number beside another label
    assert opener_errors("You have 8 cards due, 19 days to go, and 3 packs.", _DEMO, picked)  # a number not a fact
    assert opener_errors("You have cards due.", _DEMO, picked)  # a chosen number missing
    text, how = asyncio.run(
        word_opener(
            _Router("Welcome back! 8 cards are due, and your exam is in 19 days."), _DEMO, picked, "template", _SCHEMA
        )
    )  # type: ignore[arg-type]
    assert (how, text) == ("model", "Welcome back! 8 cards are due, and your exam is in 19 days.")


def test_the_opener_falls_back_to_the_template_after_one_correction_phase_2() -> None:
    picked = chosen(_DEMO)
    router = _Router("19 cards due!", "8 cards are due and your exam is in 19 days.")
    _, how = asyncio.run(word_opener(router, _DEMO, picked, "the template", _SCHEMA))  # type: ignore[arg-type]
    assert how == "corrected" and "broke the rules" in router.prompts[1]
    router = _Router("19 cards due!", "Still 19 cards due!")
    assert asyncio.run(word_opener(router, _DEMO, picked, "the template", _SCHEMA)) == ("the template", "template")  # type: ignore[arg-type]
    assert asyncio.run(word_opener(None, _DEMO, picked, "the template", _SCHEMA)) == ("the template", "template")  # type: ignore[arg-type]


def test_a_changed_fact_invalidates_the_cached_wording_phase_2() -> None:
    held = store(day="2026-10-11")
    held.conn.execute("UPDATE profile SET exam_date = NULL")
    _session(held, "S1", "guided", "physics", at_ms("2026-10-10"), at_ms("2026-10-10") + 60_000)
    router = _Router(
        "Last time: physics with the tutor on 2026-10-10.", "1 card is due now; physics was on 2026-10-10."
    )
    desk = CompanionDesk(lambda: held.learner, held.clock, Settings(), router=lambda: router, schema=lambda: _SCHEMA)  # type: ignore[arg-type,return-value]

    async def go() -> list[dict[str, Any]]:
        sid = "ses_" + "1" * 26
        held.conn.execute("INSERT INTO sessions (session_id, mode, started_at) VALUES (?, 'study_companion', ?)",
                          (sid.removeprefix("ses_"), held.clock.now))  # fmt: skip
        first = await desk.open(lambda: sid, lambda s: True)
        again = await desk.open(lambda: sid, lambda s: True)  # the same facts: the cached wording, no call
        _due(held, "kc.phy.o.motion.average_speed", held.clock.now)
        changed = await desk.open(lambda: sid, lambda s: True)
        return [first, again, changed]

    first, again, changed = asyncio.run(go())
    assert first["opener"]["text"] == again["opener"]["text"] and len(router.prompts) == 2
    assert changed["opener"]["facts"]["learner_cards_due"] == 1
    assert changed["opener"]["text"] == "1 card is due now; physics was on 2026-10-10."
    assert errors("api/commands#/$defs/CompanionOpened", changed) == []


def test_the_onboarding_interview_and_sessions_without_learning_never_count() -> None:
    """The hand-off's scripted interview runs in a session with no learning event; neither it nor any session the
    learner opened and left without learning is "last time": a brand-new profile sees the first-time card (§19 fix,
    2026-10-29)."""
    held = store(day="2026-10-11")
    held.conn.execute("UPDATE profile SET exam_date = NULL")  # a brand-new profile: nothing else to say yet
    _session(held, "interview", "guided", "mathematics", at_ms("2026-10-11") - 3_600_000,
             at_ms("2026-10-11") - 3_000_000, learned=False)  # fmt: skip
    found = OpenerDesk(held.learner, Settings(), held.clock).opener()
    assert found["facts"]["last_session_date"] is None and found["facts"]["last_session_mode"] is None
    assert found["text"] == load_templates().text("first_time")
    # A session with learning in it does count, even an older one.
    _session(held, "S1", "practice", "physics", at_ms("2026-10-09"), at_ms("2026-10-09") + 600_000)
    after = OpenerDesk(held.learner, Settings(), held.clock).opener()
    assert (after["facts"]["last_session_date"], after["facts"]["last_subject"]) == ("2026-10-09", "physics")
