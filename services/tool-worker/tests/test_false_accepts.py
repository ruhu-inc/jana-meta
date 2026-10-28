"""Wrong answers are never marked correct (VER-04, VER-09, VER-10) and no input escapes the per-call budget (SEC-08).

Each case here was a reproduced false accept or a computation that ran outside the budget's Python checkpoints."""

from __future__ import annotations

import json
import subprocess
import sys
from typing import Any

import pytest
from tool_worker.functions.answers import math_check_answer
from tool_worker.functions.maths import math_check_equivalence
from tool_worker.registry import CallContext


def _context(**settings: Any) -> CallContext:
    return CallContext("x", "t", {}, {}, lambda: False, settings=settings or None)


# --- a decimal for an exact key needs the item's figures ------------------------------------------------------------


@pytest.mark.parametrize(("student", "key"), [("3", "pi"), ("1.4", "sqrt(2)"), ("3.1", "pi")])
def test_decimal_for_exact_key_with_too_few_figures_is_not_accepted(student: str, key: str) -> None:
    value, _ = math_check_answer({"student": student, "key": key}, _context())
    assert value["verdict"] == "incorrect"
    assert value["components"]["precision"]["sf"] == "too_few"


@pytest.mark.parametrize(("student", "key"), [("3.14", "pi"), ("1.41", "sqrt(2)"), ("1.414", "sqrt(2)")])
def test_decimal_for_exact_key_at_the_item_precision_is_accepted(student: str, key: str) -> None:
    value, _ = math_check_answer({"student": student, "key": key}, _context())
    assert value["verdict"] == "correct"
    assert value["components"]["precision"]["sf"] == "ok"


def test_decimal_for_exact_key_follows_the_items_min_sf() -> None:
    value, _ = math_check_answer({"student": "1.4", "key": "sqrt(2)", "rule": {"min_sf": 2}}, _context())
    assert value["verdict"] == "correct"
    value, _ = math_check_answer({"student": "1.41", "key": "sqrt(2)", "rule": {"min_sf": 4}}, _context())
    assert value["verdict"] == "incorrect" and value["components"]["precision"]["sf"] == "too_few"


def test_decimal_for_exact_key_still_needs_the_right_value() -> None:
    value, _ = math_check_answer({"student": "3.15", "key": "pi"}, _context())
    assert value["verdict"] == "incorrect" and value["components"]["value"] == "incorrect"


# --- tiny magnitudes are compared relatively ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("a", "b"), [("2e-12*x", "1e-12*x"), ("6.6e-34*x", "6.63e-34*x"), ("1e-12*(x+1)", "2e-12*(x+1)")]
)
def test_tiny_coefficients_that_differ_are_not_equivalent(a: str, b: str) -> None:
    value, _ = math_check_equivalence({"a": a, "b": b}, _context())
    assert value["verdict"] == "not_equivalent"


def test_tiny_coefficient_answer_is_marked_incorrect() -> None:
    value, _ = math_check_answer({"student": "2e-12*x", "key": "1e-12*x"}, _context())
    assert value["verdict"] == "incorrect"


@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("sin(x)^2 + cos(x)^2", "1"),
        ("x*(sin(x)^2 + cos(x)^2 - 1)", "0"),
        ("1e-12*(sin(x)^2 + cos(x)^2)", "1e-12"),
        ("atan(x) + atan(1/x)", "pi/2"),
    ],
)
def test_identities_that_cancel_to_zero_still_agree(a: str, b: str) -> None:
    value, _ = math_check_equivalence({"a": a, "b": b, "assumptions": {"x": ["positive"]}}, _context())
    assert value["verdict"] == "equivalent"


# --- a point where only one side is real is a counterexample --------------------------------------------------------


def test_log_of_square_is_not_twice_the_log_on_the_reals() -> None:
    value, _ = math_check_equivalence({"a": "ln(x^2)", "b": "2*ln(x)"}, _context())
    assert value["verdict"] == "not_equivalent"
    example = value["counterexample"]
    assert float(example["at"]["x"]) < 0 and example["b"] == "not real"


def test_log_of_square_answer_is_marked_incorrect() -> None:
    value, _ = math_check_answer({"student": "2*ln(x)", "key": "ln(x^2)"}, _context())
    assert value["verdict"] == "incorrect"


def test_log_of_square_is_twice_the_log_for_positive_x() -> None:
    value, _ = math_check_equivalence({"a": "ln(x^2)", "b": "2*ln(x)", "assumptions": {"x": ["positive"]}}, _context())
    assert value["verdict"] == "equivalent"


# --- huge powers are refused before they are computed ---------------------------------------------------------------

_HUGE = {
    "unit_power_chain": (
        "from tool_worker.functions.units import units_convert\n"
        "units_convert({'quantity': '1 m^9^9^9', 'to': 'm'}, context)\n"
    ),
    "unit_power_chain_starred": (
        "from tool_worker.functions.units import units_convert\n"
        "units_convert({'quantity': '1 m', 'to': 'm**9**9**9'}, context)\n"
    ),
    "unit_nested_power": (
        "from tool_worker.functions.units import units_convert\n"
        "units_convert({'quantity': '1 m', 'to': 'm^((((9^99)^99)^99)^99)'}, context)\n"
    ),
    "unit_long_exponent": (
        "from tool_worker.functions.units import units_convert\n"
        "units_convert({'quantity': '1 m', 'to': 'm*9^999999999'}, context)\n"
    ),
    "unit_huge_power_of_ten": (
        "from tool_worker.functions.units import units_convert\n"
        "units_convert({'quantity': '1 x 10^99999999999 m', 'to': 'km'}, context)\n"
    ),
    "evaluate_huge_exponent": (
        "from tool_worker.functions.maths import math_evaluate\n"
        "math_evaluate({'expression': 'x^(10^29)', 'values': {'x': 2}}, context)\n"
    ),
    "integer_sampling": (
        "from tool_worker.functions.maths import math_check_equivalence\n"
        "math_check_equivalence({'a': '(n+1)^(10^29)', 'b': 'n', 'assumptions': {'n': ['integer']}}, context)\n"
    ),
}


@pytest.mark.parametrize("case", sorted(_HUGE))
def test_huge_powers_answer_promptly(case: str) -> None:
    """Run in a child process with a hard timeout, so a regression fails here instead of hanging the suite."""
    script = (
        "import json\n"
        "from tool_worker.protocol import WorkerError\n"
        "from tool_worker.registry import CallContext\n"
        "context = CallContext('x', 't', {}, {}, lambda: False)\n"
        "try:\n"
        + "".join(f"    {line}\n" for line in _HUGE[case].splitlines())
        + "    print(json.dumps({'outcome': 'answered'}))\n"
        "except WorkerError as error:\n"
        "    print(json.dumps({'outcome': 'refused', 'code': int(error.code)}))\n"
    )
    run = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=30, check=True)
    out = json.loads(run.stdout.strip().splitlines()[-1])
    if case == "unit_huge_power_of_ten":
        assert out == {"outcome": "refused", "code": 5}  # LIMIT_EXCEEDED
    elif case.startswith("unit_"):
        assert out == {"outcome": "refused", "code": 3}  # PARSE_REJECTED
    elif case == "evaluate_huge_exponent":
        assert out == {"outcome": "refused", "code": 5}  # LIMIT_EXCEEDED
    else:
        assert out == {"outcome": "answered"}  # sampled, never expanded


def test_small_powers_still_evaluate_and_convert() -> None:
    from tool_worker.functions.maths import math_evaluate
    from tool_worker.functions.units import units_convert

    value, _ = math_evaluate({"expression": "x^10", "values": {"x": 2}}, _context())
    assert value["exact"]["text"] == "1024"
    value, _ = units_convert({"quantity": "1 m^3", "to": "cm^3"}, _context())
    assert value["value"]["text"] == "1000000"
    value, _ = units_convert({"quantity": "4 m^(1/2)", "to": "m**(1/2)"}, _context())
    assert value["value"]["text"] == "4"
    value, _ = units_convert({"quantity": "3 (m/s)^2", "to": "m^2 s^-2"}, _context())
    assert value["value"]["text"] == "3"


def test_decimal_equal_to_an_exact_key_needs_no_more_figures() -> None:
    value, _ = math_check_answer({"student": "0.5", "key": "1/2"}, _context())
    assert value["components"]["value"] == "correct" and value["components"]["precision"]["sf"] == "ok"
    assert value["because"] == ["form"]  # only the exact form asked by a fraction key is unmet (TABLE VER-09a)
