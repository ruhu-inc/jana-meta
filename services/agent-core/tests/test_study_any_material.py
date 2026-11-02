"""Studying any material: written answers marked online, long sources sampled, course files accepted, no set level."""

from __future__ import annotations

import asyncio
import json

import pytest
from agent_core.engine.study import LONG_SOURCE_BATCHES, TEXT_SUFFIXES, StudyDesk, StudyError
from agent_core.memory.queries import ProfileSummary
from agent_core.memory.render import profile_line
from study_worker import notebook_text
from test_study_workspace import claim, queue_for, seeded


def blank_quiz(d, chunk):
    sources = [{"source_id": chunk["source_id"], "revision": chunk["revision"]}]
    job = d.create_job({"kind": "notes", "execution": "prefer_cloud", "sources": sources})
    job["state"] = "running"
    d.save_job(job)
    return job


class Marking:
    def __init__(self, said="correct"):
        self.said, self.bodies = said, []

    async def mark_answer(self, conn, request_id, body):
        self.bodies.append(body)
        if isinstance(self.said, Exception):
            raise self.said
        return self.said


def item_and_key(chunk):
    item = {"item_id": "q0", "type": "fill_blank", "stem": claim(chunk, "It stores ____.")}
    key = {"item_id": "q0", "answer": "DNA", "explanation": claim(chunk), "marking": "judged"}
    return item, key


@pytest.mark.parametrize("said", ["correct", "incorrect", "partial"])
def test_a_written_answer_takes_the_online_verdict(tmp_path, said):
    d, s = seeded(tmp_path)
    chunk = d.chunks(s["source_id"], 1)["items"][0]
    job = blank_quiz(d, chunk)
    aid = d.commit_aid(job, {"request_id": job["job_id"], "kind": "notes", "claims": [claim(chunk)]}, [True])
    queue = queue_for(d)
    queue.cloud = Marking(said)
    item, key = item_and_key(chunk)
    assert asyncio.run(queue.mark_online(d, aid["aid_id"], item, key, "genetic code")) == said
    sent = queue.cloud.bodies[0]
    assert sent["passages"] == [chunk["text"]] and sent["answer"] == "genetic code"  # only what the question cites


def test_a_failed_or_undecided_marking_leaves_the_answer_unmarked(tmp_path):
    d, s = seeded(tmp_path)
    chunk = d.chunks(s["source_id"], 1)["items"][0]
    job = blank_quiz(d, chunk)
    aid = d.commit_aid(job, {"request_id": job["job_id"], "kind": "notes", "claims": [claim(chunk)]}, [True])
    item, key = item_and_key(chunk)
    for said in ("unverifiable", ValueError("consent_required"), TimeoutError()):
        queue = queue_for(d)
        queue.cloud = Marking(said)
        assert asyncio.run(queue.mark_online(d, aid["aid_id"], item, key, "an answer")) is None
    queue = queue_for(d)
    queue.cloud = None
    assert asyncio.run(queue.mark_online(d, aid["aid_id"], item, key, "an answer")) is None


def test_a_long_source_with_no_focus_is_sampled_evenly_and_says_so(tmp_path):
    d, s = seeded(tmp_path)
    sources = [{"source_id": s["source_id"], "revision": 1}]
    job = d.create_job({"kind": "notes", "execution": "prefer_cloud", "sources": sources})
    template = d.chunks(s["source_id"], 1)["items"][0]
    chunks = [{**template, "chunk_id": f"sck_{i:026d}", "text": "x" * 16000, "ordinal": i} for i in range(300)]
    seen = []

    class Cloud:
        async def process(self, connection, identity, request, batch, attempt, batch_index=0):
            seen.append(batch[0]["ordinal"])
            raise StudyError("model_unavailable")  # stop after the plan is made

        async def cleanup(self, connection):
            pass

    queue = queue_for(d)
    queue.cloud = Cloud()
    request = d.one("SELECT checkpoint FROM study_jobs WHERE job_id=?", (job["job_id"],))["request"]
    with pytest.raises(StudyError):
        asyncio.run(queue.generate_batches(d, d.job(job["job_id"]), request, chunks))
    made = d.job(job["job_id"])
    assert made["notice"] == "sampled_long_source"
    assert made["total_units"] == len(chunks) + 2 * LONG_SOURCE_BATCHES  # the plan reads 24 sections, not 100


@pytest.mark.parametrize("name", ["week3.tex", "model.py", "results.csv", "lab.ipynb", "refs.bib"])
def test_course_files_are_accepted_as_text(name):
    StudyDesk.accept_file("document", name)
    assert "." + name.rsplit(".", 1)[1] in TEXT_SUFFIXES


def test_an_unknown_binary_format_is_still_refused():
    with pytest.raises(StudyError):
        StudyDesk.accept_file("document", "installer.exe")


def test_a_notebook_reads_as_its_cells_without_outputs():
    code = {"cell_type": "code", "source": "fit(X, y)", "outputs": [{"text": "SECRET"}]}
    notebook = {"nbformat": 4, "cells": [{"cell_type": "markdown", "source": ["# Ridge\n", "Penalty"]}, code]}
    text = notebook_text(json.dumps(notebook))
    assert "# Ridge" in text and "fit(X, y)" in text and "SECRET" not in text
    assert notebook_text("just some text") == "just some text"


def test_a_profile_with_no_subjects_is_never_described_as_o_level():
    own = ProfileSummary("O", (), None, None, None, "guided")
    assert "O level" not in profile_line(own) and "own course" in profile_line(own)
    assert "O level" in profile_line(ProfileSummary("O", ("physics",), None, None, None, "guided"))


def test_study_practice_lists_its_ideas_newest_first_without_a_skipped_question():
    import sqlite3

    from agent_core.memory.queries import studied_kcs

    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE events (seq INTEGER PRIMARY KEY, type TEXT, payload TEXT, occurred_at INT, erased_at INT)"
    )
    rows = [("quiz_item", "kc.a", "correct", 10), ("quiz_item", "kc.b", "skipped", 11),
            ("card_review", "kc.c", None, 12), ("aid_made", "kc.d", None, 13),
            ("quiz_item", "kc.a", "incorrect", 2)]  # fmt: skip
    for activity, kc, outcome, at in rows:
        # Stored exactly as `kc_tags` writes them: an object with a weight, not a bare id.
        payload = {"activity": activity, "kc_tags": [{"kc_id": kc, "weight": 1.0}], "outcome": outcome}
        conn.execute("INSERT INTO events (type, payload, occurred_at) VALUES ('study_activity', ?, ?)",
                     (json.dumps(payload), at))  # fmt: skip
    assert studied_kcs(conn, 5) == ["kc.c", "kc.a"]


def test_a_quiz_question_is_tagged_to_a_skill_through_its_material():
    """One short question names no topic by itself: the real packs tagged 0 of 6 answers. The source names the topic."""
    from agent_core.engine.study_session import StudyVisits
    from test_w9_teaching_outline import seeded_pack

    content = seeded_pack()
    visits = StudyVisits.__new__(StudyVisits)
    visits.content = lambda: content
    recorded = []
    visits.record = lambda activities, **_: recorded.extend(activities) or len(activities)
    material = "in this lecture we look at projectile motion and the range of a projectile launched from level ground"
    question = "What does the range equation give for a launch from level ground, and how does the angle change it?"
    visits.quiz("sqa_1", [(0, question, "correct")], material=material)
    assert recorded[0]["kc_tags"], "the question should reach a skill through its material"
    assert all(t["kc_id"].startswith("kc.") for t in recorded[0]["kc_tags"])
    recorded.clear()
    visits.quiz("sqa_2", [(0, question, "correct")])  # no material: as before, no guess
    assert isinstance(recorded[0]["kc_tags"], list)
