"""Live-walk-through fix of 1 November (item 1): with the cloud tutor allowed but its first-use notice (ARC-10) not yet
answered, and no model on this computer, a tutoring turn used to fail inside its first model call and the learner saw
"The tutor stopped unexpectedly". Every turn now shows the notice card, or says plainly what is missing, and sends
nothing. Every learner and reply here is synthetic."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
from agent_core.engine.turn import Engine, TurnNeedsNotice
from engine_harness import STATEMENT, close, make_engine

LOOP = asyncio.new_event_loop()


def run(coro: Any) -> Any:
    return LOOP.run_until_complete(coro)


def events(engine: Engine) -> list[dict[str, Any]]:
    engine.events.flush()
    return [f["event"] for f in engine.events.frames]


def shown(engine: Engine) -> str:
    return "".join(e["delta"] for e in events(engine) if e["type"] == "text.delta")


def card_titles(engine: Engine) -> list[str]:
    return [
        e["card"]["title"] for e in events(engine) if e["type"] == "card.open" and e["card"].get("purpose") == "egress"
    ]


def turn_ends(engine: Engine) -> list[dict[str, Any]]:
    return [e for e in events(engine) if e["type"] == "turn.end"]


async def waiting_engine(tmp: Path, answers: dict[str, str]) -> Engine:
    """The demo host's shape: cloud tutor consented and switched on, no model on this computer, notice unanswered."""
    engine, local = await make_engine(tmp, {})
    engine.deps.router.providers.pop("local")
    engine.cloud_possible = lambda: True
    engine.cloud_notice = lambda: answers.get("cloud_tier")
    engine.record_cloud_notice = lambda ok: answers.__setitem__("cloud_tier", "accepted" if ok else "declined")
    engine.local_calls = local  # type: ignore[attr-defined]
    return engine


ENTRY_POINTS = {
    "guided": lambda e: e.start_problem(STATEMENT),
    "ask": lambda e: e.side_question("Why does a ball curve?"),
    "answer": lambda e: e.student_turn("s = 3 m"),
    "hint": lambda e: e.student_turn("I'm stuck", stuck=True),
}


@pytest.mark.parametrize("name", sorted(ENTRY_POINTS))
def test_every_tutoring_turn_asks_or_says_what_is_missing(tmp_path: Path, name: str) -> None:
    answers: dict[str, str] = {}

    async def scenario() -> tuple[Engine, Any]:
        engine = await waiting_engine(tmp_path, answers)
        try:
            with pytest.raises(TurnNeedsNotice) as stopped:
                await ENTRY_POINTS[name](engine)
            return engine, stopped.value.result
        finally:
            await close(engine)

    engine, outcome = run(scenario())
    (end,) = turn_ends(engine)
    assert end["status"] != "error", end
    assert outcome.status == "complete"
    assert card_titles(engine) == ["Use the cloud tutor?"]  # the first-use card is on screen
    assert "Choose OK" in shown(engine) and "nothing has been sent" in shown(engine)
    assert outcome.trace["model_calls"] == []


def test_a_second_turn_before_the_answer_repeats_the_request_in_words(tmp_path: Path) -> None:
    answers: dict[str, str] = {}

    async def scenario() -> Engine:
        engine = await waiting_engine(tmp_path, answers)
        try:
            for ask in (lambda: engine.start_problem(STATEMENT), lambda: engine.student_turn("s = 3 m")):
                with pytest.raises(TurnNeedsNotice):
                    await ask()
            return engine
        finally:
            await close(engine)

    engine = run(scenario())
    assert card_titles(engine) == ["Use the cloud tutor?"]  # one card, not one per turn
    assert [e["status"] for e in turn_ends(engine)] == ["complete", "complete"]
    assert shown(engine).count("Choose OK") == 2


def test_a_declined_notice_says_the_tutor_needs_the_online_tutor(tmp_path: Path) -> None:
    answers: dict[str, str] = {"cloud_tier": "declined"}

    async def scenario() -> Engine:
        engine = await waiting_engine(tmp_path, answers)
        try:
            with pytest.raises(TurnNeedsNotice):
                await engine.start_problem(STATEMENT)
            return engine
        finally:
            await close(engine)

    engine = run(scenario())
    text = shown(engine)
    assert "no tutor on this computer" in text and "Settings" in text
    assert card_titles(engine) == []  # the learner already answered it; no card is raised again
    assert [e["status"] for e in turn_ends(engine)] == ["complete"]


def test_the_trace_records_the_connectivity_state_it_read() -> None:
    from agent_core.trace.record import TraceBuilder

    build = TraceBuilder("ses_1", "prf_1", turn_id="turn_1", mode="guided", subject="physics", level="O",
                         build={"app_version": "0", "build_id": "dev", "os": "linux", "arch": "x64",
                                "hardware_class": "mid"},
                         assets={}, connectivity="online")  # fmt: skip
    assert build.record()["connectivity"]["state_at_start"] == "online"
    assert json.dumps(build.record()).count('"state_at_start"') == 1
