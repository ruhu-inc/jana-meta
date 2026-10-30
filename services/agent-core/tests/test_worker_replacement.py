"""Rejected checks return before worker warm-up; replacement cannot strand callers or outlive shutdown."""

import asyncio

import pytest
from agent_core.config import Settings
from agent_core.tools.worker import WorkerCallError, WorkerSupervisor
from tool_worker.protocol import Code


class ControlledWorker:
    def __init__(self, *, reject=False, gate=None, fail=False):
        self.reject, self.gate, self.fail = reject, gate, fail
        self.entered = asyncio.Event()
        self.killed = self.closed = False

    async def start(self):
        pass

    async def hello(self, *args, **kwargs):
        self.entered.set()
        if self.gate is not None:
            await self.gate.wait()
        if self.fail:
            raise TimeoutError
        return {"functions": [{"name": "math_parse"}]}

    async def request(self, *args, **kwargs):
        assert not self.killed and not self.closed, "a retired worker must never receive another check"
        if self.reject:
            raise WorkerCallError(Code.LIMIT_EXCEEDED, "expression limit")
        return {"value": "checked"}

    def kill(self):
        self.killed = True

    async def close(self, **kwargs):
        self.closed = True


async def checked(supervisor):
    return await supervisor.call("math_parse", 1, {"text": "x+1"}, "chk_test", 2000)


@pytest.mark.parametrize("fail", [False, True])
def test_rejection_returns_before_replacement_and_waiters_finish(fail):
    async def scenario():
        release = asyncio.Event()
        original = ControlledWorker(reject=True)
        replacement = ControlledWorker(gate=release, fail=fail)
        workers = iter([original, replacement])
        supervisor = WorkerSupervisor(
            lambda: next(workers), Settings(worker_pool_size=1, worker_respawn_backoff_s=(0.0,))
        )
        await supervisor.start()
        rejected = asyncio.create_task(checked(supervisor))
        try:
            await asyncio.wait_for(replacement.entered.wait(), 5)
            assert rejected.done(), "return the rejection without waiting for the replacement handshake"
            assert (await rejected).error == "limit_exceeded"
            assert original.killed and original.closed
            waiting = [asyncio.create_task(checked(supervisor)) for _ in range(2)]
            await asyncio.sleep(0)
            assert not any(task.done() for task in waiting)
            release.set()
            results = await asyncio.wait_for(asyncio.gather(*waiting), 5)
            assert all(result.error == "worker_unavailable" if fail else result.ok for result in results)
        finally:
            release.set()
            await rejected
            await supervisor.close()

    asyncio.run(scenario())


def test_shutdown_during_replacement_closes_the_new_worker_and_releases_waiters():
    async def scenario():
        release = asyncio.Event()
        replacement = ControlledWorker(gate=release)
        workers = iter([ControlledWorker(reject=True), replacement])
        supervisor = WorkerSupervisor(
            lambda: next(workers), Settings(worker_pool_size=1, worker_respawn_backoff_s=(0.0,))
        )
        await supervisor.start()
        rejected = asyncio.create_task(checked(supervisor))
        try:
            await asyncio.wait_for(replacement.entered.wait(), 5)
            assert rejected.done(), "the caller must receive its rejection while replacement is pending"
            waiting = asyncio.create_task(checked(supervisor))
            closing = asyncio.create_task(supervisor.close())
            await asyncio.sleep(0)
            release.set()
            await asyncio.wait_for(closing, 5)
            assert (await asyncio.wait_for(waiting, 5)).error == "worker_unavailable"
            assert replacement.closed and not supervisor.compute_available()
            assert (await checked(supervisor)).error == "worker_unavailable"
        finally:
            release.set()
            await rejected
            await supervisor.close()

    asyncio.run(scenario())
