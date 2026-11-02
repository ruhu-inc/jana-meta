"""A generated aid the verifier refused goes again once by itself; a question the material cannot answer does not."""

from __future__ import annotations

import asyncio

from agent_core.engine.study import StudyError
from test_study_workspace import claim, queue_for, seeded


class Cloud:
    def __init__(self, refusals: int, reason: str = "insufficient_evidence") -> None:
        self.refusals, self.reason = refusals, reason
        self.attempts: list[int] = []

    async def process(self, connection, identity, request, chunks, attempt, batch_index=0):
        self.attempts.append(attempt)
        if len(self.attempts) <= self.refusals:
            raise StudyError(self.reason)
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


def test_a_model_reply_that_could_not_be_read_goes_again_once(tmp_path):
    """The reliability run of 2 November: one quiz in 22 failed on a support reply that was not valid JSON."""
    d, s = seeded(tmp_path)
    cloud = Cloud(1, "model_unavailable")
    assert drive(d, cloud, job_of(d, s))["state"] == "completed"
    assert len(cloud.attempts) >= 2


def test_a_model_that_stays_down_reaches_the_learner(tmp_path):
    d, s = seeded(tmp_path)
    cloud = Cloud(99, "model_unavailable")
    job = drive(d, cloud, job_of(d, s), runs=4)
    assert job["state"] == "failed" and job["error"] == "model_unavailable"


class Unreachable(Cloud):
    """The gateway cannot be reached at first, then comes back."""

    async def process(self, connection, identity, request, chunks, attempt, batch_index=0):
        if self.refusals > 0:
            self.refusals -= 1
            raise StudyError("waiting_online")
        return await super().process(connection, identity, request, chunks, attempt, batch_index)


def test_a_job_parked_by_a_brief_outage_goes_again_by_itself(tmp_path):
    d, s = seeded(tmp_path)
    jid = job_of(d, s)
    queue = queue_for(d)
    queue.cloud = Unreachable(1)
    asyncio.run(queue.run(d, jid))
    assert d.job(jid)["state"] == "waiting_online"
    queue.next_online_retry = 0
    queue.retry_waiting_online(d)
    assert d.job(jid)["state"] == "queued"
    asyncio.run(queue.run(d, jid))
    assert d.job(jid)["state"] == "completed"


def test_parked_jobs_are_not_retried_more_often_than_the_interval(tmp_path):
    d, s = seeded(tmp_path)
    jid = job_of(d, s)
    queue = queue_for(d)
    queue.cloud = Unreachable(1)
    asyncio.run(queue.run(d, jid))
    queue.next_online_retry = queue.clock() + 1000
    queue.retry_waiting_online(d)
    assert d.job(jid)["state"] == "waiting_online"


def test_a_job_that_may_only_run_on_this_device_stays_parked(tmp_path):
    d, s = seeded(tmp_path)
    jid = d.create_job(
        {"kind": "notes", "execution": "local", "sources": [{"source_id": s["source_id"], "revision": 1}]}
    )["job_id"]
    job = d.job(jid)
    job.update(state="waiting_online", error=None)
    d.save_job(job)
    queue = queue_for(d)
    queue.cloud = Unreachable(0)
    queue.retry_waiting_online(d)
    assert d.job(jid)["state"] == "waiting_online"
