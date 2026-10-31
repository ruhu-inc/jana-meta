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
