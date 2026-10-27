"""The Checker's role prompt lists the verdict contract's error categories, exactly and in order (SPEC §12).

With tools offered the Checker writes its verdict unconstrained, so it sees only the prompt: before the list, Spark
invented categories (`calculation`, `wrong_value`, ...) in 6 of 13 verdicts and each cost a decode-only redo. A role
prompt is static text, so the list is copied there and this test keeps it equal to the contract's enum."""

from __future__ import annotations

import re

from agent_core.contracts import document
from jana_tools import REPO_ROOT


def test_the_checker_prompt_lists_the_contracts_error_categories() -> None:
    body = (REPO_ROOT / "content" / "agent" / "roles" / "checker.md").read_text()
    found = re.search(r"^Error categories, exactly as written: (.+?)\.$", body, re.M | re.S)
    assert found is not None, "the Checker's role prompt names no error categories"
    listed = [c.strip() for c in found.group(1).replace("\n", " ").split(",")]
    assert listed == document("agents/verdict")["properties"]["error_category"]["enum"]
