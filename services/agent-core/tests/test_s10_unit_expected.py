"""SPEC §10.7: a numeric part says whether its answer has a unit, so the client shows the unit field and the unit
chips only then. `unit_prompt` alone cannot tell "no unit" from "a unit, not necessarily this one". Items are
synthetic."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from agent_core.config import Settings
from agent_core.contracts import errors
from agent_core.engine.assessment.items import present
from agent_core.engine.learn import student_item


def numeric(unit: str | None, policy: str) -> dict[str, Any]:
    answer = {"kind": "numeric", "value": "12", "unit": unit, "unit_policy": policy,
              "tolerance": {"kind": "absolute", "value": "0"}, "check_id": "chk_synthetic"}  # fmt: skip
    return {"id": "itm.mth.o.number.0001", "type": "numeric", "stem": "Synthetic.", "kc_ids": ["kc.mth.o.number.x"],
            "parts": [{"id": "a", "prompt": "Give the answer.", "marks": 1, "answer": answer}]}  # fmt: skip


CASES = [
    (None, "none", False, None),  # a count: no unit at all
    ("", "none", False, None),
    ("cm", "equivalent", True, None),  # a length in any equivalent unit
    ("°C", "exact", True, "°C"),  # in exactly this unit
]


@pytest.mark.parametrize(("unit", "policy", "expected", "prompt"), CASES)
def test_numeric_parts_say_whether_a_unit_is_expected(unit: str | None, policy: str, expected: bool,
                                                      prompt: str | None) -> None:  # fmt: skip
    content = SimpleNamespace(subject_packs={}, charts={})
    for shown in (present(numeric(unit, policy), content, Settings()), student_item(numeric(unit, policy), None)):
        assert shown is not None
        part_input = shown["parts"][0]["input"]
        assert part_input == {"kind": "numeric", "unit_prompt": prompt, "unit_expected": expected}
        assert errors("api/commands#/$defs/PracticeItem", shown) == []
