"""The W9 Study scenario (SPEC §20.9, §20.10): `scenarios/w9/youtube_lecture.yaml`, run through the generalised loader
(`scenario_cases.py`) against the real Study desk and queue, the outline's device-side fill and the companion's study
tools, with the gateway scripted (its own tests cover Muse Spark's draft and verification). The rubric is checked by
code; `run` returns the failures, an empty list being a pass."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from agent_core.config import Settings
from agent_core.engine.companion import fact_binding_errors, resolve_action
from agent_core.engine.memory_session import MemoryAccess, SessionMemory
from agent_core.engine.memory_tools import StudyTools
from agent_core.engine.study import StudyQueue


def _youtube_lecture(case: dict[str, Any], tmp: Path) -> list[str]:
    from memory_harness import PROFILE_A
    from test_w8_study_activity import world
    from test_w9_teaching_outline import Cloud, seeded_pack

    expect, failures = case["expect"], []
    transcript = (Path(__file__).parent / case["transcript_fixture"]).read_text()
    w = world(tmp)
    w.visits.open()
    w.conn.execute(
        "INSERT INTO kc_mastery (kc_id, status, p_mastery, n_eff, attempts, correct, mastery_check_state, last_seen_at,"
        " last_event_seq) VALUES (?, 'mastered', 0.97, 8, 8, 8, 'passed', ?, 1)",
        (case["learner_secure"], w.clock.now),
    )
    source = w.desk.create(
        {"kind": "video_link", "url": case["video"], "transcript": transcript, "title": case["title"]}
    )
    if source["state"] != "ready":
        failures.append(f"the source is {source['state']}, not ready at once")
    if [c["title"] for c in source.get("chapters", [])] != expect["chapters"]:
        failures.append(f"chapters {[c['title'] for c in source.get('chapters', [])]}")
    uploads = w.conn.execute("SELECT count(*) FROM study_revisions WHERE blob_ref IS NOT NULL").fetchone()[0]
    if uploads != expect["uploads"]:
        failures.append(f"{uploads} uploads for a pasted transcript")
    # What this video teaches: one cloud call over the transcript chunks, the rest by code on the device.
    cloud = Cloud()
    job = w.desk.create_job({"kind": "teaching_outline", "execution": "prefer_cloud",
                             "sources": [{"source_id": source["source_id"], "revision": 1}]})  # fmt: skip
    queue = StudyQueue(lambda: w.conn, lambda: None, lambda: False, w.clock, w.desk.settings)
    queue.cloud, queue.content, queue.activity = cloud, seeded_pack, w.visits
    asyncio.run(queue.run(w.desk, job["job_id"]))
    done = w.desk.job(job["job_id"])
    if done["state"] != "completed":
        return [*failures, f"the outline job {done['state']}: {done.get('error')}"]
    outline = w.desk.aid(done["result_ids"][0])["outline"]
    if len(outline["objectives"]) != expect["objectives"] or any("at_ms" not in o for o in outline["objectives"]):
        failures.append("objectives: count or moments")
    if len(outline["examples"]) != expect["examples"]:
        failures.append("worked examples count")
    concepts = {c["name"]: c for c in outline["concepts"]}
    if list(concepts) != expect["concepts"]:
        failures.append(f"concepts {list(concepts)}")
    rng = concepts.get("Range", {})
    if rng.get("kc_ids", [None])[0] != expect["range_kc"] or rng.get("at_ms") != expect["range_at_ms"]:
        failures.append(f"the range concept: {rng.get('kc_ids')} at {rng.get('at_ms')}")
    if [a["text"] for a in outline["assumes"]] != [expect["assumes"]]:
        failures.append(f"assumes {[a['text'] for a in outline['assumes']]}")
    if [s["kc_id"] for s in outline["skips"]] != expect["skips"]:
        failures.append(f"skips {[s['kc_id'] for s in outline['skips']]}")
    bands = {f["kc_id"]: f["band"] for f in outline["for_you"]}
    if bands != expect["bands"]:
        failures.append(f"for you {bands}")
    ((request, chunks),) = cloud.requests
    if sorted(request) != sorted(expect["request_keys"]) or any(c["locator"]["kind"] != "time" for c in chunks):
        failures.append(f"the outline request carried {sorted(request)}")
    # Your tutor: the hit's moment resolves to open_moment, and the timestamp binds as a moment.
    held = _source(w)
    memory = SessionMemory(MemoryAccess(PROFILE_A, lambda: held), Settings(), "ses_" + "0" * 26)
    tools = StudyTools(memory, Settings(), lambda: False)
    hits = asyncio.run(tools.search({"query": "range equation"}, _Context()))["items"]  # type: ignore[arg-type]
    hit = next((h for h in hits if h.get("moment") == expect["moment"]), None)
    if hit is None:
        failures.append(f"no hit at {expect['moment']}: {[h.get('moment') for h in hits]}")
    else:
        action = resolve_action({"kind": "open_moment", "ref": hit["ref"]}, tools.bands, tools.moments)
        if action != {
            "action": "open_moment",
            "payload": {"source_id": source["source_id"], "at_ms": expect["range_at_ms"]},
        }:
            failures.append(f"open_moment resolved to {action}")
        if fact_binding_errors(f"She derives it at 0{expect['moment']}.", [{"items": [hit]}]):
            failures.append("04:12 did not bind as a moment")
    return failures


def _source(w: Any) -> Any:
    from agent_core.engine.memory_session import MemorySource
    from memory_harness import CAPTURE, PACK

    return MemorySource(w.learner, PACK, CAPTURE)


class _Context:
    class session:
        session_id = "ses_" + "0" * 26
        subject = "physics"


RUNNERS = {"youtube_lecture": _youtube_lecture}
