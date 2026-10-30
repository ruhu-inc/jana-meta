"""Personalization explains its evidence without treating a preference as demonstrated understanding."""

from agent_core.config import Settings
from agent_core.engine.knows import KnowsDesk
from agent_core.memory.queries import stored_notes
from memory_harness import store


def test_saved_note_explains_its_sources_and_the_limits_of_its_evidence() -> None:
    held = store()
    note_id = held.note("Prefers drawing labelled force diagrams", "A" * 26)
    desk = KnowsDesk(held.source(), Settings())
    note = desk._note(next(n for n in stored_notes(held.conn) if n.note_id == note_id))
    assert note["explanation"]["basis"] == "practice_observation"
    assert note["explanation"]["sources"][0]["kind"] == "hint"
    assert "does not establish" in note["explanation"]["meaning"]


def test_teaching_observations_are_exposed_separately_from_preferences_and_mastery() -> None:
    held = store()
    desk = KnowsDesk(held.source(), Settings())
    assert desk.view()["teaching_observations"] == []


def test_observation_links_hints_and_delayed_outcomes_without_promoting_mastery() -> None:
    from agent_core.memory.observations import teaching_observations
    from memory_harness import SPEED
    from test_m15e_memory import World
    from test_m33b_research_rows import SKILL

    held = store()
    world = World(held.learner, held.clock, held.session("A" * 26))
    world.practise(SPEED, "incorrect")
    delivered = held.learner.record(
        "skills_delivered", {"turn_id": "B" * 26, "skills": [SKILL]}, source="engine", session_id=world.sid
    )
    world.practise(SPEED, "correct", hints=2)
    world.tick(2 * 86_400_000)
    world.sid = held.session("C" * 26)
    world.practise(SPEED, "incorrect")
    before = held.conn.execute("SELECT * FROM kc_mastery").fetchall()
    rows = teaching_observations(held.conn, held.source().content)
    assert len(rows) == 1
    row = rows[0]
    assert row["source_event_id"] == delivered.event_id
    assert row["immediate"]["outcome"] == "correct" and row["immediate"]["hints_used"] == 2
    assert row["delayed"]["outcome"] == "incorrect" and row["conflicting_outcomes"]
    assert row["confidence"] == "tentative"
    assert held.conn.execute("SELECT * FROM kc_mastery").fetchall() == before


def test_self_reports_and_generated_study_activity_never_become_teaching_outcomes() -> None:
    from agent_core.memory.observations import teaching_observations
    from agent_core.memory.write import NOTES_WRITER
    from agent_core.store.ids import new_ulid

    held = store()
    sid = held.session("A" * 26)
    event = held.learner.record("memory_requested", {"request_id": new_ulid()}, source="student", session_id=sid)
    note_id = new_ulid()
    held.learner.record(
        "note_written",
        {
            "note_id": note_id,
            "text": "Prefers drawing force diagrams",
            "status": "active",
            "subject": "physics",
            "source_event_ids": [event.event_id],
        },
        source="student",
        session_id=sid,
        writer=NOTES_WRITER,
    )
    desk = KnowsDesk(held.source(), Settings())
    note = desk.view()["notes"][0]
    assert note["explanation"]["basis"] == "self_report"
    assert teaching_observations(held.conn, held.source().content) == []
