"""Trace the real gap: a wrong answer that matches a misconception the pack links to an earlier skill (its `root_gap`)
tells the student in one line what the mistake is really about, and accepting routes the next practice to that skill
(LRN-23's detour, then back to the problem at the same step). The engine runs for real with scripted model outputs;
the items, misconceptions and the Maths prerequisite are the repository's own pack sources."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from agent_core.engine import offers
from agent_core.retrieval.index import KnowledgeIndex
from engine_harness import close, make_engine, reply, tutor
from jana_tools import REPO_ROOT
from pack_builder.build import load_source

CURRICULUM = REPO_ROOT / "content" / "curriculum"
OHM = "itm.phy.o.electrical_quantities.0057"  # R from 0.8 V and 100 mA; option A is R = I/V
REARRANGING = "kc.mth.o.algebra_and_graphs.change_subject"
LOOP = asyncio.new_event_loop()
SOURCES: dict[str, Any] = {}


def run(coro: Any) -> Any:
    return LOOP.run_until_complete(coro)


def tables(subject: str) -> dict[str, list[dict[str, Any]]]:
    if subject not in SOURCES:
        source = load_source(CURRICULUM / subject / "o")
        SOURCES[subject] = (dict(source.pack), {t: list(rows) for t, rows in source.tables.items()})
    return SOURCES[subject][1]


def knowledge() -> KnowledgeIndex:
    tables("phy"), tables("mth")
    return KnowledgeIndex.from_tables([SOURCES["phy"], SOURCES["mth"]])


class Detours:
    """The detour's reads over the installed packs, with every prerequisite strong (so LRN-23's own policy, which
    waits for two failures and a weak prerequisite, would offer nothing here)."""

    def __init__(self) -> None:
        self.items_by_kc = [i for s in ("phy", "mth") for i in tables(s)["items"]]
        self.kcs = {k["id"]: k for s in ("phy", "mth") for k in tables(s)["kcs"]}

    def prerequisites(self, kc_ids: Any) -> dict[str, dict[str, float]]:
        return {kc: {p["kc_id"]: 0.9 for p in self.kcs[kc].get("prerequisites", [])} for kc in kc_ids if kc in self.kcs}

    def items(self, kc_id: str, count: int) -> list[dict[str, Any]]:
        found = [i for i in self.items_by_kc if kc_id in i["kc_ids"] and len(i["parts"]) == 1
                 and i["type"] != "mcq_diagnostic"]  # fmt: skip
        return found[:count]

    def statement(self, kc_id: str) -> str | None:
        kc = self.kcs.get(kc_id)
        return None if kc is None else str(kc["statement"])


def _diagnosis() -> dict[str, Any]:
    return reply(json.dumps({"in_scope": True, "subject": "physics", "topic_ref": None, "kc_refs": [],
                             "question_kind": "calculation", "knowns": [], "unknowns": [],
                             "clarifying_question": None, "misconception_ref": None, "evidence": [], "inference": "",
                             "prerequisite_gap_refs": [], "confidence": "medium"}))  # fmt: skip


def cards(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [e for e in events if e["type"] == "card.open"]


def test_the_misconceptions_pack_link_is_in_the_index() -> None:
    record = knowledge().misconceptions["mc.phy.o.ohm_law_upside_down"]
    assert (record.root_kc_id, record.root_idea) == (REARRANGING, "rearranging equations")
    assert knowledge().misconceptions["mc.phy.o.milliamps_used_as_amps"].root_kc_id is None


def test_root_gap_said_in_one_line_and_next_practice_on_the_prerequisite(tmp_path: Path) -> None:
    item = next(i for i in tables("phy")["items"] if i["id"] == OHM)
    notes: list[str] = []

    def coach(body: dict[str, Any]) -> dict[str, Any]:
        notes.append("\n".join(str(m["content"]) for m in body["messages"]))
        return tutor("Look again at which quantity goes on top.")

    script = {"diagnoser": [_diagnosis()], "coach": [coach, coach, coach]}

    async def scenario() -> tuple[Any, list[dict[str, Any]], list[dict[str, Any]]]:
        engine, _ = await make_engine(tmp_path, script)
        engine.deps.stage = "S2"
        engine.bind_knowledge(knowledge())
        engine.detours = Detours()
        await engine.start_practice(item)
        before = len(engine.events.frames)
        await engine.student_turn("A")  # R = I/V: the upside-down rearrangement
        wrong = [f["event"] for f in engine.events.frames[before:]]
        (card,) = cards(wrong)
        accept = next(o["id"] for o in card["card"]["options"] if o["label"].startswith("Practise"))
        choice, offer = offers.answered(engine, card["request_id"], {"option_ids": [accept]}) or ("", {})
        assert choice == "detour"
        before = len(engine.events.frames)
        await engine.accept_offer(choice, offer, "Practise rearranging equations first")
        routed = [f["event"] for f in engine.events.frames[before:]]
        await close(engine)
        return engine, wrong, routed

    engine, wrong, routed = run(scenario())
    (card,) = cards(wrong)
    assert card["card"]["prompt"] == "This is really about rearranging equations."
    labels = [o["label"] for o in card["card"]["options"]]
    assert labels == ["Practise rearranging equations first", "Not now, I'll keep trying"]
    # The card says what it is about, so the concept map can light the gap path from the Maths skill.
    assert card["about"] == {
        "kind": "root_gap",
        "kc_id": item["kc_ids"][0],
        "root_kc_id": REARRANGING,
        "misconception_id": card["about"]["misconception_id"],
    }
    assert card["about"]["misconception_id"].startswith("mc.phy.o.")
    assert "this mistake is really about rearranging equations" in notes[1]  # the Coach does not repeat the line
    # The next practice is on the Maths prerequisite; the Ohm's law problem waits on the return stack.
    assert engine.state.detour["kc_id"] == REARRANGING
    assert REARRANGING in engine.state.practice["item"]["kc_ids"]
    assert engine.state.detour_stack[-1]["problem_ref"].startswith(OHM)
    assert any(e["type"] == "board.reset" for e in routed)


def test_root_gap_offered_once_and_a_decline_is_kept(tmp_path: Path) -> None:
    item = next(i for i in tables("phy")["items"] if i["id"] == OHM)
    script = {"diagnoser": [_diagnosis()], "coach": [tutor("Which quantity goes on top?")] * 3}

    async def scenario() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        engine, _ = await make_engine(tmp_path, script)
        engine.deps.stage = "S2"
        engine.bind_knowledge(knowledge())
        engine.detours = Detours()
        await engine.start_practice(item)
        before = len(engine.events.frames)
        await engine.student_turn("A")
        first = [f["event"] for f in engine.events.frames[before:]]
        (card,) = cards(first)
        decline = next(o["id"] for o in card["card"]["options"] if o["label"].startswith("Not now"))
        assert (offers.answered(engine, card["request_id"], {"option_ids": [decline]}) or ("",))[0] == "declined"
        before = len(engine.events.frames)
        await engine.student_turn("A")
        again = [f["event"] for f in engine.events.frames[before:]]
        await close(engine)
        return first, again

    first, again = run(scenario())
    assert len(cards(first)) == 1
    assert not [c for c in cards(again) if "really about" in c["card"]["prompt"]]


def test_a_misconception_without_a_link_offers_no_root_gap(tmp_path: Path) -> None:
    item = next(i for i in tables("phy")["items"] if i["id"] == OHM)
    script = {"diagnoser": [_diagnosis()], "coach": [tutor("Check the units of the current.")] * 2}

    async def scenario() -> list[dict[str, Any]]:
        engine, _ = await make_engine(tmp_path, script)
        engine.deps.stage = "S2"
        engine.bind_knowledge(knowledge())
        engine.detours = Detours()
        await engine.start_practice(item)
        before = len(engine.events.frames)
        await engine.student_turn("D")  # milliamps used as amps: no earlier skill is linked
        events = [f["event"] for f in engine.events.frames[before:]]
        await close(engine)
        return events

    assert not cards(run(scenario()))
