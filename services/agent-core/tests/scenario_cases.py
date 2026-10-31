"""The scenario cases of every week (SPEC §19.9 W8, §20.9 W9, §21.9 W10): one loader over `tests/scenarios/*/`,
generalised from `w8_scenarios.py` (review finding 18). Each case is a YAML file whose directory names its week, with
its rubric written before any run (`case`, `rubric`, `expect`); a handler per case runs it against the real engine
pieces and checks the rubric by code. `run(case, tmp)` returns the rubric's failures: an empty list is a pass. The W8
handlers stay in `w8_scenarios.py`, the W9 one in `w9_scenarios.py`, the W10 ones in `w10_scenarios.py`; this module
only finds cases and dispatches them."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

SCENARIOS = Path(__file__).parent / "scenarios"


def cases(week: str | None = None) -> list[dict[str, Any]]:
    """Every case under `tests/scenarios/<week>/`, or under every week's directory; each carries its `week`."""
    out = []
    for path in sorted(SCENARIOS.glob(f"{week or '*'}/*.yaml")):
        case = yaml.safe_load(path.read_text())
        case["week"] = path.parent.name
        out.append(case)
    return out


def runners() -> dict[str, Callable[[dict[str, Any], Path], list[str]]]:
    import w8_scenarios
    import w9_scenarios
    import w10_scenarios

    found: dict[str, Callable[[dict[str, Any], Path], list[str]]] = {}
    for module in (w8_scenarios, w9_scenarios, w10_scenarios):
        for name, handler in module.RUNNERS.items():
            assert name not in found, f"two handlers for the case {name}"
            found[name] = handler
    return found


def run(case: dict[str, Any], tmp: Path) -> list[str]:
    return runners()[case["case"]](case, tmp)
