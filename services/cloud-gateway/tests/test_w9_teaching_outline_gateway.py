"""SPEC §20.4 (W9): `teaching_outline` at the gateway. The generation schema narrows Muse Spark's structured output to
the cited part of the outline (no moments, skills, skips or bands: those are the device's); the prompt carries the
outline paragraph; the claims are the outline's items by code; the verifier checks each item on its own citation and
an unsupported item is dropped from the outline the device receives. Provider outputs are scripted."""

import asyncio
import hashlib
import json

from gateway_stubs import Device, Output, gateway_config, harness
from jsonschema import Draft202012Validator

JID = "stj_" + "0" * 26
SID = "src_" + "1" * 26
CID = "sck_" + "2" * 26
TEXT = (
    "[3:50] now let's derive how far the ball travels before it lands\n"
    "[4:12] substituting the time of flight gives the range equation R equals u squared sin two theta over g\n"
    "[4:21] notice the range depends on sin two theta"
)


def cite(text: str | None = None, name: str | None = None) -> dict:
    item: dict = {"citations": [{"passage_id": "p0"}]}
    if name is not None:
        item["name"] = name
    else:
        item["text"] = text
    return item


def payload() -> dict:
    chunk = {"chunk_id": CID, "source_id": SID, "revision": 1, "ordinal": 0,
             "locator": {"kind": "time", "start_ms": 230_000, "end_ms": 400_000}, "text": TEXT,
             "sha256": hashlib.sha256(TEXT.encode()).hexdigest()}  # fmt: skip
    return {"request_id": JID, "kind": "teaching_outline", "chunks": [chunk], "output_locale": "en"}


def draft() -> dict:
    outline = {
        "objectives": [cite("derive the range equation for a launch from level ground")],
        "examples": [],
        "concepts": [cite(name="Range"), cite(name="Air resistance")],
        "assumes": [cite("the learner knows sin two theta")],
    }
    claims = [cite("derive the range equation for a launch from level ground"), cite("Range"), cite("Air resistance"),
              cite("the learner knows sin two theta")]  # fmt: skip
    return {"request_id": JID, "kind": "teaching_outline", "claims": claims, "outline": outline}


def verdict(flags: list[bool]) -> dict:
    return {"reason": "Synthetic check", "safe": True, "answerable": True, "supported": all(flags),
            "repairable": False, "claim_support": flags}  # fmt: skip


def test_the_outline_schema_asks_for_the_cited_part_only():
    from cloud_gateway.study import GRANULAR_KINDS, generation_schema

    assert "teaching_outline" in GRANULAR_KINDS
    schema = generation_schema("teaching_outline", JID, passage_ids=["p0"])
    assert "outline" in schema["required"]
    assert not {"quiz", "flashcards", "chapters", "concept_map"} & set(schema["properties"])
    outline = schema["properties"]["outline"]  # the definitions are inlined for structured output
    assert not {"skips", "for_you"} & set(outline["properties"])
    concept = outline["properties"]["concepts"]["items"]["properties"]
    assert not {"at_ms", "kc_ids", "outside_packs"} & set(concept)
    assert "at_ms" not in outline["properties"]["objectives"]["items"]["properties"]
    assert Draft202012Validator(schema).is_valid(draft())
    uncited = draft()
    uncited["outline"]["concepts"][0]["citations"] = [{"passage_id": "p9"}]
    assert not Draft202012Validator(schema).is_valid(uncited)
    assert "outline" not in generation_schema("notes", JID, passage_ids=["p0"])["properties"]


def test_the_verifier_drops_an_uncited_item_and_the_claims_are_the_items(tmp_path):
    async def run():
        h = harness(gateway_config(tmp_path))
        device = Device()
        await device.login(h.client)
        # "Air resistance" is not in the lecture's words: its item goes; the rest stay, in order.
        h.stubs["meta"].say(
            Output(text=json.dumps(draft())), Output(text=json.dumps(verdict([True, True, False, True])))
        )
        reply = await h.client.post("/v1/study/process", json=payload(), headers=device.headers())
        assert reply.status_code == 200, reply.text
        result = reply.json()
        outline = result["outline"]
        assert [c["name"] for c in outline["concepts"]] == ["Range"]
        assert [o["text"] for o in outline["objectives"]] == [
            "derive the range equation for a launch from level ground"
        ]
        assert [a["text"] for a in outline["assumes"]] == ["the learner knows sin two theta"]
        assert [c["text"] for c in result["claims"]] == [
            "derive the range equation for a launch from level ground",
            "Range",
            "the learner knows sin two theta",
        ]
        citation = outline["concepts"][0]["citations"][0]
        assert citation["quote"] == TEXT and citation["chunk_id"] == CID and citation["source_id"] == SID
        # No moment, skill, skip or band came from the gateway: the device fills them.
        assert not any(k in outline["concepts"][0] for k in ("at_ms", "kc_ids", "outside_packs"))
        assert "skips" not in outline and "for_you" not in outline
        drafted, checked = h.stubs["meta"].seen[-2:]
        assert "Say what this lecture teaches, in its order" in drafted.system
        assert "Never add what the lecture does not say" in drafted.system
        assert "one boolean per item in order (objectives, worked examples" in checked.system
        assert checked.schema is not None and checked.schema["properties"]["claim_support"]["minItems"] == 4
        # The request carried transcript chunks and nothing else: no learner block, no syllabus.
        assert "learner" not in drafted.body["messages"][1]["content"] or "kcs" not in drafted.user_texts[0]

    asyncio.run(run())


def test_an_outline_with_no_supported_item_is_refused(tmp_path):
    async def run():
        h = harness(gateway_config(tmp_path))
        device = Device()
        await device.login(h.client)
        h.stubs["meta"].say(Output(text=json.dumps(draft())), Output(text=json.dumps(verdict([False] * 4))),
                            Output(text=json.dumps(draft())),
                            Output(text=json.dumps(verdict([False] * 4))))  # fmt: skip
        reply = await h.client.post("/v1/study/process", json=payload(), headers=device.headers())
        assert reply.status_code == 422, reply.text
        assert reply.json()["error"]["code"] == "insufficient_evidence"

    asyncio.run(run())


def long_draft() -> dict:
    long = draft()
    too_long = "derive the range equation " + "in a great many words " * 12
    long["outline"]["objectives"].append(cite(too_long))
    long["claims"].append(cite(too_long))
    return long


def test_a_draft_that_runs_long_gets_the_reserved_second_draft_with_the_limits(tmp_path):
    """The outline refused on the 2 November rehearsal (`draft_response_maxLength`): told the limits, it comes back."""

    async def run():
        h = harness(gateway_config(tmp_path))
        device = Device()
        await device.login(h.client)
        h.stubs["meta"].say(Output(text=json.dumps(long_draft())), Output(text=json.dumps(draft())),
                            Output(text=json.dumps(verdict([True] * 4))))  # fmt: skip
        reply = await h.client.post("/v1/study/process", json=payload(), headers=device.headers())
        assert reply.status_code == 200, reply.text
        assert len(reply.json()["outline"]["objectives"]) == 1
        second = repr(h.stubs["meta"].seen[1])
        assert "ran past its limit" in second

    asyncio.run(run())


def test_a_second_long_draft_keeps_its_whole_items_and_drops_the_long_one(tmp_path):
    async def run():
        h = harness(gateway_config(tmp_path))
        device = Device()
        await device.login(h.client)
        h.stubs["meta"].say(Output(text=json.dumps(long_draft())), Output(text=json.dumps(long_draft())),
                            Output(text=json.dumps(verdict([True] * 4))))  # fmt: skip
        reply = await h.client.post("/v1/study/process", json=payload(), headers=device.headers())
        assert reply.status_code == 200, reply.text
        assert [o["text"] for o in reply.json()["outline"]["objectives"]] == [
            "derive the range equation for a launch from level ground"
        ]

    asyncio.run(run())


def marking() -> dict:
    return {"request_id": "req_" + "0" * 26, "item_type": "fill_blank", "question": "The time of flight is ____.",
            "answer": "2u sin theta / g", "reference": "T = 2u sin(theta)/g", "passages": [TEXT],
            "output_locale": "en"}  # fmt: skip


def test_a_written_answer_is_marked_online_only_when_the_judge_and_the_check_agree(tmp_path):
    async def run():
        h = harness(gateway_config(tmp_path))
        device = Device()
        await device.login(h.client)
        h.stubs["meta"].say(Output(text=json.dumps({"verdict": "correct"})),
                            Output(text=json.dumps({"verdict": "entailed"})))  # fmt: skip
        reply = await h.client.post("/v1/study/mark", json=marking(), headers=device.headers())
        assert reply.status_code == 200, reply.text
        assert reply.json()["verdict"] == "correct"
        checker = repr(h.stubs["meta"].seen[1])
        assert "2u sin(theta)/g" not in checker  # the separate check never sees the reference answer
        h.stubs["meta"].say(Output(text=json.dumps({"verdict": "correct"})),
                            Output(text=json.dumps({"verdict": "unknown"})))  # fmt: skip
        again = await h.client.post("/v1/study/mark", json={**marking(), "request_id": "req_" + "1" * 26},
                                    headers=device.headers())  # fmt: skip
        assert again.json()["verdict"] == "unverifiable"

    asyncio.run(run())


def test_agreement_rules_never_turn_a_disagreement_into_a_verdict():
    from cloud_gateway.study import agreed_verdict

    assert agreed_verdict("correct", "entailed") == "correct"
    assert agreed_verdict("incorrect", "contradicted") == "incorrect"
    assert agreed_verdict("partial", "unknown") == "partial"
    assert agreed_verdict("partial", "contradicted") == "unverifiable"
    assert agreed_verdict("correct", "contradicted") == "unverifiable"
    assert agreed_verdict("incorrect", "entailed") == "unverifiable"
    assert agreed_verdict("incorrect", "unknown") == "incorrect"  # off target, and nothing supports it
    assert agreed_verdict("correct", "unknown") == "unverifiable"


def test_a_transcript_line_can_be_the_prerequisite_a_hint_offers():
    """A recall question from a lecture had no cue at all: transcript lines have no capitals or full stops, so every
    hint fell back to general strategy (the 1 November rehearsal). A line that gives the answer away is left out."""
    from cloud_gateway.study import coaching_cues

    quote = (
        "[0:48] start with a ball launched at speed u at an angle theta above the horizontal\n"
        "[0:55] I assume you already know how to resolve a vector into perpendicular components\n"
        "[1:02] the horizontal component of the velocity is u cos theta\n"
    )
    body = {"kind": "chat", "prompt": "Give me one short hint", "settings": {"focus": "Coaching withheld wording: "
            '["horizontal component of the velocity is u cos theta"]'}}  # fmt: skip
    texts = [c["text"] for c in coaching_cues(body, [{"passage_id": "p0", "quote": quote}])]
    assert "I assume you already know how to resolve a vector into perpendicular components." in texts
    assert not any("0:55" in t for t in texts)
