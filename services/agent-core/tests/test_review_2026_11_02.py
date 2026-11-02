"""The review of 2 November 2026: study consent, the withheld set, numeric marking and stated units. Synthetic data."""

from __future__ import annotations

import asyncio
import sqlite3
from decimal import Decimal
from fractions import Fraction
from types import SimpleNamespace
from typing import Any

import pytest
from agent_core.config import Settings
from agent_core.engine.gates import leak_findings
from agent_core.engine.marking import Converted, mark, parse_numeric
from agent_core.engine.state import Plan, PlanStep, Problem, SessionState
from agent_core.engine.turn import _stated_match
from agent_core.net.layer import OnlineLayer
from test_m6e_marking_mastery import SETTINGS, convert, numeric


def session(statement: str, final: str, *lines: str) -> SessionState:
    state = SessionState("ses_test")
    state.problem = Problem("prb", statement, "prb#statement")
    state.plan = Plan([PlanStep(1, "", None, None, None)], final, None, "chk_final")
    state.step = 1
    state.student_lines = [statement, *lines]
    return state


def held(state: SessionState) -> list[Fraction]:
    return [value for value, _ in state.withheld()]


# --- the withheld set ------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(("statement", "final"), [("Solve x + 5 = 10", "5"), ("Solve 3x = 9", "3")])
def test_an_answer_that_is_also_a_given_stays_withheld(statement: str, final: str) -> None:
    assert held(session(statement, final)) == [Fraction(final)]


def test_a_working_line_that_quotes_the_statement_does_not_reach_the_answer() -> None:
    assert held(session("Solve 3x + 5 = 14", "3", "3x = 9")) == [Fraction(3)]


def test_a_stated_value_reaches_the_answer() -> None:
    assert held(session("Solve 3x + 5 = 14", "3", "3x = 9", "x = 3")) == []


def test_an_earlier_problem_does_not_reach_this_answer() -> None:
    state = session("Solve 2x = 12", "6")
    state.student_lines = ["Solve y + 1 = 7", "y = 6", "Solve 2x = 12"]
    assert held(state) == [Fraction(6)]


def findings(text: str, value: str, givens: set[Fraction]) -> list[str]:
    found = leak_findings({"say": text}, [(Fraction(value), None)], Settings(), None, givens)
    return [f.kind for f in found]


def test_a_given_that_is_the_answer_may_be_quoted_but_not_stated() -> None:
    givens = {Fraction(5), Fraction(10)}
    assert findings("Look at x + 5 = 10. What could you take from both sides?", "5", givens) == []
    assert findings("Subtract 5 from both sides.", "5", givens) == []
    assert findings("Take five from both sides.", "5", givens) == []
    assert findings("So x = 5.", "5", givens) == ["exact"]
    assert findings("The answer is 5.", "5", givens) == ["exact"]


# --- numeric marking -------------------------------------------------------------------------------------------------


def run(item: dict, response: Any, converter: Any = convert) -> Any:
    return asyncio.run(mark(item, "a", response, converter, SETTINGS))


@pytest.mark.parametrize("response", ["3 or 4", "3+4", "3-1", "3^2", "3 * 4", "3, 4", "3 and 4", "3x", "3 4"])
def test_a_second_value_is_not_a_unit(response: str) -> None:
    verdict = run(numeric("3", None, "none"), response)
    assert (verdict.outcome, verdict.error_category) == ("incorrect", "unreadable")


@pytest.mark.parametrize(
    "response", ["3", "x = 3", "3 cm", "3 apples", "3 m/s^2", "3 N m", "3 m s-2", "3 m s^-2", "3 /s", "3 %", "3.0"]
)
def test_a_unit_is_still_a_unit(response: str) -> None:
    assert parse_numeric(response) is not None
    assert run(numeric("3", None, "none"), response).outcome == "correct"


def test_a_wrong_kind_of_quantity_is_still_a_unit_error() -> None:
    verdict = run(numeric("10", "m"), "10 kg")
    assert (verdict.outcome, verdict.error_category) == ("incorrect", "unit_error")


def test_a_worker_failure_is_unverifiable_not_wrong() -> None:
    async def down(_quantity: str, _to: str) -> Converted | None:
        return None

    assert run(numeric("10", "m"), "10 m", down).outcome == "unverifiable"


# --- stated values and their units -----------------------------------------------------------------------------------


def worker(failing: bool = False) -> Any:
    async def call(_name: str, args: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
        converted = None if failing else await convert(args["quantity"], args["to"])
        if converted is None:
            return None, None
        return {"value": {"decimal": str(Decimal(converted.value))}}, converted.check_id

    return call


@pytest.mark.parametrize(
    ("text", "value", "unit", "expected"),
    [
        ("10 m", "10", "m", "yes"),
        ("s = 10", "10", "m", "yes"),
        ("10 km", "10", "m", "no"),
        ("10 kg", "10", "m", "no"),
        ("10 seconds", "10", "m", "no"),
        ("1000 mm", "1", "m", "yes"),
        ("10.2", "10.2041", "m", "yes"),
        ("10.3", "10.2041", "m", "no"),
        ("10", "10", None, "yes"),
    ],
)
def test_stated_match(text: str, value: str, unit: str | None, expected: str) -> None:
    from agent_core.engine.state import stated_value

    stated = stated_value(text)
    assert stated is not None
    assert asyncio.run(_stated_match(worker(), text, stated, Fraction(value), unit)) == expected


def test_stated_match_never_marks_wrong_when_no_tool_answers() -> None:
    assert asyncio.run(_stated_match(worker(True), "10 km", Fraction(10), Fraction(10), "m")) == "unknown"


# --- study consent ---------------------------------------------------------------------------------------------------


def learner(*rows: tuple[str, int | None, int | None, int | None]) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE consents (consent_id TEXT, scope TEXT, granted_by_role TEXT, method TEXT, notice_version TEXT,"
        " granted_at INTEGER, paused_at INTEGER, withdrawn_at INTEGER, expires_at INTEGER)"
    )
    for scope, paused, withdrawn, expires in rows:
        conn.execute(
            "INSERT INTO consents VALUES (?, ?, 'user', 'self', '1', 1, ?, ?, ?)",
            (f"con_{scope}", scope, paused, withdrawn, expires),
        )
    return conn


def layer(features: set[str]) -> Any:
    return SimpleNamespace(features_on=lambda: features, cloud_effective=lambda _p, _c: True, clock_ms=lambda: 1000)


ON = {"cloud_tier", "study_materials"}


@pytest.mark.parametrize(
    ("features", "row", "effective"),
    [
        (ON, ("study_materials", None, None, None), True),
        (ON, ("study_materials", None, None, 2000), True),
        (ON, None, False),
        (ON, ("study_materials", 5, None, None), False),
        (ON, ("study_materials", None, 5, None), False),
        (ON, ("study_materials", None, None, 500), False),
        ({"cloud_tier"}, ("study_materials", None, None, None), False),
    ],
)
def test_study_effective_reads_the_profiles_own_consent(features: set[str], row: Any, effective: bool) -> None:
    conn = learner(("cloud_tier", None, None, None), *([row] if row else []))
    assert OnlineLayer.study_effective(layer(features), "pro", conn) is effective
