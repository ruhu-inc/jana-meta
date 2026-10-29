"""The W8 Study-memory scenarios (SPEC §19.9, suite `companion` in evals/suites.toml): each case's rubric, by code."""

from __future__ import annotations

from pathlib import Path

import pytest
from w8_scenarios import cases, run

CASES = cases()


def test_every_case_built_so_far_is_present() -> None:
    assert {c["case"] for c in CASES} == {"study_quiz_activity", "last_time_card", "research_level_known",
                                          "companion_recall_local", "cloud_block_dat18", "checkin_sunday"}  # fmt: skip
    assert all(c.get("rubric") for c in CASES)


@pytest.mark.parametrize("case", CASES, ids=[c["case"] for c in CASES])
def test_w8_scenario_rubric(case: dict, tmp_path: Path) -> None:
    assert run(case, tmp_path) == []
