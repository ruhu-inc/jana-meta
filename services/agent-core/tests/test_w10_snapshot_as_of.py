"""The learner model as of a date (SPEC §21.5, JM-D37; W10): a dated event log replays, in memory, to the bands the
projections had then; `snapshot_as_of(now)` equals the live tables; the live database's checksums are unchanged by a
replay; the 26-week bound; the per-date cache; and 10,000 events within the 2 s budget (the rebuild budget of
`config/keys.py`, 100,000 events in 10 s, scaled). Synthetic learners from `learner_harness`."""

from __future__ import annotations

import random
import time
from pathlib import Path

import pytest
from agent_core.engine.learner_map import AsOfRefused, MapState, check_as_of, day_end, snapshot, states_now
from agent_core.learner.mastery import DAY_MS, MasteryParams
from agent_core.learner.projections import Snapshots, snapshot_as_of, table_checksum
from agent_core.memory.render import BANDS
from learner_harness import Clock, Session, make_learner
from test_m13g_learn import run
from w10_map_harness import V_T, node, world

PARAMS = MasteryParams()


def _bands(conn, now: int) -> dict[str, str]:
    return {kc: BANDS[s] for kc, s in states_now(conn, PARAMS, now).items()}


def _all_checksums(conn) -> dict[str, str]:
    tables = [
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_schema WHERE type = 'table'"
            " AND name NOT LIKE 'sqlite_%' AND name NOT LIKE '%fts%' ORDER BY name"
        )
    ]
    return {t: table_checksum(conn, t) for t in tables}


def test_a_dated_log_replays_to_the_bands_the_projections_had_then() -> None:
    rng, clock = random.Random(21), Clock()
    learner = make_learner(clock=clock)
    learner.log.clock.wall_ms = clock
    seen: list[tuple[int, str, dict[str, str]]] = []
    for _ in range(14):
        Session(rng, learner, clock).run(rng.randint(1, 4))
        seen.append((clock.now, learner.projector.checksum(), _bands(learner.conn, clock.now)))
        clock.now += rng.randint(DAY_MS, 9 * DAY_MS)
    for at, checksum, bands in seen:
        mem = snapshot_as_of(learner.conn, PARAMS, None, at, learner.projector.projections)
        # Every projection table as it stood then, and so the bands shown then.
        from agent_core.learner.projections import Projector

        assert Projector(mem, PARAMS).checksum() == checksum
        assert _bands(mem, at) == bands
        mem.close()
    assert len({c for _, c, _ in seen}) > 5, "the learner moved between the dates"


def test_snapshot_at_now_equals_the_live_tables_and_writes_nothing() -> None:
    rng, clock = random.Random(8), Clock()
    learner = make_learner(clock=clock)
    learner.log.clock.wall_ms = clock
    for _ in range(10):
        Session(rng, learner, clock).run(rng.randint(1, 4))
        clock.now += rng.randint(3_600_000, 5 * DAY_MS)
    before = _all_checksums(learner.conn)
    mem = snapshot_as_of(learner.conn, PARAMS, None, clock.now, learner.projector.projections)
    from agent_core.learner.projections import Projector

    live = Projector(learner.conn, PARAMS, None, learner.projector.projections)
    copy = Projector(mem, PARAMS, None, learner.projector.projections)
    for projection in live.projections:
        assert copy.checksum(projection.name) == live.checksum(projection.name), projection.name
    assert table_checksum(mem, "events") == table_checksum(learner.conn, "events")
    assert _all_checksums(learner.conn) == before, "the live database is only read"


def test_the_26_week_bound_and_dates() -> None:
    now = 1_790_000_000_000
    today = check_as_of(PARAMS, now, "2026-09-21")
    assert today == "2026-09-21"
    assert check_as_of(PARAMS, now, "2026-03-23") == "2026-03-23"  # exactly 26 weeks back
    for bad in ("2026-03-22", "2026-09-22", "2026-9-1", "yesterday", "2026-02-30"):
        with pytest.raises(AsOfRefused):
            check_as_of(PARAMS, now, bad)
    # A date's moment is the last millisecond of that local day.
    assert day_end(PARAMS, "2026-09-21") + 1 == (PARAMS.local_day(now) + 1) * DAY_MS


def test_the_api_refuses_a_date_out_of_bounds_and_replays_one_in_them(tmp_path: Path) -> None:
    from datetime import UTC, datetime, timedelta

    async def scenario() -> None:
        async with world(tmp_path) as w:
            start = datetime.fromtimestamp(w.now / 1000, UTC).date()
            w.days(1)
            w.practise(V_T)
            w.days(30)
            w.secure(V_T)
            today = datetime.fromtimestamp(w.now / 1000, UTC).date()
            for bad in (today + timedelta(days=1), today - timedelta(weeks=26, days=1)):
                reply = await w.c.get(f"/v1/curriculum/cur.phy.o/concept-map?as_of={bad.isoformat()}")
                assert reply.status_code == 422 and reply.json()["error"]["code"] == "validation_failed", reply.text
            assert (await w.c.get("/v1/curriculum/cur.phy.o/concept-map?as_of=soon")).status_code == 422
            live = await w.map()
            then = await w.map(as_of=(today - timedelta(days=28)).isoformat())
            assert (node(live, V_T)["band"], node(then, V_T)["band"]) == ("secure", "learning")
            assert then["as_of"] == (today - timedelta(days=28)).isoformat() and live["as_of"] is None
            before = await w.map(as_of=start.isoformat())
            assert {n["band"] for n in before["nodes"]} == {"not_started"}, "before any practice: all not yet"
            assert live["first_day"] is not None and live["first_day"] <= (today - timedelta(days=28)).isoformat()

    run(scenario())


def test_the_cache_replays_a_date_once_until_the_log_grows() -> None:
    rng, clock = random.Random(3), Clock()
    learner = make_learner(clock=clock)
    learner.log.clock.wall_ms = clock
    Session(rng, learner, clock).run(3)
    state = MapState()
    args = (learner.conn, PARAMS, None, learner.projector.projections)
    first, _ = snapshot(state, "p", "2025-10-09", *args)
    second, _ = snapshot(state, "p", "2025-10-09", *args)
    assert first is second and state.snapshots.builds == 1
    Session(rng, learner, clock).run(1)  # a later event (a sync could bring an earlier one): replay again
    third, _ = snapshot(state, "p", "2025-10-09", *args)
    assert third is not first and state.snapshots.builds == 2
    held = Snapshots(limit=2)
    for day in ("2025-10-01", "2025-10-02", "2025-10-03"):
        held.get("p", day, learner.conn, lambda: snapshot_as_of(learner.conn, PARAMS, None, clock.now))
    assert len(held.held) == 2


def test_ten_thousand_events_replay_within_the_budget() -> None:
    rng, clock = random.Random(5), Clock()
    learner = make_learner(clock=clock)
    learner.log.clock.wall_ms = clock
    while learner.conn.execute("SELECT count(*) FROM events").fetchone()[0] < 10_000:
        Session(rng, learner, clock).run(rng.randint(2, 6))
        clock.now += rng.randint(3_600_000, 3 * DAY_MS)
    started = time.perf_counter()
    mem = snapshot_as_of(learner.conn, PARAMS, None, clock.now, learner.projector.projections)
    elapsed = time.perf_counter() - started
    assert mem.execute("SELECT count(*) FROM events").fetchone()[0] >= 10_000
    # Measured on the development machine; TABLE MDL-16a's mid class runs in the device lab (as the rebuild budget).
    assert elapsed <= 2.0, f"{elapsed:.2f} s"
