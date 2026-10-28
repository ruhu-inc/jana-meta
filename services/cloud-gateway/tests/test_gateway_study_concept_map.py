"""The Study concept map (`concept_map`): the gateway narrows Muse Spark's structured output to concepts and typed
relations, each with a citation to a source passage; the verifier checks every concept and relation on its own
citations; only verified concepts, and relations whose two ends were kept, reach the device, with exact frozen quotes.
Provider outputs are scripted, never a model-quality claim."""

import asyncio
import hashlib
import json

from gateway_stubs import Device, Output, gateway_config, harness
from jsonschema import Draft202012Validator

JID = "stj_" + "0" * 26
SID = "src_" + "1" * 26
CID = "sck_" + "2" * 26
TEXT = (
    "Velocity is the rate of change of displacement. Acceleration is the rate of change of velocity. "
    "The gradient of a velocity-time graph gives the acceleration."
)


def cite(text: str) -> dict:
    return {"text": text, "citations": [{"passage_id": "p0"}]}


def payload() -> dict:
    chunk = {
        "chunk_id": CID,
        "source_id": SID,
        "revision": 1,
        "ordinal": 0,
        "locator": {"kind": "page", "page": 3},
        "text": TEXT,
        "sha256": hashlib.sha256(TEXT.encode()).hexdigest(),
    }
    return {"request_id": JID, "kind": "concept_map", "chunks": [chunk], "output_locale": "en"}


def draft() -> dict:
    concepts = [
        {"concept_id": "c1", "name": "Velocity", "summary": cite("Velocity is the rate of change of displacement.")},
        {
            "concept_id": "c2",
            "name": "Acceleration",
            "summary": cite("Acceleration is the rate of change of velocity."),
        },
        {"concept_id": "c3", "name": "Jerk", "summary": cite("Jerk is the rate of change of acceleration.")},
    ]
    relations = [
        {
            "from": "c1",
            "to": "c2",
            "type": "builds_on",
            "claim": cite("Acceleration is the rate of change of velocity."),
        },
        {"from": "c2", "to": "c1", "type": "causes", "claim": cite("Acceleration causes velocity.")},
        {"from": "c2", "to": "c3", "type": "builds_on", "claim": cite("Jerk builds on acceleration.")},
    ]
    claims = [c["summary"] for c in concepts] + [r["claim"] for r in relations]
    return {
        "request_id": JID,
        "kind": "concept_map",
        "claims": claims,
        "concept_map": {"concepts": concepts, "relations": relations},
    }


def verdict(concepts: list[bool], relations: list[bool]) -> dict:
    return {
        "reason": "Synthetic check",
        "safe": True,
        "answerable": True,
        "supported": all(concepts + relations),
        "repairable": False,
        "claim_support": concepts + relations,
        "concept_support": concepts,
        "relation_support": relations,
    }


def test_concept_map_schema_requires_cited_concepts_and_typed_relations():
    from cloud_gateway.study import generation_schema

    schema = generation_schema("concept_map", JID, passage_ids=["p0"])
    assert "concept_map" in schema["required"]
    assert not {"quiz", "flashcards", "chapters"} & set(schema["properties"])
    assert Draft202012Validator(schema).is_valid(draft())
    bad = draft()
    bad["concept_map"]["relations"][0]["type"] = "is_like"
    assert not Draft202012Validator(schema).is_valid(bad)
    uncited = draft()
    uncited["concept_map"]["concepts"][0]["summary"]["citations"] = [{"passage_id": "p9"}]
    assert not Draft202012Validator(schema).is_valid(uncited), "a citation names a passage of this request only"
    assert "concept_map" not in generation_schema("notes", JID, passage_ids=["p0"])["properties"]


def test_only_verified_concepts_and_relations_with_both_ends_reach_the_device(tmp_path):
    async def run():
        h = harness(gateway_config(tmp_path))
        device = Device()
        await device.login(h.client)
        # Jerk is not in the source; the reversed "causes" relation is not stated. The relation to Jerk goes with it.
        h.stubs["meta"].say(
            Output(text=json.dumps(draft())), Output(text=json.dumps(verdict([True, True, False], [True, False, True])))
        )
        reply = await h.client.post("/v1/study/process", json=payload(), headers=device.headers())
        assert reply.status_code == 200, reply.text
        result = reply.json()
        kept = result["concept_map"]
        assert [c["name"] for c in kept["concepts"]] == ["Velocity", "Acceleration"]
        assert [(r["from"], r["to"], r["type"]) for r in kept["relations"]] == [("c1", "c2", "builds_on")]
        assert [c["text"] for c in result["claims"]] == [
            "Velocity is the rate of change of displacement.",
            "Acceleration is the rate of change of velocity.",
            "Acceleration is the rate of change of velocity.",
        ]
        citation = kept["concepts"][1]["summary"]["citations"][0]
        assert citation["quote"] == TEXT and citation["source_id"] == SID and citation["chunk_id"] == CID
        # The draft call asked for the concept map's schema; the verifier for one flag per concept and relation.
        drafted, checked = h.stubs["meta"].seen[-2:]
        assert "concept_map" in drafted.schema["required"]
        assert "builds_on" in json.dumps(drafted.schema) and "concept_support" in checked.system
        assert {"concept_support", "relation_support"} <= set(checked.schema["required"])

    asyncio.run(run())


def test_a_concept_map_with_no_verified_concept_is_withheld(tmp_path):
    async def run():
        h = harness(gateway_config(tmp_path))
        device = Device()
        await device.login(h.client)
        h.stubs["meta"].say(
            Output(text=json.dumps(draft())), Output(text=json.dumps(verdict([False] * 3, [False] * 3)))
        )
        reply = await h.client.post("/v1/study/process", json=payload(), headers=device.headers())
        assert reply.status_code == 422 and "concept_map" not in reply.json()

    asyncio.run(run())


TOPIC_REQ = "req_" + "3" * 26


def test_a_typed_topic_gets_one_uncited_concept_map_call_settled_once(tmp_path):
    async def run():
        h = harness(gateway_config(tmp_path))
        device = Device()
        await device.login(h.client)
        topic = {
            "request_id": TOPIC_REQ,
            "concepts": [
                {
                    "concept_id": "c1",
                    "name": "Refraction",
                    "note": "Light changes direction as it enters a new medium.",
                },
                {"concept_id": "c2", "name": "Refractive index", "note": "How much a material slows light."},
            ],
            "relations": [{"from": "c1", "to": "c2", "type": "related_to"}],
        }
        h.stubs["meta"].say(Output(text=json.dumps(topic)))
        reply = await h.client.post(
            "/v1/study/concept-topic", json={"request_id": TOPIC_REQ, "topic": "refraction"}, headers=device.headers()
        )
        assert reply.status_code == 200, reply.text
        result = reply.json()
        assert [c["name"] for c in result["concepts"]] == ["Refraction", "Refractive index"]
        assert "citations" not in json.dumps(result) and result["usage"]["receipt_id"]
        (seen,) = h.stubs["meta"].seen
        assert "no source document" in seen.system and "refraction" in seen.user_texts[0]
        # The same attempt is never sent twice; a relation to an unknown concept is withheld.
        again = await h.client.post(
            "/v1/study/concept-topic", json={"request_id": TOPIC_REQ, "topic": "refraction"}, headers=device.headers()
        )
        assert again.status_code == 409
        broken = {**topic, "request_id": "req_" + "4" * 26, "relations": [{"from": "c1", "to": "c9", "type": "causes"}]}
        h.stubs["meta"].say(Output(text=json.dumps(broken)))
        bad = await h.client.post(
            "/v1/study/concept-topic",
            json={"request_id": "req_" + "4" * 26, "topic": "refraction"},
            headers=device.headers(),
        )
        assert bad.status_code == 422

    asyncio.run(run())
