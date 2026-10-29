"""W8 phase 1 (SPEC §19.3.1, §19.4, §19.8): Study requests carry the learner block, MDL-25's set and nothing else, and
the research conversation knows the level an O profile holds (JM-D29): it never asks it, and the brief's level is
o_level by code. An A profile keeps the level question. Every learner, note and topic here is synthetic."""

from __future__ import annotations

import asyncio
import hashlib
import json
import random
from pathlib import Path
from typing import Any

import pytest
from agent_core.config import Settings
from agent_core.contracts import errors
from agent_core.engine.research_chat import (
    LearnerProfile,
    Start,
    learner_profile,
    next_turn,
    profile_lines,
    task,
)
from agent_core.memory.queries import KcLine, MisconceptionLine, ProfileSummary
from agent_core.memory.snapshot import FrozenMemory, freeze, learner_block_data
from agent_core.net.study import StudyCloudError
from agent_core.store import consents
from learner_harness import Session
from memory_harness import PACK, store
from net_harness import FakeServices, enable, layer
from test_research_chat import Router, brief, question, wrote

PROJECTILES = Start(topic="projectile motion")
O_PROFILE = LearnerProfile("O", ("physics",), (("secure", "Calculate average speed"),))
A_PROFILE = LearnerProfile("A", ("mathematics",), ())
MDL25 = {"level", "subjects", "kcs", "misconception_ids"}


def _frozen(kcs: int = 30, misconceptions: int = 10) -> FrozenMemory:
    states = ("mastered", "learning", "not_started", "ready_to_check", "needs_review", "moved_on")
    return FrozenMemory(
        session_date="2026-11-04",
        profile=ProfileSummary(
            "O", ("physics", "mathematics", "physics"), "in 19 days", "standard", "extra", "on_request"
        ),
        kcs=tuple(KcLine(f"kc.phy.o.motion.k{n:02d}", f"Statement {n}", states[n % 6], "low") for n in range(kcs)),  # type: ignore[arg-type]
        misconceptions=tuple(
            MisconceptionLine(f"mc.phy.o.m{n:02d}", f"Name {n}", "active", 2) for n in range(misconceptions)
        ),
        preferences=(),
        recent=(),
        older=(),
    )


def test_processing_request_carries_mdl25_fields_only() -> None:
    block = learner_block_data(_frozen())
    assert set(block) == MDL25
    assert block["level"] == "O" and block["subjects"] == ["physics", "mathematics"]  # once each, enum only
    assert all(set(k) == {"kc_id", "band"} for k in block["kcs"])
    assert {k["band"] for k in block["kcs"]} == {"secure", "learning", "not_started"}
    chunk = {
        "chunk_id": "sck_" + "2" * 26,
        "source_id": "src_" + "1" * 26,
        "revision": 1,
        "ordinal": 0,
        "locator": {"kind": "text", "paragraph": 1},
        "text": "x",
        "sha256": hashlib.sha256(b"x").hexdigest(),
    }
    body = {"request_id": "stj_" + "0" * 26, "kind": "quiz", "chunks": [chunk], "output_locale": "en", "learner": block}
    assert errors("study/workspace#/$defs/ProcessingRequest", body) == []
    # Anything outside MDL-25's set does not validate: notes (phase 3 only), an exam date, a name, a preference.
    for extra in ({"notes": []}, {"exam_date": "2027-06-01"}, {"display_name": "Ama"}, {"pace": "short"}):
        assert errors("study/workspace#/$defs/ProcessingRequest", {**body, "learner": {**block, **extra}})
    with pytest.raises(ValueError):
        learner_block_data(_frozen(), variant="local")  # type: ignore[arg-type]


def test_learner_block_data_selects_focus_kcs_first_and_caps_at_24() -> None:
    block = learner_block_data(_frozen())
    assert len(block["kcs"]) == 24 and len(block["misconception_ids"]) == 8
    assert [k["kc_id"] for k in block["kcs"]] == [
        f"kc.phy.o.motion.k{n:02d}" for n in range(24)
    ]  # the snapshot's order
    # On a real learner database the snapshot's order is the focus KCs first, then the most recently practised.
    held = store()
    Session(random.Random(7), held.learner, held.clock).run(4)
    practised = [r[0] for r in held.conn.execute("SELECT kc_id FROM kc_mastery ORDER BY kc_id")]
    assert practised, "the synthetic session left evidence"
    focus = "kc.phy.o.motion.solve_with_equation"
    frozen = freeze(
        held.conn,
        PACK,
        Settings(),
        subject=None,
        topic_id=None,
        session_date="2026-11-04",
        focus=[focus],
        kcs_max=24,
        misconceptions_max=8,
    )
    kcs = [k["kc_id"] for k in learner_block_data(frozen)["kcs"]]
    assert kcs[0] == focus and set(practised) <= set(kcs) and len(kcs) <= 24


def test_a_cloud_study_request_carries_nothing_outside_mdl25(tmp_path: Path) -> None:
    """DAT-18 for a Study request (extends test_dat18_egress.py): what reaches the study host is the request, its
    chunks and the learner block's four fields; no name, exam date, note or preference rides with it."""
    held = store(path=str(tmp_path / "learner.db"))
    held.conn.execute("UPDATE profile SET display_name = 'Ama MUSTSTAYLOCAL', age_band = '18_plus'")
    held.note("Prefers diagrams first MUSTSTAYLOCAL", "ses_" + "1" * 26)
    held.conn.execute(
        "INSERT INTO preferences (key, value, confidence, last_event_seq) VALUES ('pace', ?, 1, 0)",
        (json.dumps({"override": "short"}),),
    )
    Session(random.Random(3), held.learner, held.clock).run(3)
    frozen = freeze(
        held.conn,
        PACK,
        Settings(),
        subject=None,
        topic_id=None,
        session_date="2026-11-04",
        kcs_max=24,
        misconceptions_max=8,
    )
    block = learner_block_data(frozen)
    for scope in ("study_materials", "cloud_tier"):
        consents.grant(
            held.conn,
            scope,
            "student_18_plus",
            "Ama",
            "v1",
            "dpia-test",
            held.clock.now,
            include_study=True,
            early=("cloud_tier",),
        )
    text = "Uniform acceleration links v, u, a and t."
    chunk = {
        "chunk_id": "sck_" + "2" * 26,
        "source_id": "src_" + "1" * 26,
        "revision": 1,
        "ordinal": 0,
        "locator": {"kind": "text", "paragraph": 1},
        "text": text,
        "sha256": hashlib.sha256(text.encode()).hexdigest(),
    }

    async def scenario() -> dict[str, Any]:
        async with FakeServices(tmp_path) as fake:
            fake.handlers["/v1/study/process"] = lambda seen: (422, {"error": {"code": "insufficient_evidence"}})
            online = layer(tmp_path, fake, settings=Settings(study_workspace_enabled=True))
            try:
                enable(online, "study_materials", "cloud_tier")
                online.record_notice("prf_test", "study_materials", True)
                online.connectivity.state = "online"
                online.subscription = lambda: {  # type: ignore[method-assign]
                    "subscription_id": "sub_test",
                    "period_start": 0,
                    "period_end": 4_000_000_000_000,
                    "seats": 1,
                    "allowance_tokens": 1_800_000,
                    "plan": "jana_online",
                    "profiles": ["prf_test"],
                    "consent_needed": [],
                    "ended_at": None,
                }
                cloud = online.study_client(lambda: "prf_test", lambda: held.conn)
                request = {
                    "kind": "quiz",
                    "sources": [{"source_id": chunk["source_id"], "revision": 1}],
                    "count": 3,
                    "learner": block,
                }
                with pytest.raises(StudyCloudError):
                    await cloud.process(held.conn, "stj_" + "0" * 26, request, [chunk], attempt=1)
                sent = [r for r in fake.requests if r.path == "/v1/study/process"]
                assert len(sent) == 1
                wire = json.dumps([r.json() for r in fake.requests]) + json.dumps([r.headers for r in fake.requests])
                assert "MUSTSTAYLOCAL" not in wire and "2027-06-01" not in wire and "short" not in wire
                return dict(sent[0].json())
            finally:
                await online.stop()

    body = asyncio.run(scenario())
    assert errors("study/workspace#/$defs/ProcessingRequest", body) == []
    assert set(body) == {"request_id", "kind", "chunks", "output_locale", "count", "learner"}
    assert set(body["learner"]) == MDL25 and body["learner"] == block
    assert all(set(k) == {"kc_id", "band"} for k in body["learner"]["kcs"])


# --- the research conversation (§19.4 research_chat.py, JM-D29) --------------------------------------------------


def _run(
    router: Router,
    profile: LearnerProfile | None,
    history: list[dict[str, Any]] | None = None,
    answer: str | None = None,
) -> dict[str, Any]:
    return asyncio.run(next_turn(router, PROJECTILES, history or [], answer, profile=profile))


def test_the_research_chat_never_asks_a_level_an_o_profile_holds() -> None:
    asks_level = {
        **question("purpose", "Is this pack for an O level exam, a lesson or curiosity?"),
        "chips": ["O level exam", "First year", "Curiosity"],
    }
    known = {
        **question("known", "What do you already know about projectile motion?"),
        "chips": ["Nothing yet", "O level only", "The equations"],
    }
    router = Router([asks_level, known])
    turn = _run(router, O_PROFILE)
    # The question that would ask the level never reaches the learner: code asked for the next one instead.
    assert turn["kind"] == "question" and turn["asks"] == "known"
    assert "level" not in turn["question"].lower() and not any("level" in c.lower() for c in turn["chips"])
    assert turn["chips"] == ["Nothing yet", "The equations"]
    assert len(router.calls) == 2 and "Already asked: purpose" in router.calls[1]["prompt"]
    assert "<learner-profile>" in router.calls[0]["prompt"] and "do not ask it" in router.calls[0]["prompt"]
    assert not errors("study/research#/$defs/ChatTurn", turn)
    # Asked again under another name, it is passed over again; the conversation goes on to the brief.
    level_again = question("known", "Which level are you studying at, and what do you know already?")
    router = Router([asks_level, level_again, wrote({k: v for k, v in brief().items() if k != "level"})])
    turn = _run(router, O_PROFILE)
    assert turn["kind"] == "brief" and turn["brief"]["level"] == "o_level" and len(router.calls) == 3
    assert "Already asked: purpose, known" in router.calls[2]["prompt"]


def test_an_a_profile_keeps_the_level_question() -> None:
    asks_level = question("purpose", "Is this pack for an O level exam or for first year?")
    router = Router([asks_level])
    turn = _run(router, A_PROFILE)
    assert turn["kind"] == "question" and turn["question"] == asks_level["question"]  # JM-D29: A is not mapped
    decode = router.calls[0]["schema"]
    assert "level" in decode["$defs"]["Brief"]["properties"] and "level" in decode["$defs"]["Brief"]["required"]
    assert "do not ask it" not in router.calls[0]["prompt"]
    # An A learner's brief keeps the level the learner said.
    router = Router([wrote(brief(level="first_year"))])
    assert _run(router, A_PROFILE, answer="first year at university")["brief"]["level"] == "first_year"


def test_brief_level_is_set_by_code_before_validation() -> None:
    without_level = {k: v for k, v in brief().items() if k != "level"}
    router = Router([wrote(without_level)])
    turn = _run(router, O_PROFILE)
    # The decode schema has no level for the model to write; code sets o_level, then the turn is checked whole.
    decode = router.calls[0]["schema"]
    assert "level" not in decode["$defs"]["Brief"]["properties"] and "level" not in decode["$defs"]["Brief"]["required"]
    assert turn["brief"]["level"] == "o_level"
    assert not errors("study/research#/$defs/Brief", turn["brief"])
    # The learner says the pack is for first year: the profile no longer decides, and the model must write a level.
    history = [
        {"role": "jana", "text": "What is the pack for?", "asks": "purpose"},
        {"role": "learner", "text": "It's for my first year course"},
    ]
    router = Router([wrote(brief(level="first_year"))])
    turn = _run(router, O_PROFILE, history=history, answer="20 minutes")
    assert "level" in router.calls[0]["schema"]["$defs"]["Brief"]["required"]
    assert turn["brief"]["level"] == "first_year"


def test_research_task_lines_hold_bands_as_words_not_ids() -> None:
    held = store()
    Session(random.Random(11), held.learner, held.clock).run(4)
    profile = learner_profile(held.conn, PACK, Settings(), "2026-11-04")
    assert profile.level == "O" and profile.subjects == ("physics",)
    section = profile_lines(
        LearnerProfile(
            "O",
            ("physics",),
            (
                ("secure", "Calculate average speed from the total distance and the total time"),
                ("learning", "Solve <for> v"),
            ),
        )
    )
    assert section.startswith("<learner-profile>") and section.endswith("</learner-profile>")
    assert "Level: O level" in section and "Subjects: physics" in section
    assert "Secure: Calculate average speed" in section and "Still learning: Solve &lt;for&gt; v" in section
    prompt = task(PROJECTILES, [], None, brief_now=False, profile=profile)
    assert "<learner-profile>" in prompt and prompt.index("<learner-profile>") < prompt.index("<topic>projectile")
    for marker in ("kc.", "mc.", "prf_", "Ama"):  # ids and the name never reach the conversation
        assert marker not in prompt.split("<learner-profile>")[1].split("</learner-profile>")[0]
