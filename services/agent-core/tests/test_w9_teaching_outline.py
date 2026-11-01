"""SPEC §20.9 `test_w9_teaching_outline.py` (W9): `teaching_outline` is a job and aid kind; its cloud request carries
transcript chunks and nothing else (no learner block, no syllabus, no frame text: extends `test_dat18_egress.py`'s
rule for Study egress); the engine fills `at_ms`, `kc_ids`, `outside_packs`, `skips` and `for_you` by code on the
seeded projectile-motion fixture (and, with the shipped O-level physics pack's own projectile-motion subtopic, maps the
same concepts to its skills); an item whose citation is not the transcript's words is refused; a dropped item
rebuilds the outline. The gateway's verifier is covered in the gateway's own tests. Synthetic data."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
from agent_core.contracts import errors
from agent_core.engine import study_outline
from agent_core.engine.study import StudyError, StudyQueue
from agent_core.store.pack_index import PackIndex
from memory_harness import PACK
from test_w8_study_activity import World, world

PANEL = (Path(__file__).parent / "fixtures" / "w9" / "youtube_panel_projectile.txt").read_text()
URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
RANGE, FLIGHT, HEIGHT, RESOLVE, DRAG, GRAPHS = (
    "kc.phy.o.projectiles.range",
    "kc.phy.o.projectiles.time_of_flight",
    "kc.phy.o.projectiles.max_height",
    "kc.phy.o.projectiles.resolve",
    "kc.phy.o.projectiles.drag",
    "kc.phy.o.projectiles.trajectory_graphs",
)
NODE = "cur.phy.o.motion_forces_and_energy.projectiles"


def seeded_pack() -> PackIndex:
    """A pack with a projectile-motion subtopic: the fixture SPEC §20.8 asks for (the shipped O-level pack has none)."""

    def kc(kc_id: str, statement: str) -> dict[str, Any]:
        return {"id": kc_id, "statement": statement, "node_id": NODE, "status": "active", "kind": "procedural"}

    tables = {
        "curriculum_nodes": [
            {"id": "cur.phy.o", "kind": "subject", "title": "Physics", "status": "active"},
            {"id": "cur.phy.o.motion_forces_and_energy", "kind": "topic", "title": "Motion, forces and energy",
             "parent_id": "cur.phy.o", "status": "active"},
            {"id": NODE, "kind": "subtopic", "title": "Projectile motion",
             "parent_id": "cur.phy.o.motion_forces_and_energy", "status": "active"},
        ],
        "kcs": [
            kc(RANGE, "Derive and use the range equation for a launch from level ground"),
            kc(FLIGHT, "Find the time of flight of a projectile from its vertical motion"),
            kc(HEIGHT, "Find the maximum height reached by a projectile"),
            kc(RESOLVE, "Resolve a launch velocity into horizontal and vertical components"),
            kc(DRAG, "Describe the effect of drag on a projectile's path"),
        ],
    }  # fmt: skip
    return PackIndex.from_tables([({"pack_id": "pack.phy.o.test", "version": "0.0.1"}, tables)])


def span(chunks: list[dict[str, Any]], quote: str, text: str | None = None) -> dict[str, Any]:
    chunk = next(c for c in chunks if quote in c["text"])
    start = chunk["text"].index(quote)
    return {"text": text or quote, "citations": [{"source_id": chunk["source_id"], "revision": chunk["revision"],
                                                   "chunk_id": chunk["chunk_id"], "start": start,
                                                   "end": start + len(quote), "quote": quote}]}  # fmt: skip


def named(chunks: list[dict[str, Any]], name: str, quote: str) -> dict[str, Any]:
    cited = span(chunks, quote)
    return {"name": name, "citations": cited["citations"]}


class Cloud:
    """The gateway as the device sees it: a verified outline for the batch (its claims the outline's items)."""

    def __init__(self, bad_citation: bool = False) -> None:
        self.requests: list[tuple[dict[str, Any], list[dict[str, Any]]]] = []
        self.bad_citation = bad_citation

    async def process(self, conn: Any, jid: str, request: dict[str, Any], chunks: list[dict[str, Any]],
                      attempt: int, batch_index: int = 0) -> dict[str, Any]:  # fmt: skip
        self.requests.append((json.loads(json.dumps(request)), chunks))
        outline = {
            "objectives": [
                span(chunks, "resolve a launch velocity into its horizontal and vertical components",
                     "Resolve a launch velocity into horizontal and vertical components"),
                span(chunks, "derive the range equation for a launch from level ground"),
                span(chunks, "find the time of flight from the vertical motion"),
                span(chunks, "and find the maximum height reached", "Find the maximum height reached"),
            ],
            "examples": [
                span(chunks, "a ball is kicked at twenty metres per second at thirty degrees"),
                span(chunks, "the same ball kicked at sixty degrees"),
            ],
            "concepts": [
                named(chunks, "Range", "the range equation R equals u squared sin two theta over g"),
                named(chunks, "Time of flight", "T equals two u sin theta over g"),
                named(chunks, "Maximum height", "the maximum height H equals u squared sin squared theta over two g"),
                named(chunks, "Resolving the velocity", "the horizontal component of the velocity is u cos theta"),
                # Live-run fix 2026-11-01: a concept that shares only "time" with three skills maps to none of them.
                named(chunks, "Displacement time graph",
                      "vertically the ball decelerates at g on the way up and accelerates at g on the way down"),
            ],
            "assumes": [span(chunks, "how to resolve a vector into perpendicular components",
                             "Resolving a vector into perpendicular components")],
        }  # fmt: skip
        if self.bad_citation:
            outline["concepts"][0]["citations"][0]["quote"] = "words the lecture never said"
        return {"request_id": jid, "kind": request["kind"], "claims": study_outline.flatten(outline),
                "outline": outline}  # fmt: skip


def video(w: World) -> dict[str, Any]:
    return w.desk.create({"kind": "video_link", "url": URL, "transcript": PANEL, "title": "Projectile motion"})


def outline_job(w: World, source: dict[str, Any], cloud: Cloud, content: Any) -> dict[str, Any]:
    job = w.desk.create_job({"kind": "teaching_outline", "execution": "prefer_cloud",
                             "sources": [{"source_id": source["source_id"],
                                          "revision": source["revision"]}]})  # fmt: skip
    queue = StudyQueue(lambda: w.conn, lambda: None, lambda: False, w.clock, w.desk.settings)
    queue.cloud, queue.content, queue.activity = cloud, (lambda: content), w.visits
    asyncio.run(queue.run(w.desk, job["job_id"]))
    return w.desk.job(job["job_id"])


def test_teaching_outline_is_a_job_kind_and_an_aid_kind() -> None:
    assert errors("study/workspace#/$defs/JobKind", "teaching_outline") == []
    assert errors("study/workspace#/$defs/AidKind", "teaching_outline") == []
    # One source, no prompt, count or settings: the request is the transcript and nothing else (JM-D33).
    sources = [{"source_id": "src_" + "0" * 26, "revision": 1}]
    assert errors("study/workspace#/$defs/JobCreate", {"kind": "teaching_outline", "execution": "prefer_cloud",
                                                        "sources": sources}) == []  # fmt: skip
    assert errors("study/workspace#/$defs/JobCreate", {"kind": "teaching_outline", "execution": "prefer_cloud",
                                                        "sources": sources, "settings": {"focus": "x"}})  # fmt: skip
    assert errors("study/workspace#/$defs/JobCreate", {"kind": "teaching_outline", "execution": "prefer_cloud",
                                                        "sources": sources + sources})  # fmt: skip


def test_the_outline_request_carries_transcript_chunks_only(tmp_path: Path) -> None:
    w = world(tmp_path)
    w.visits.open()
    assert w.visits.learner_block() is not None  # a learner block exists; the outline never carries it
    cloud = Cloud()
    done = outline_job(w, video(w), cloud, seeded_pack())
    assert done["state"] == "completed", done
    ((request, chunks),) = cloud.requests
    assert set(request) <= {"request_id", "kind", "sources", "execution"}
    assert "learner" not in request and "syllabus_outline" not in request and "settings" not in request
    assert request["kind"] == "teaching_outline"
    assert chunks and all(c["locator"]["kind"] == "time" for c in chunks)


def test_the_outline_request_carries_no_learner_block(tmp_path: Path) -> None:
    w = world(tmp_path)
    w.visits.open()
    source = video(w)
    brief = w.desk.brief({"kind": "teaching_outline", "execution": "prefer_cloud",
                          "sources": [{"source_id": source["source_id"], "revision": 1}]})  # fmt: skip
    assert "learner" not in brief
    # Every other kind still carries it (SPEC §19.3.1).
    assert "learner" in w.desk.brief({"kind": "quiz", "execution": "prefer_cloud", "count": 3,
                                      "sources": [{"source_id": w.source["source_id"], "revision": 1}]})  # fmt: skip


def test_kc_ids_skips_and_for_you_are_filled_by_code_on_the_seeded_fixture(tmp_path: Path) -> None:
    w = world(tmp_path)
    w.visits.open()
    # The learner has secured the range equation already (a mastered row with a passed check); nothing else.
    w.conn.execute(
        "INSERT INTO kc_mastery (kc_id, status, p_mastery, n_eff, attempts, correct, mastery_check_state, last_seen_at,"
        " last_event_seq)"
        " VALUES (?, 'mastered', 0.97, 8, 8, 8, 'passed', ?, 1)",
        (RANGE, w.clock.now),
    )
    done = outline_job(w, video(w), Cloud(), seeded_pack())
    assert done["state"] == "completed", done
    aid = w.desk.aid(done["result_ids"][0])
    assert errors("study/workspace#/$defs/Aid", aid) == []
    outline = aid["outline"]
    # Moments from the cited line, by code: never the model's arithmetic.
    assert [o["at_ms"] for o in outline["objectives"]] == [21_000, 29_000, 35_000, 41_000]
    assert [e["at_ms"] for e in outline["examples"]] == [580_000, 596_000]
    concepts = {c["name"]: c for c in outline["concepts"]}
    assert concepts["Range"]["at_ms"] == 252_000 and concepts["Time of flight"]["at_ms"] == 413_000
    assert concepts["Maximum height"]["at_ms"] == 501_000 and concepts["Resolving the velocity"]["at_ms"] == 62_000
    assert "at_ms" not in outline["assumes"][0]
    # The range concept maps to its skill first (fixture checked, SPEC §20.8); nothing is outside the packs.
    assert concepts["Range"]["kc_ids"][0] == RANGE and concepts["Range"]["outside_packs"] is False
    assert concepts["Time of flight"]["kc_ids"][0] == FLIGHT
    assert concepts["Maximum height"]["kc_ids"][0] == HEIGHT
    assert concepts["Resolving the velocity"]["kc_ids"][0] == RESOLVE
    # Each concept maps to its one skill: a second skill only when it scores within a tenth of the best.
    assert all(len(concepts[n]["kc_ids"]) == 1 for n in ("Range", "Time of flight", "Maximum height",
                                                          "Resolving the velocity"))  # fmt: skip
    # The seeded pack has no graphs skill: sharing "time" with the time-of-flight skill is not enough to map there.
    assert concepts["Displacement time graph"]["kc_ids"] == [] and concepts["Displacement time graph"]["outside_packs"]
    # One skipped skill of the matched topic: drag, which the lecture never reaches ("not covered here").
    assert outline["skips"] == [{"kc_id": DRAG, "statement": "Describe the effect of drag on a projectile's path"}]
    # For this learner: the range secure, the rest not started (bands joined on the device, never sent).
    bands = {f["kc_id"]: f["band"] for f in outline["for_you"]}
    assert bands[RANGE] == "secure" and bands[FLIGHT] == "not_started" and bands[HEIGHT] == "not_started"
    assert set(bands) == {RANGE, FLIGHT, HEIGHT, RESOLVE}
    # The aid's claims are the outline's items, in order, each cited; the activity names the kind.
    assert [c["text"] for c in aid["claims"]][:2] == [
        "Resolve a launch velocity into horizontal and vertical components",
        "derive the range equation for a launch from level ground",
    ]
    made = [a for a in w.activity() if a["activity"] == "aid_made"]
    assert made and made[-1]["aid_kind"] == "teaching_outline"


def test_with_the_installed_physics_pack_the_concepts_map_to_its_projectile_skills(tmp_path: Path) -> None:
    """The shipped O-level physics pack has a projectile-motion subtopic (`kcs/projectiles.yaml`) whose statements
    use the lecture's words, so `kc_tags` maps every demo concept to one of its skills (SPEC §20.10, §20.4)."""
    assert NODE in PACK.nodes and {RANGE, FLIGHT, HEIGHT, RESOLVE} <= set(PACK.kcs)
    assert "range" in (PACK.kc_statement(RANGE) or "").lower()
    w = world(tmp_path)
    w.visits.open()
    done = outline_job(w, video(w), Cloud(), PACK)
    assert done["state"] == "completed", done
    outline = w.desk.aid(done["result_ids"][0])["outline"]
    concepts = {c["name"]: c for c in outline["concepts"]}
    assert not any(c["outside_packs"] for c in outline["concepts"])
    assert concepts["Range"]["kc_ids"][0] == RANGE
    assert concepts["Time of flight"]["kc_ids"][0] == FLIGHT
    assert concepts["Maximum height"]["kc_ids"][0] == HEIGHT
    assert concepts["Resolving the velocity"]["kc_ids"][0] == RESOLVE
    # Tight mapping (live-run fix 2026-11-01): the graph concept maps to the trajectory-and-graphs skill alone, not
    # to the time-of-flight, components and resolving skills that merely say "time" or "vertical"; the others too.
    assert concepts["Displacement time graph"]["kc_ids"] == [GRAPHS]
    assert concepts["Resolving the velocity"]["kc_ids"] == [RESOLVE]
    assert concepts["Time of flight"]["kc_ids"] == [FLIGHT] and concepts["Range"]["kc_ids"] == [RANGE]
    # The skipped skills are the subtopic's own skills the lecture never reaches; the learner has started none.
    assert all(s["kc_id"].startswith("kc.phy.o.projectiles.") for s in outline["skips"])
    assert {f["kc_id"] for f in outline["for_you"]} >= {RANGE, FLIGHT, HEIGHT, RESOLVE, GRAPHS}
    assert all(f["band"] == "not_started" for f in outline["for_you"])


def test_an_outline_item_whose_citation_is_not_the_transcripts_words_is_refused(tmp_path: Path) -> None:
    w = world(tmp_path)
    done = outline_job(w, video(w), Cloud(bad_citation=True), seeded_pack())
    assert done["state"] == "failed" and done["error"] == "insufficient_evidence"
    assert (
        w.conn.execute(
            "SELECT count(*) FROM study_aids WHERE json_extract(body,'$.kind')='teaching_outline'"
        ).fetchone()[0]
        == 0
    )


def test_a_dropped_item_rebuilds_the_outline_and_batches_merge_in_order() -> None:
    cite = [
        {
            "source_id": "src_" + "0" * 26,
            "revision": 1,
            "chunk_id": "sck_" + "0" * 26,
            "start": 0,
            "end": 1,
            "quote": "x",
        }
    ]
    outline = {"objectives": [{"text": "a", "citations": cite}, {"text": "b", "citations": cite}], "examples": [],
               "concepts": [{"name": "C", "citations": cite}],
               "assumes": [{"text": "d", "citations": cite}]}  # fmt: skip
    assert [c["text"] for c in study_outline.flatten(outline)] == ["a", "b", "C", "d"]
    kept = study_outline.rebuild(outline, [True, False, True, False])
    assert kept == {"objectives": [{"text": "a", "citations": cite}], "examples": [],
                    "concepts": [{"name": "C", "citations": cite}], "assumes": []}  # fmt: skip
    assert study_outline.rebuild(outline, [False, False, False, False]) is None
    merged = study_outline.merge([outline, {"objectives": [{"text": "e", "citations": cite}]}])
    assert [o["text"] for o in merged["objectives"]] == ["a", "b", "e"]
    many = {"objectives": [{"text": str(i), "citations": cite} for i in range(10)]}
    assert len(study_outline.merge([many, many])["objectives"]) == 12


def test_a_local_run_cannot_make_an_outline(tmp_path: Path) -> None:
    w = world(tmp_path)
    source = video(w)
    assert not w.desk.local_possible(
        {"kind": "teaching_outline", "sources": [{"source_id": source["source_id"], "revision": 1}]}
    )
    job = w.desk.create_job({"kind": "teaching_outline", "execution": "local",
                             "sources": [{"source_id": source["source_id"], "revision": 1}]})  # fmt: skip
    asyncio.run(w.queue.run(w.desk, job["job_id"]))
    assert w.desk.job(job["job_id"])["state"] == "waiting_online"
    with pytest.raises(StudyError, match="invalid_study_request"):  # a text source has no moments to outline
        w.desk.create_job({"kind": "teaching_outline", "execution": "prefer_cloud",
                           "sources": [{"source_id": w.source["source_id"], "revision": 1}]})  # fmt: skip


class LiveShapedCloud(Cloud):
    """The outline as Muse Spark wrote it in the live run (1 November): each objective cites the whole passage it sits
    in, from its first line, and two concepts name the lecture's subject or what it sets aside, not a skill."""

    async def process(self, conn: Any, jid: str, request: dict[str, Any], chunks: list[dict[str, Any]],
                      attempt: int, batch_index: int = 0) -> dict[str, Any]:  # fmt: skip
        done = await super().process(conn, jid, request, chunks, attempt, batch_index)
        outline = done["outline"]
        for objective in outline["objectives"][:3]:  # the fourth cites its own line, as in the live run
            chunk = next(c for c in chunks if c["chunk_id"] == objective["citations"][0]["chunk_id"])
            quote = chunk["text"][:490]  # a citation's quote is at most 500 characters
            objective["citations"] = [{**objective["citations"][0], "start": 0, "end": len(quote), "quote": quote}]
        outline["concepts"] += [
            named(chunks, "projectile motion", "in this lecture we look at projectile motion"),
            named(chunks, "air resistance", "we will ignore air resistance throughout"),
        ]
        return {**done, "claims": study_outline.flatten(outline)}


def test_an_objective_whose_citation_spans_the_passage_opens_at_its_own_line(tmp_path: Path) -> None:
    """Live-run fix 2026-11-01: the first three objectives showed "Open at 0:00" because their citations began at the
    passage's first line; the moment is the cited line that says the objective, by code (SPEC §20 "Lines keep their
    moments")."""
    w = world(tmp_path)
    w.visits.open()
    done = outline_job(w, video(w), LiveShapedCloud(), seeded_pack())
    assert done["state"] == "completed", done
    outline = w.desk.aid(done["result_ids"][0])["outline"]
    assert [o["at_ms"] for o in outline["objectives"]] == [21_000, 29_000, 35_000, 41_000]


def test_concepts_that_name_the_subject_or_what_is_set_aside_map_to_no_skill(tmp_path: Path) -> None:
    """Live-run fix 2026-11-01: "projectile motion" and "air resistance" were tagged to the time-of-flight skill
    because every skill of the subtopic says "projectile"; a concept maps through a word that tells skills apart."""
    for content in (seeded_pack(), PACK):
        (tmp_path / ("seeded" if content is not PACK else "installed")).mkdir()
        w = world(tmp_path / ("seeded" if content is not PACK else "installed"))
        w.visits.open()
        done = outline_job(w, video(w), LiveShapedCloud(), content)
        outline = w.desk.aid(done["result_ids"][0])["outline"]
        by_name = {c["name"]: c for c in outline["concepts"]}
        for generic in ("projectile motion", "air resistance"):
            assert by_name[generic]["kc_ids"] == [] and by_name[generic]["outside_packs"] is True, generic
        assert by_name["Time of flight"]["kc_ids"] == [FLIGHT]  # the skills the lecture does teach still map
