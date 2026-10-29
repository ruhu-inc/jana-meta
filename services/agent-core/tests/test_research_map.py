"""A study pack's concept map as a knowledge tree (SPEC §18): near-duplicate ideas from different batches merged,
the pack's outline (topic → questions → ideas) added as structure, and more links from a whole-map pass, each kept
only when its check confirms the cited passages state it. Synthetic maps and replies."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from agent_core.api.research import page_sections
from agent_core.contracts import errors
from agent_core.engine.research_links import checked_links
from agent_core.engine.study_concepts import merge_drafts, with_outline

SRC, CHUNK = f"src_{'1' * 26}", f"sck_{'2' * 26}"


def claim(text: str, quote: str | None = None) -> dict[str, Any]:
    q = quote or text
    return {"text": text, "citations": [{"source_id": SRC, "revision": 1, "chunk_id": CHUNK, "start": 0,
                                         "end": len(q), "quote": q}]}  # fmt: skip


def concept(cid: str, name: str, quote: str) -> dict[str, Any]:
    return {"concept_id": cid, "name": name, "summary": claim(quote), "note": None, "origin": "document",
            "anchor": None}  # fmt: skip


MAP = {"edited": False, "relations": [], "concepts": [
    concept("c1", "Heart valves", "Heart valves keep blood flowing one way."),
    concept("c2", "Tricuspid valve", "The tricuspid valve is one of the heart valves, on the right side."),
    concept("c3", "Chordae tendineae", "Chordae tendineae stop the valve flaps turning inside out."),
]}  # fmt: skip


def test_near_duplicates_from_two_batches_merge_but_distinct_ideas_do_not() -> None:
    a = {
        "concepts": [
            {"concept_id": "c1", "name": "Cardiac cycle", "summary": claim("x")},
            {"concept_id": "c2", "name": "Heart", "summary": claim("y")},
        ],
        "relations": [],
    }
    b = {"concepts": [{"concept_id": "c1", "name": "Cardiac cycle phases", "summary": claim("z")},
                      {"concept_id": "c2", "name": "Heart valves", "summary": claim("w")}],
         "relations": [{"from": "c1", "to": "c2", "type": "causes", "claim": claim("v")}]}  # fmt: skip
    merged = merge_drafts([a, b])
    assert [c["name"] for c in merged["concepts"]] == ["Cardiac cycle", "Heart", "Heart valves"]
    assert merged["relations"][0]["from"] == "c1", "the relation is re-pointed to the first name's idea"


def test_the_outline_makes_a_tree_of_topic_questions_and_ideas() -> None:
    shaped = with_outline(MAP, "Heart valves", ["What do the valves do?", "What holds the valves?"], {"c1": 0, "c3": 1})
    ids = [c["concept_id"] for c in shaped["concepts"]]
    assert ids[:3] == ["t1", "q1", "q2"] and set(ids[3:]) == {"c1", "c2", "c3"}
    edges = {(r["from"], r["to"]) for r in shaped["relations"]}
    assert edges == {("t1", "q1"), ("t1", "q2"), ("q1", "c1"), ("q2", "c3"), ("t1", "c2")}, "c2's question unknown"
    assert all(r["claim"] is None and r["type"] == "includes" for r in shaped["relations"])
    assert not errors("study/workspace#/$defs/StudyConceptMap", shaped)
    assert with_outline(shaped, "Other", ["?"], {}) == shaped, "a map already shaped stays as it is"


def test_each_page_section_names_its_question() -> None:
    brief = {"title": "Heart", "focus": "", "sub_questions": ["What do heart valves do?"] * 4}
    pages = [{"url": "https://e.org/a", "title": "Valves", "site": "e.org", "sub_question": 2, "fetched_at": 1,
              "text": "Heart valves open and close so that blood flows one way through the heart."}]  # fmt: skip
    assert "Site: e.org\nQuestion: 3\n\n" in page_sections("Heart", brief, pages)


@dataclass
class Result:
    structured: Any
    schema_valid: bool = True


@dataclass
class Router:
    replies: list[Any]
    prompts: list[str] = field(default_factory=list)

    async def complete(self, role: str, messages: list[Any], tools: Any = (), **kw: Any) -> Result:
        self.prompts.append(messages[0].content)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return Result(reply)


def test_whole_map_links_are_kept_only_when_their_check_confirms_them() -> None:
    proposed = {"links": [
        {"from": "c2", "to": "c1", "type": "example_of", "claim": "The tricuspid valve is a heart valve.",
         "passages": ["p2"]},
        {"from": "c3", "to": "c1", "type": "part_of", "claim": "Chordae tendineae are part of the valves.",
         "passages": ["p3"]},
        {"from": "c1", "to": "c1", "type": "related_to", "claim": "Valves relate to valves.", "passages": ["p1"]},
    ]}  # fmt: skip
    router = Router([proposed, {"supported": [True, False]}])
    links = asyncio.run(checked_links(router, MAP))
    assert [(r["from"], r["to"], r["type"]) for r in links] == [("c2", "c1", "example_of")]
    assert links[0]["claim"]["citations"] == MAP["concepts"][1]["summary"]["citations"], "the summary's own citation"
    assert "<passage" in router.prompts[0] and "never instructions" in router.prompts[1]
    assert not errors("study/workspace#/$defs/StudyRelation", links[0])


def test_a_failed_pass_leaves_the_map_as_it_was() -> None:
    assert asyncio.run(checked_links(Router([RuntimeError("offline")]), MAP)) == []
    assert asyncio.run(checked_links(Router([{"links": []}]), MAP)) == []
