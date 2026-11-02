"""A generated aid the verifier refused goes again once by itself; a question the material cannot answer does not."""

from __future__ import annotations

import asyncio

from agent_core.engine.study import StudyError
from test_study_workspace import claim, queue_for, seeded


class Cloud:
    def __init__(self, refusals: int) -> None:
        self.refusals = refusals
        self.attempts: list[int] = []

    async def process(self, connection, identity, request, chunks, attempt, batch_index=0):
        self.attempts.append(attempt)
        if len(self.attempts) <= self.refusals:
            raise StudyError("insufficient_evidence")
        return {"request_id": identity, "kind": request["kind"], "claims": [claim(c) for c in chunks]}

    async def cleanup(self, connection):
        pass


def job_of(d, s, kind="notes", **extra):
    return d.create_job(
        {"kind": kind, "execution": "prefer_cloud", "sources": [{"source_id": s["source_id"], "revision": 1}], **extra}
    )["job_id"]


def drive(d, cloud, jid, runs=2):
    queue = queue_for(d)
    queue.cloud = cloud
    for _ in range(runs):
        if d.job(jid)["state"] in ("queued", "running"):
            asyncio.run(queue.run(d, jid))
    return d.job(jid)


def test_a_refused_aid_goes_again_once_and_completes(tmp_path):
    d, s = seeded(tmp_path)
    cloud = Cloud(refusals=1)
    finished = drive(d, cloud, job_of(d, s))
    assert finished["state"] == "completed" and finished["error"] is None
    assert cloud.attempts == [1, 2]  # a new attempt number, so the gateway bills and sends it as a new try


def test_two_refusals_reach_the_learner_and_try_again_earns_one_more_automatic_try(tmp_path):
    d, s = seeded(tmp_path)
    cloud = Cloud(refusals=2)
    jid = job_of(d, s)
    failed = drive(d, cloud, jid)
    assert failed["state"] == "failed" and failed["error"] == "insufficient_evidence"
    assert cloud.attempts == [1, 2]
    cloud.refusals = 3
    d.action(jid, {"action": "retry"})
    finished = drive(d, cloud, jid)
    assert finished["state"] == "completed"
    assert cloud.attempts == [1, 2, 3, 4]


def test_a_question_the_material_cannot_answer_is_not_retried(tmp_path):
    d, s = seeded(tmp_path)
    cloud = Cloud(refusals=5)
    failed = drive(d, cloud, job_of(d, s, kind="chat", prompt="What does this say about tides?"))
    assert failed["state"] == "failed" and failed["error"] == "insufficient_evidence"
    assert cloud.attempts == [1]
