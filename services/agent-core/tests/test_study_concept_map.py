"""Study concept maps on the device: a document's map comes through the Study queue's cloud path (scripted here, the
gateway's own tests cover Muse Spark's draft and verification) with every concept and relation cited to an exact
source quote; concepts anchor to the curated backbone by the pack's own records (glossary, statement, topic) or
stay "from your document"; batches merge by concept name; a typed topic is the pack's curated skills when it names
a pack topic and Muse Spark's uncited draft otherwise; the learner's edits (rename, remove, merge, add) are kept.
No model is asked on the device. Every learner is synthetic."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from agent_core.config import Settings
from agent_core.contracts import errors
from agent_core.engine.study import StudyDesk, StudyError, StudyQueue
from agent_core.engine.study_concepts import (
    ConceptEditError,
    anchor,
    apply_edits,
    document_map,
    merge_drafts,
    model_map,
    pack_map,
)
from agent_core.store.pack_index import PackIndex
from agent_core.store.sqlite import open_database
from jana_tools import REPO_ROOT
from pack_builder.build import load_source

NOW = 1792281600000
TEXT = (
    "Velocity is the speed of an object in a given direction. Acceleration is the rate of change of velocity. "
    "The gradient of a velocity-time graph gives the acceleration. A data logger records the speed of a "
    "trolley many times a second."
)
_CONTENT: list[PackIndex] = []


def content() -> PackIndex:
    if not _CONTENT:
        packs = []
        for subject in ("phy", "mth"):
            tables = load_source(REPO_ROOT / "content" / "curriculum" / subject / "o").tables
            packs.append(({"pack_id": f"pack.{subject}.o", "version": "0.1.0"}, tables))
        _CONTENT.append(PackIndex.from_tables(packs))
    return _CONTENT[0]


def span(chunk: dict[str, Any], quote: str) -> dict[str, Any]:
    start = chunk["text"].index(quote)
    return {
        "text": quote,
        "citations": [
            {
                "source_id": chunk["source_id"],
                "revision": chunk["revision"],
                "chunk_id": chunk["chunk_id"],
                "start": start,
                "end": start + len(quote),
                "quote": quote,
            }
        ],
    }


class Cloud:
    """The gateway as the device sees it: a verified concept map for each batch (STU cloud path)."""

    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []

    async def process(self, conn, jid, request, chunks, attempt, batch_index=0):
        self.requests.append(request)
        c = chunks[0]
        concepts = [
            {
                "concept_id": "c1",
                "name": "Velocity",
                "summary": span(c, "Velocity is the speed of an object in a given direction."),
            },
            {
                "concept_id": "c2",
                "name": "Acceleration",
                "summary": span(c, "Acceleration is the rate of change of velocity."),
            },
            {
                "concept_id": "c3",
                "name": "Data logger",
                "summary": span(c, "A data logger records the speed of a trolley many times a second."),
            },
        ]
        relations = [
            {
                "from": "c1",
                "to": "c2",
                "type": "builds_on",
                "claim": span(c, "Acceleration is the rate of change of velocity."),
            }
        ]
        draft = {"concepts": concepts, "relations": relations}
        claims = [x["summary"] for x in concepts] + [r["claim"] for r in relations]
        return {"request_id": jid, "kind": request["kind"], "claims": claims, "concept_map": draft}


def desk_at(path) -> StudyDesk:
    conn, _ = open_database(path / "learner.db", "learner")
    return StudyDesk(conn, lambda: NOW, Settings(study_offline_enabled=True))


def test_a_documents_concept_map_is_cited_anchored_and_labelled(tmp_path) -> None:
    d = desk_at(tmp_path)
    notes = d.create({"kind": "text", "title": "Motion notes", "text": TEXT})
    sources = [{"source_id": notes["source_id"], "revision": notes["revision"]}]
    job = d.create_job({"kind": "concept_map", "sources": sources, "execution": "prefer_cloud"})
    cloud = Cloud()
    queue = StudyQueue(lambda: d.conn, lambda: None, lambda: False, d.clock, d.settings)
    queue.cloud, queue.content = cloud, content
    asyncio.run(queue.run(d, job["job_id"]))
    done = d.job(job["job_id"])
    assert done["state"] == "completed", done
    aid = d.aid(done["result_ids"][0])
    assert errors("study/workspace#/$defs/Aid", aid) == []
    cmap = aid["concept_map"]
    by = {c["name"]: c for c in cmap["concepts"]}
    assert all(c["origin"] == "document" for c in cmap["concepts"])
    assert (
        by["Velocity"]["summary"]["citations"][0]["quote"] == "Velocity is the speed of an object in a given direction."
    )
    # Glossary terms anchor to curated KCs (the one sharing most words with the concept's text); none for a logger.
    assert by["Velocity"]["anchor"]["how"] == "glossary" and by["Velocity"]["anchor"]["kc_id"].startswith("kc.phy.o.")
    assert by["Acceleration"]["anchor"]["kc_id"] == "kc.phy.o.motion.acceleration_from_change"
    assert by["Data logger"]["anchor"] is None
    assert [(r["from"], r["to"], r["type"], r["origin"]) for r in cmap["relations"]] == [
        ("c1", "c2", "builds_on", "document")
    ]
    assert [c["text"] for c in aid["claims"]][:3] == [
        by[n]["summary"]["text"] for n in ("Velocity", "Acceleration", "Data logger")
    ]
    assert cloud.requests[0]["kind"] == "concept_map"


def test_a_concept_map_is_only_made_online_and_takes_one_source(tmp_path) -> None:
    d = desk_at(tmp_path)
    notes = d.create({"kind": "text", "title": "Motion notes", "text": TEXT})
    sources = [{"source_id": notes["source_id"], "revision": notes["revision"]}]
    with pytest.raises(StudyError):
        d.create_job({"kind": "concept_map", "sources": sources, "execution": "prefer_cloud", "prompt": "map it"})
    job = d.create_job({"kind": "concept_map", "sources": sources, "execution": "local"})
    queue = StudyQueue(lambda: d.conn, lambda: None, lambda: False, d.clock, d.settings)
    asyncio.run(queue.run(d, job["job_id"]))
    assert d.job(job["job_id"])["state"] == "failed"
    assert d.job(job["job_id"])["error"] == "model_unavailable"


def test_batches_merge_by_concept_name_with_relations_repointed() -> None:
    claim = {"text": "x", "citations": []}
    first = {
        "concepts": [
            {"concept_id": "c1", "name": "Velocity", "summary": claim},
            {"concept_id": "c2", "name": "Acceleration", "summary": claim},
        ],
        "relations": [{"from": "c1", "to": "c2", "type": "builds_on", "claim": claim}],
    }
    second = {
        "concepts": [
            {"concept_id": "c1", "name": "acceleration", "summary": claim},
            {"concept_id": "c2", "name": "Force", "summary": claim},
        ],
        "relations": [
            {"from": "c2", "to": "c1", "type": "causes", "claim": claim},
            {"from": "c1", "to": "c1", "type": "related_to", "claim": claim},
        ],
    }
    merged = merge_drafts([first, second, first])
    assert [(c["concept_id"], c["name"]) for c in merged["concepts"]] == [
        ("c1", "Velocity"),
        ("c2", "Acceleration"),
        ("c3", "Force"),
    ]
    assert [(r["from"], r["to"], r["type"]) for r in merged["relations"]] == [
        ("c1", "c2", "builds_on"),
        ("c3", "c2", "causes"),
    ]


def test_learner_edits_rename_remove_merge_and_add() -> None:
    quote = "Acceleration is the rate of change of velocity."
    cite = {
        "text": quote,
        "citations": [
            {
                "source_id": "src_" + "1" * 26,
                "revision": 1,
                "chunk_id": "sck_" + "2" * 26,
                "start": 0,
                "end": len(quote),
                "quote": quote,
            }
        ],
    }
    draft = {
        "concepts": [
            {"concept_id": "c1", "name": "Velocity", "summary": cite},
            {"concept_id": "c2", "name": "Acceleration", "summary": cite},
            {"concept_id": "c3", "name": "Rate of change of velocity", "summary": cite},
            {"concept_id": "c4", "name": "Data logger", "summary": cite},
        ],
        "relations": [
            {"from": "c1", "to": "c2", "type": "builds_on", "claim": cite},
            {"from": "c1", "to": "c3", "type": "builds_on", "claim": cite},
            {"from": "c4", "to": "c1", "type": "related_to", "claim": cite},
        ],
    }
    start = document_map(draft, content())
    edited = apply_edits(
        start,
        [
            {"op": "rename", "concept_id": "c1", "name": "Velocity (speed with direction)"},
            {"op": "remove", "concept_id": "c4"},
            {"op": "merge", "concept_ids": ["c2", "c3"], "name": "Acceleration"},
            {"op": "add", "name": "Gradient", "link_to": "m1"},
        ],
        content(),
    )
    assert edited["edited"] is True
    names = [(c["concept_id"], c["name"], c["origin"]) for c in edited["concepts"]]
    assert names == [
        ("c1", "Velocity (speed with direction)", "document"),
        ("m1", "Acceleration", "document"),
        ("u1", "Gradient", "learner"),
    ]
    merged = edited["concepts"][1]
    assert merged["merged_from"] == ["c2", "c3"] and merged["summary"] == cite, "a merge keeps the first cited summary"
    # The two links into the merged concept become one; the removed concept's link goes with it.
    assert [(r["from"], r["to"], r["origin"]) for r in edited["relations"]] == [
        ("c1", "m1", "document"),
        ("u1", "m1", "learner"),
    ]
    added = edited["concepts"][2]
    assert added["summary"] is None and added["anchor"]["how"] == "glossary", "an added concept is anchored by name"
    assert errors("study/workspace#/$defs/StudyConceptMap", edited) == []
    for bad in (
        [{"op": "remove", "concept_id": "c9"}],
        [{"op": "merge", "concept_ids": ["c1", "c9"], "name": "x"}],
        [{"op": "add", "name": "x", "link_to": "c9"}],
    ):
        with pytest.raises(ConceptEditError):
            apply_edits(start, bad)
    assert start["edited"] is False and len(start["concepts"]) == 4, "a refused edit changes nothing"


def test_a_typed_topic_is_the_packs_curated_skills_or_an_uncited_draft() -> None:
    node_id, cmap = pack_map(content(), "motion in a straight line") or ("", {})
    assert node_id == "cur.phy.o.motion_forces_and_energy.motion"
    assert cmap["concepts"] and all(
        c["origin"] == "pack" and c["anchor"] and c["summary"] is None for c in cmap["concepts"]
    )
    by_kc = {c["anchor"]["kc_id"]: c["concept_id"] for c in cmap["concepts"]}
    vt = by_kc["kc.phy.o.motion.velocity_time_gradient"]
    assert any(r["to"] == vt and r["type"] == "builds_on" and r["origin"] == "pack" for r in cmap["relations"])
    assert errors("study/workspace#/$defs/StudyConceptMap", cmap) == []
    assert pack_map(content(), "the history of jazz") is None
    drafted = {
        "request_id": "req_" + "0" * 26,
        "concepts": [
            {"concept_id": "c1", "name": "Acceleration", "note": "How fast velocity changes."},
            {"concept_id": "c2", "name": "Swing rhythm", "note": "An uneven long-short beat."},
        ],
        "relations": [{"from": "c1", "to": "c2", "type": "related_to"}, {"from": "c1", "to": "c9", "type": "causes"}],
    }
    model = model_map(drafted, content())
    assert [(c["origin"], c["summary"], bool(c["anchor"])) for c in model["concepts"]] == [
        ("model", None, True),
        ("model", None, False),
    ]
    assert [(r["from"], r["to"], r["claim"]) for r in model["relations"]] == [("s1", "s2", None)]
    assert anchor(None, "Acceleration") is None and anchor(content(), "") is None


def test_topic_maps_and_edits_over_the_api(tmp_path) -> None:
    """POST, GET, list and PATCH of a typed topic's map, and PATCH of a document map, through the real routes."""
    from api_harness import cli, start_core, stop_core
    from test_m10a_profiles import Api, student
    from test_m13g_learn import install

    async def scenario() -> None:
        install(tmp_path, "phy")
        r = await start_core(
            tmp_path,
            settings=Settings(
                worker_pool_size=1,
                worker_respawn_backoff_s=(0.0,),
                api_command_burst_per_s=1000,
                study_workspace_enabled=True,
            ),
            worker=False,
        )
        try:
            r.core.study.content = r.runtime.content  # as the app wires it (api/__main__.py)
            api = Api(r)
            token = (await api.unlock(await api.add(student("Ama")))).json()["profile_token"]

            async def send(method: str, path: str, body: Any = None) -> Any:
                return await api.call(method, path, body, profile=token, headers={"idempotency-key": cli()})

            async def get(path: str) -> Any:
                return await api.call("GET", path, profile=token)

            made = await send(
                "POST", "/v1/study/concept-maps", {"topic": "Motion in a straight line", "execution": "local"}
            )
            assert made.status_code == 200, made.text
            record = made.json()
            assert errors("study/workspace#/$defs/ConceptTopicMap", record) == []
            assert record["origin"] == "pack" and record["node_id"] == "cur.phy.o.motion_forces_and_energy.motion"
            first = record["concept_map"]["concepts"][0]["concept_id"]
            edited = await send(
                "PATCH",
                f"/v1/study/concept-maps/{record['map_id']}",
                {"ops": [{"op": "rename", "concept_id": first, "name": "My first idea"}]},
            )
            assert edited.status_code == 200, edited.text
            again = await get(f"/v1/study/concept-maps/{record['map_id']}")
            assert again.json()["concept_map"]["concepts"][0]["name"] == "My first idea"
            assert again.json()["concept_map"]["edited"] is True
            listed = await get("/v1/study/concept-maps")
            assert [m["map_id"] for m in listed.json()["maps"]] == [record["map_id"]]
            # No pack topic and no cloud: offline is refused, never an unlabelled guess.
            none = await send("POST", "/v1/study/concept-maps", {"topic": "the history of jazz", "execution": "local"})
            assert none.status_code == 422 and none.json()["error"]["details"]["reason"] == "model_unavailable"
            missing = await send(
                "PATCH", "/v1/study/concept-maps/ctm_" + "0" * 26, {"ops": [{"op": "remove", "concept_id": "k1"}]}
            )
            assert missing.status_code == 404
        finally:
            await stop_core(r)

    asyncio.run(scenario())
