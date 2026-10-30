"""Fixes found running the §19.10 demo path live (SPEC §19 status, 2026-10-29): the thread's own first-time line, the
knows page's sharing flag for personal tutor memory online, and Study activity from a research pack named as the
pack's. Every learner, source and reply here is synthetic."""

from __future__ import annotations

import json
from pathlib import Path

from agent_core.api.records import SHARING
from agent_core.contracts import errors
from agent_core.engine.companion_opener import OpenerDesk, load_templates
from agent_core.memory.queries import from_research_pack, recent_study_activity
from agent_core.store.ids import new_ulid
from memory_harness import PACK
from test_w8_plan_study_cards import _deck
from test_w8_study_activity import world


def test_the_thread_greets_with_its_own_first_time_line(tmp_path: Path) -> None:
    from w8_companion_harness import run, stop_core, thread

    templates = load_templates()
    assert templates.text("first_time_thread") != templates.text("first_time")

    async def go() -> None:
        t = await thread(tmp_path, {})
        try:
            learner = t.r.core.records.learner  # type: ignore[union-attr]
            learner.conn.execute("UPDATE profile SET exam_date = NULL")  # a new profile: nothing to recall yet
            opened = await t.open()
            assert opened["opener"]["text"] == templates.text("first_time_thread")
            card = OpenerDesk(learner, t.r.core.settings, t.r.core.clock_ms).opener()
            assert card["text"] == templates.text("first_time"), "the card keeps its own words"
        finally:
            await stop_core(t.r)

    run(go())


def test_the_knows_sharing_flag_follows_personal_tutor_memory_online() -> None:
    assert SHARING["tutor_memory"] == "tutor_memory_online"
    flags = {"backup": False, "devices": False, "parent_view": False, "cloud_tutor": True}
    sharing = "api/commands#/$defs/KnowsView/properties/sharing"
    assert errors(sharing, {**flags, "tutor_memory": True}) == []
    assert errors(sharing, flags) == [], "an older core's flags still validate"


def test_study_activity_from_a_research_pack_is_the_packs(tmp_path: Path) -> None:
    w = world(tmp_path)
    deck = _deck(w, w.source["source_id"])
    aid_id = w.conn.execute("SELECT aid_id FROM study_decks WHERE deck_id = ?", (deck,)).fetchone()[0]
    card_id = w.conn.execute("SELECT card_id FROM study_flashcards WHERE deck_id = ?", (deck,)).fetchone()[0]
    assert not from_research_pack(w.conn, f"aid:{aid_id}")  # the learner's own material
    w.visits.card(card_id, "", "good")
    assert [a.get("from_pack") for a in recent_study_activity(w.conn, PACK) if a["activity"] == "card_review"] == [
        False
    ]
    # The same source as a research pack's (the research agent made it, §18).
    w.conn.execute(
        "INSERT INTO study_research (research_id, gateway_id, body, created_at, updated_at) VALUES (?, NULL, ?, 1, 2)",
        (f"rsr_{new_ulid()}", json.dumps({"status": "ready", "source_id": w.source["source_id"]})),
    )
    assert from_research_pack(w.conn, f"aid:{aid_id}") and from_research_pack(w.conn, f"card:{card_id}")
    assert not from_research_pack(w.conn, "jny:step_1") and not from_research_pack(w.conn, "att:missing:0")
    marked = [a for a in recent_study_activity(w.conn, PACK) if a["activity"] == "card_review"]
    assert marked and all(a["from_pack"] is True for a in marked)
    assert errors("api/commands#/$defs/KnowsView/properties/activity", marked) == []
