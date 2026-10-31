"""The W10 learner's map scenarios (SPEC §21.9, §21.10): the `learner_map` suite in evals/suites.toml, run through
`scenario_cases.py`. Each handler plays a case's steps against the real core (the W10 map harness: Physics and Maths
packs, a clock the case moves) and checks its rubric by code. `RUNNERS` maps a case name to its handler."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from test_m13g_learn import run as run_async
from w10_map_harness import ident, node, world


def _map_month_later(case: dict[str, Any], tmp: Path) -> list[str]:
    failures: list[str] = []

    async def scenario() -> None:
        async with world(tmp) as w:
            start = w.now
            for n, step in enumerate(case["steps"]):
                w.at(start + int(step["day"]) * 86_400_000)
                if "secure" in step:
                    w.secure(step["secure"])
                elif "practise" in step:
                    w.practise(step["practise"])
                elif "study" in step:
                    w.study(step["study"], f"aid:{ident('aid', n)}", "aid_made", aid_kind="summary")
                elif "misconception" in step:
                    w.misconception(*step["misconception"])
                elif step.get("open"):
                    await w.map()
                    w.new_visit()
            expect = case["expect"]
            recorded = w.events()
            live = await w.map()
            for kc, bucket in expect["freshness"].items():
                if node(live, kc)["freshness"] != bucket:
                    failures.append(f"{kc} freshness {node(live, kc)['freshness']}, expected {bucket}")
            due = sorted(n["kc_id"] for n in live["nodes"] if n["refresh_due"])
            if due != sorted(expect["refresh_due"]):
                failures.append(f"refresh due on {due}")
            if any(n["refresh_due"] != (n["state"] == "needs_review") for n in live["nodes"]):
                failures.append("refresh due disagrees with the state shown")
            rings = {m["kc_id"]: [] for m in live["mistakes"]}
            for m in live["mistakes"]:
                rings[m["kc_id"]].append(m["status"])
            if rings != expect["rings"]:
                failures.append(f"rings {rings}")
            marked = {n["kc_id"]: n["changed_since"] for n in live["nodes"] if n["changed_since"]}
            if marked != expect["changed"]:
                failures.append(f"since last time {marked}")
            today = datetime.fromtimestamp(w.now / 1000, UTC).date()
            then = await w.map(as_of=(today - timedelta(weeks=int(expect["weeks_back"]))).isoformat())
            for kc, band in expect["then"].items():
                if node(then, kc)["band"] != band:
                    failures.append(f"{kc} four weeks ago {node(then, kc)['band']}, expected {band}")
            tiles = [
                t for s in (await w.overview())["subjects"] for t in s["topics"] if t["topic_id"].endswith(".motion")
            ]
            motion = [n for n in live["nodes"] if n["topic_id"].endswith(".motion")]
            if not tiles or tiles[0]["refresh_due"] != any(n["refresh_due"] for n in motion):
                failures.append("the overview's motion tile disagrees with the map")
            if w.events() != recorded:
                failures.append("opening the map wrote a learning event")

    run_async(scenario())
    return failures


RUNNERS = {"map_month_later": _map_month_later}
