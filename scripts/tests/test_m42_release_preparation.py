"""The Study acceptance inventory names real checks: every automated selector is a test file (and function) here."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_all_41_canonical_acceptance_names_have_real_check_targets():
    import ast
    import re

    inventory = json.loads((ROOT / "evals/study/m42-acceptance.json").read_text())
    canonical = {row["acceptance"] for row in inventory["cases"]}
    assert len(canonical) == inventory["required_count"] == len(inventory["cases"]) == 41
    assert all(re.fullmatch(r"[a-z]{3}\d{2}_[a-z0-9_]+", name) for name in canonical)
    for row in inventory["cases"]:
        assert row["remaining"] and not row["acceptance_complete"]
        for selector in row["automated_checks"]:
            file, _, function = selector.partition("::")
            path = ROOT / file
            assert path.is_file(), selector
            if function:
                assert any(
                    isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == function
                    for n in ast.walk(ast.parse(path.read_text()))
                ), selector
