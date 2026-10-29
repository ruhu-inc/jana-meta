"""W8 phase 2 (SPEC §19.4 plans.py and planner.py, §19.8, LEARNING_AGENT_REVIEW B5): the plan's warm-up lists Study's
due cards. The state collector reads them (due by the end of today, soonest first, at most ten, only from decks whose
source revision still exists, never suspended); the planner puts them in one `due_reviews_study` warm-up after the
learner-model warm-up, within the same review cap; and the deck and card ids survive the `plan_generated` event, the
stored plan and the Plan view. Every learner, source and card here is synthetic."""

from __future__ import annotations

import asyncio
import json
import random
from dataclasses import replace
from pathlib import Path

from agent_core.config import Settings
from agent_core.contracts import errors
from agent_core.engine.events import new_id
from agent_core.engine.plans import PlanDesk
from agent_core.learner import planner
from agent_core.learner.mastery import DAY_MS
from agent_core.learner.planner import KcPlanInfo, PlannerState, SubjectInfo
from memory_harness import PACK
from test_m15d_plans import fixture_state
from test_w8_study_activity import TEXT, World, world

S = Settings()
LESSON = "kc.phy.o.motion.average_speed"


def _deck(w: World, source_id: str) -> str:
    """Flashcards made from one source through the scripted local model; the new deck's id."""
    job = w.desk.create_job(
        {"kind": "flashcards", "execution": "local", "count": 3, "sources": [{"source_id": source_id, "revision": 1}]}
    )
    asyncio.run(w.queue.run(w.desk, job["job_id"]))
    done = w.desk.job(job["job_id"])
    assert done["state"] == "completed", done
    return str(w.desk.aid(done["result_ids"][0])["deck_id"])


def _card(w: World, deck_id: str, due_at: int, like: str | None = None) -> str:
    """One more card in a deck due at `due_at`, a copy of a card of that deck (or of the deck `like`)."""
    body, schedule = w.conn.execute(
        "SELECT body, schedule FROM study_flashcards WHERE deck_id = ? LIMIT 1", (like or deck_id,)
    ).fetchone()
    card_id = new_id("fcd")
    w.conn.execute(
        "INSERT INTO study_flashcards VALUES (?,?,?,?,?,?)",
        (card_id, deck_id, 1, json.dumps({**json.loads(body), "card_id": card_id}), schedule, due_at),
    )
    return card_id


def _desk(w: World) -> PlanDesk:
    return PlanDesk(w.learner, PACK, S, clock_ms=w.clock)


# --- the state collector (§19.4 plans.py) ------------------------------------------------------------------------


def test_the_state_collector_reads_due_study_cards_whose_source_exists(tmp_path: Path) -> None:
    w = world(tmp_path)
    desk = _desk(w)
    now = w.clock.now
    p = desk.params
    end = (p.local_day(now) + 1) * DAY_MS - p.learner_day_offset_minutes * 60_000
    assert desk.state(now).study_due == ()  # no Study cards: nothing to read

    deck = _deck(w, w.source["source_id"])  # two cards, due now
    eligible = [(due, card) for card, due in w.conn.execute(
        "SELECT card_id, due_at FROM study_flashcards WHERE deck_id = ?", (deck,))]  # fmt: skip
    eligible += [(now - 60_000 * i, _card(w, deck, now - 60_000 * i)) for i in range(1, 10)]
    eligible.append((now, _card(w, deck, now)))  # a tie with the first two, ordered by card id
    eligible.append((end - 1, _card(w, deck, end - 1)))  # the last moment of today still counts
    _card(w, deck, end)  # due tomorrow

    # A stale source's cards are suspended.
    other = w.desk.create({"kind": "text", "title": "Second notes", "text": TEXT + "\n\nA second copy."})
    stale = _deck(w, other["source_id"])
    w.conn.execute("UPDATE study_flashcards SET due_at = ? WHERE deck_id = ?", (now - DAY_MS, stale))
    w.desk.stale(other["source_id"])
    # A deck whose source revision no longer exists (written with the foreign keys off, as a damaged store might be).
    w.conn.execute("PRAGMA foreign_keys=OFF")
    gone = new_id("dek")
    w.conn.execute("INSERT INTO study_decks VALUES (?,?,?,?,?)",
                   (gone, new_id("aid"), w.source["source_id"], 99, "fsrs"))  # fmt: skip
    orphan = _card(w, gone, now - DAY_MS, like=deck)
    w.conn.execute("PRAGMA foreign_keys=ON")

    due = desk.state(now).study_due
    assert len(eligible) == 13 and len(due) == planner.STUDY_CARDS_MAX
    assert due == tuple((deck, card) for _, card in sorted(eligible)[: planner.STUDY_CARDS_MAX])
    suspended = {r[0] for r in w.conn.execute("SELECT card_id FROM study_flashcards WHERE deck_id = ?", (stale,))}
    assert suspended and not suspended & {c for _, c in due} and orphan not in {c for _, c in due}


# --- the planner (§19.4 planner.py) ------------------------------------------------------------------------------


def _cards(n: int) -> tuple[tuple[str, str], ...]:
    return tuple((f"dek_{'0' * 26}", f"fcd_{i:026d}") for i in range(n))


def _state(reviews: int, cards: int) -> PlannerState:
    kcs = {LESSON: KcPlanInfo(LESSON, "physics", "not_started", 0.2, 0.1)}
    due = [(f"kc.phy.o.fixture.k{i:02d}", i / 100) for i in range(reviews)]
    kcs.update({kc: KcPlanInfo(kc, "physics", "learning", 0.5, 0.01) for kc, _ in due})
    return PlannerState((SubjectInfo("physics", None),), kcs, tuple(due), study_due=_cards(cards))


def _reviews(proposal: planner.Plan) -> int:
    return sum(len(b.kc_ids) + len(b.study_cards) for b in proposal.blocks if b.kind == "warmup")


def test_the_warm_up_block_carries_study_cards_under_the_review_share() -> None:
    # Study cards follow the learner-model warm-up and fill what it leaves of the item cap (15).
    proposal = planner.plan(_state(12, 10), S)
    first, study, main = proposal.blocks
    assert (first.kind, first.reason_code, len(first.kc_ids), first.study_cards) == ("warmup", "due_reviews", 12, ())
    assert (study.kind, study.reason_code, study.kc_ids) == ("warmup", "due_reviews_study", ())
    assert study.study_cards == _cards(3) and study.minutes == planner.warmup_minutes(3, S)
    assert main.kind == "main" and _reviews(proposal) == S.review_cap_items
    assert study.payload() == {"kind": "warmup", "minutes": study.minutes, "reason_code": "due_reviews_study",
                               "study_cards": [{"deck_id": d, "card_id": c} for d, c in _cards(3)]}  # fmt: skip
    assert "study_cards" not in first.payload() and "study_cards" not in main.payload()
    # Alone, they lead the plan; a learner-model warm-up that fills the cap leaves no room for them.
    alone = planner.plan(_state(0, 10), S)
    assert [b.reason_code for b in alone.blocks] == ["due_reviews_study", "weak_high_value"]
    assert alone.blocks[0].study_cards == _cards(10)
    assert [b.reason_code for b in planner.plan(_state(20, 10), S).blocks] == ["due_reviews", "weak_high_value"]
    # Every due review asked for: all of the Study cards too.
    assert planner.plan(_state(20, 10), S, all_reviews=True).blocks[1].study_cards == _cards(10)
    # The stored plan reads back with its cards (a change keeps them).
    stored = planner.from_payload(proposal.payload("p", "2026-11-04"))
    assert stored.blocks == proposal.blocks
    # Across varied learners: the Study block changes nothing else, both warm-ups stay within the cap and the share.
    rng = random.Random(19)
    for _ in range(300):
        state = fixture_state(rng)
        without = planner.plan(state, S)
        with_cards = planner.plan(replace(state, study_due=_cards(rng.randint(0, 10))), S)
        assert replace(with_cards, blocks=tuple(b for b in with_cards.blocks
                                                if b.reason_code != "due_reviews_study")) == without  # fmt: skip
        warm = sum(b.minutes for b in with_cards.blocks if b.kind == "warmup")
        assert _reviews(with_cards) <= S.review_cap_items
        if with_cards.minutes > warm:
            assert warm <= S.review_cap_share * with_cards.minutes + 1e-9


# --- the event, the stored plan and the view (§19.4, §19.8 phase 2) ----------------------------------------------


def test_plan_generated_validates_with_study_cards(tmp_path: Path) -> None:
    w = world(tmp_path)
    deck = _deck(w, w.source["source_id"])
    cards = [{"deck_id": deck, "card_id": c} for (c,) in w.conn.execute(
        "SELECT card_id FROM study_flashcards WHERE deck_id = ? ORDER BY due_at, card_id", (deck,))]  # fmt: skip
    view = _desk(w).propose()
    study = [b for b in view["blocks"] if b.get("reason_code") == "due_reviews_study"]
    assert len(study) == 1 and study[0]["kind"] == "warmup" and study[0]["study_cards"] == cards
    assert errors("api/commands#/$defs/PlanView", view) == []
    assert "2 Study cards" in view["card"]["items"][study[0]["index"]]["text"]

    events = [e for e in w.learner.log.by_seq() if e.type == "plan_generated"]
    assert len(events) == 1
    block = next(b for b in events[0].payload["blocks"] if b.get("reason_code") == "due_reviews_study")
    assert block["study_cards"] == cards
    assert errors("learning/learning-event", events[0].envelope()) == []

    # The stored plan keeps the cards: a fresh desk on the same profile shows them, and a change carries them over.
    again = _desk(w).current()
    assert again is not None and again["plan_id"] == view["plan_id"]
    assert [b.get("study_cards") for b in again["blocks"]] == [b.get("study_cards") for b in view["blocks"]]
    assert errors("api/commands#/$defs/PlanView", again) == []
    order = list(reversed(range(len(view["blocks"]))))
    changed = _desk(w).change(view["plan_id"], order=order)
    assert [b.get("study_cards") for b in changed["blocks"]] == [view["blocks"][i].get("study_cards") for i in order]
    for event in w.learner.log.by_seq():
        if event.type == "plan_generated":
            assert errors("learning/learning-event", event.envelope()) == [], event.payload


def test_a_study_warm_up_completes_with_reviews_of_its_own_cards(tmp_path: Path) -> None:
    """The started plan's Study warm-up advances once per listed card reviewed in Study; practice never advances it
    (the plan projection, code version study_plans.2)."""
    w = world(tmp_path)
    deck = _deck(w, w.source["source_id"])
    view = _desk(w).propose()
    index, block = next((i, b) for i, b in enumerate(view["blocks"]) if b.get("reason_code") == "due_reviews_study")
    _desk(w).decide(view["plan_id"], "start")
    stored = lambda: _desk(w).current()["blocks"][index]  # noqa: E731
    assert (stored()["done"], stored()["target"]) == (0, len(block["study_cards"]))
    first = block["study_cards"][0]["card_id"]
    for _ in range(2):  # the same card reviewed twice counts once
        w.visits.card(first, "", "good")
    assert stored()["done"] == 1 and stored()["status"] != "done"
    for card in block["study_cards"][1:]:
        w.visits.card(card["card_id"], "", "good")
    assert stored()["status"] == "done" and stored()["done"] == len(block["study_cards"])
    assert deck
