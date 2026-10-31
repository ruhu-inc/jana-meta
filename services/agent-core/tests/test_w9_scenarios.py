"""The W9 Study scenario (SPEC §20.9, suite `companion` in evals/suites.toml): its rubric, by code, through the
generalised loader over `tests/scenarios/*/`."""

from __future__ import annotations

from pathlib import Path

import pytest
from scenario_cases import cases, run

CASES = cases("w9")


def test_every_w9_case_is_present_and_loaded_beside_the_other_weeks() -> None:
    assert {c["case"] for c in CASES} == {"youtube_lecture"}
    assert all(c.get("rubric") and c["week"] == "w9" for c in CASES)
    assert {"w8", "w9", "w10"} <= {c["week"] for c in cases()}, "the loader covers every week's directory"


@pytest.mark.parametrize("case", CASES, ids=[c["case"] for c in CASES])
def test_w9_scenario_rubric(case: dict, tmp_path: Path) -> None:
    assert run(case, tmp_path) == []
