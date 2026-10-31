"""The W10 learner's map scenarios (SPEC §21.9, suite `learner_map` in evals/suites.toml): each case's rubric, by code,
through the generalised loader over `tests/scenarios/*/`."""

from __future__ import annotations

from pathlib import Path

import pytest
from scenario_cases import cases, run

CASES = cases("w10")


def test_every_w10_case_is_present_and_every_week_is_loaded() -> None:
    assert {c["case"] for c in CASES} == {"map_month_later"}
    assert all(c.get("rubric") and c["week"] == "w10" for c in CASES)
    weeks = {c["week"] for c in cases()}
    assert {"w8", "w10"} <= weeks, "the loader covers every week's directory"


@pytest.mark.parametrize("case", CASES, ids=[c["case"] for c in CASES])
def test_w10_scenario_rubric(case: dict, tmp_path: Path) -> None:
    assert run(case, tmp_path) == []
