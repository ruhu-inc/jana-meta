"""VER-01 and VER-27: a symbolic time slice is measured in the thread's CPU time without the cyclic collector's pauses,
so neither a busy machine nor a large heap turns a verdict into `unknown`/`timeout`; real work past the slice still ends
in `SliceExpired`."""

from __future__ import annotations

import gc
import sys
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from functools import partial
from typing import Any

import pytest
from jana_tools import golden
from tool_worker.budget import CHECK_EVERY, SliceExpired, time_slice
from tool_worker.functions import maths


def _work(calls: int) -> None:
    def step() -> None:
        return None

    for _ in range(calls):
        step()


def test_ver01_slice_ignores_time_the_thread_spends_waiting() -> None:
    # Wall time passes (another process or thread has the CPU), CPU time does not: the slice still has room.
    with time_slice(0.2):
        time.sleep(0.4)
        _work(10_000)


def test_ver01_slice_ignores_another_thread_holding_the_cpu() -> None:
    stop = threading.Event()

    def spin() -> None:
        while not stop.is_set():
            sum(range(1_000))

    other = threading.Thread(target=spin)
    other.start()
    try:
        started = time.monotonic()
        with time_slice(0.05):
            while time.monotonic() - started < 0.2:  # four slices of wall time, shared with the spinning thread
                _work(100)
                time.sleep(0.001)
    finally:
        stop.set()
        other.join()


def test_ver27_slice_still_ends_cpu_work_past_it() -> None:
    with pytest.raises(SliceExpired), time_slice(0.05):
        _work(10**9)


class _Clock:
    """A CPU clock the test moves by hand. `pause_in_collector` adds a full collection's cost to every collection."""

    def __init__(self, pause_in_collector: float = 0.0) -> None:
        self.now = 0.0
        self.pause = pause_in_collector

    def __call__(self) -> float:
        return self.now

    def collecting(self, phase: str, info: dict[str, int]) -> None:
        if phase == "start":
            self.now += self.pause


@contextmanager
def _collector_pauses(clock: _Clock) -> Iterator[None]:
    gc.callbacks.append(clock.collecting)
    try:
        yield
    finally:
        gc.callbacks.remove(clock.collecting)


def test_ver01_slice_does_not_charge_a_collector_pause() -> None:
    # The collection runs in this thread and stops it for an hour of CPU time; the question has used none of its slice.
    clock = _Clock(pause_in_collector=3600.0)
    with time_slice(0.8, clock=clock), _collector_pauses(clock):
        gc.collect()
        _work(1_000)
    assert clock.now == 3600.0  # the pause did reach the clock the slice reads


def test_ver01_slice_does_not_charge_a_real_collector_pause() -> None:
    # The same with the real clock and collector: a heap whose full collection takes longer than the slice.
    heap = [[n] for n in range(1_000_000)]
    started = time.thread_time()
    gc.collect()
    pause = time.thread_time() - started
    with time_slice(pause / 4):
        gc.collect()
        _work(1_000)
    assert heap


def test_ver01_slice_charges_work_done_while_another_thread_collects() -> None:
    # Only this thread's own collections are free: its clock moves during another thread's only by its own work.
    clock = _Clock(pause_in_collector=0.9)
    other = threading.Thread(target=gc.collect)
    with pytest.raises(SliceExpired), time_slice(0.8, clock=clock), _collector_pauses(clock):
        other.start()
        other.join()
        _work(1_000)


def test_ver27_slice_still_ends_work_done_after_a_collector_pause() -> None:
    clock = _Clock(pause_in_collector=3600.0)
    with pytest.raises(SliceExpired), time_slice(0.8, clock=clock), _collector_pauses(clock):
        gc.collect()
        clock.now += 0.9  # real work past the slice, after the pause
        _work(1_000)


def test_ver27_slice_expiring_during_a_collection_still_ends_the_work() -> None:
    # An exception from a trace function during a collection would be lost and would remove the trace function, so
    # the slice would never end: the check waits for the next call outside the collector.
    clock = _Clock()
    with pytest.raises(SliceExpired), time_slice(0.8, clock=clock):
        clock.now = 0.9
        for _ in range(4 * CHECK_EVERY):
            gc.collect()
        assert sys.gettrace() is not None
        _work(1_000)


@pytest.mark.parametrize("expires", [False, True])
def test_ver27_slice_leaves_no_collector_callback_behind(expires: bool) -> None:
    before = list(gc.callbacks)
    if expires:
        with pytest.raises(SliceExpired), time_slice(0):
            _work(1_000)
    else:
        with time_slice(0.8):
            _work(1)
    assert gc.callbacks == before


# --- the failure on CI: e^x sin(x) answered unknown/timeout, then its value, in one process (job 126072229463) ---

SERIES = {"expression": "e^x sin(x)", "form": "series", "order": 5}
ANSWERED = "b912266aeb6c24214d7520b5a4455c23c4e71c917c0c69a55eec8e3c2a718a71"
TIMED_OUT = "a792122ea59e811a8a40f2f70dab9e2318e0df9d5fb2583cf13cdc02f67cd011"


def _series_hash() -> str:
    return golden.result_sha256(golden.run({"args": SERIES}, "math_simplify"))


def test_ver27_series_past_its_slice_answers_unknown_timeout() -> None:
    settings = {"symbolic_slice_ms": 0}
    value = golden.run({"args": SERIES}, "math_simplify", settings)
    assert value == {"status": "unknown", "reason": "timeout"}
    assert golden.result_sha256(value) == TIMED_OUT


def test_ver01_series_is_byte_identical_when_a_collection_lands_in_its_slice(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = _Clock(pause_in_collector=3600.0)
    series = maths._series

    def collected_first(*args: Any) -> Any:
        with _collector_pauses(clock):
            gc.collect()  # where an allocation would have started it on a large heap
        return series(*args)

    monkeypatch.setattr(maths, "time_slice", partial(time_slice, clock=clock))
    monkeypatch.setattr(maths, "_series", collected_first)
    first = _series_hash()
    monkeypatch.setattr(maths, "_series", series)
    assert first == _series_hash() == ANSWERED
