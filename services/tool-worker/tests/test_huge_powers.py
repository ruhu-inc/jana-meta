"""No maths function escapes the per-call budget through a huge power (SEC-08).

The budget and the time slice fire only at Python calls, so SymPy work in C or in tight loops cannot be stopped:
expanding (x+1)^(10^29) (binomial coefficients) or computing 2^x exactly at x = 10^29. A symbolic huge power is refused
at parsing everywhere except where it is only sampled (equivalence and answer checks); a huge value arriving by
substitution is refused before SymPy computes it, or for Newton-Raphson and iteration taken as a float.

Each case runs in a child process with a hard timeout, so a regression fails here instead of hanging the suite. The
children start together and each test waits for its own."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from collections.abc import Iterator
from typing import Any

import pytest

LIMIT_EXCEEDED = 5
BIG = "100000000000000000000000000000"  # 10^29, a valid number argument

# case: (module, function, args, expected) where expected is "refused" (LIMIT_EXCEEDED) or "answered"
_CASES: dict[str, tuple[str, str, dict[str, Any], str]] = {
    # a symbolic huge power: expansion, factorisation, solving, calculus
    "simplify_simplest": ("maths", "math_simplify", {"expression": "(x+1)^(10^29)"}, "refused"),
    "simplify_expanded": ("maths", "math_simplify", {"expression": "(x+1)^(10^29)", "form": "expanded"}, "refused"),
    "simplify_factorised": (
        "maths",
        "math_simplify",
        {"expression": "(x+1)^(10^29)", "form": "factorised"},
        "refused",
    ),
    "simplify_series": (
        "maths",
        "math_simplify",
        {"expression": "(1+x)^(10^29)", "form": "series", "order": 2},
        "refused",
    ),
    "simplify_partial_fractions": (
        "maths",
        "math_simplify",
        {"expression": "1/(x+1)^(10^29)", "form": "partial_fractions"},
        "refused",
    ),
    "solve": ("maths", "math_solve", {"equations": ["(x+1)^(10^29) = 2"]}, "refused"),
    "solve_complex": ("maths", "math_solve", {"equations": ["z^(10^29) = 1"], "domain": "complex"}, "refused"),
    "solve_newton_raphson": (
        "maths",
        "math_solve",
        {"equations": ["x^(10^29) - 2 = 0"], "method": "newton_raphson", "start": 2, "steps": 3},
        "refused",
    ),
    "evaluate_no_values": ("maths", "math_evaluate", {"expression": "(x+1)^(10^29)"}, "refused"),
    "step_expression": ("steps", "math_check_step", {"prev": "(x+1)^(10^29)", "next": "x"}, "refused"),
    "step_equation": ("steps", "math_check_step", {"prev": "(x+1)^(10^29) = 2", "next": "x = 2"}, "refused"),
    "differentiate": ("calculus", "math_differentiate", {"expression": "(x+1)^(10^29)"}, "refused"),
    "differentiate_implicit": (
        "calculus",
        "math_differentiate",
        {"mode": "implicit", "expression": "x^(10^29) + y^2 = 25"},
        "refused",
    ),
    "differentiate_parametric": (
        "calculus",
        "math_differentiate",
        {"mode": "parametric", "x_expression": "t^(10^29)", "y_expression": "t"},
        "refused",
    ),
    "integrate": ("calculus", "math_integrate", {"expression": "(x+1)^(10^29)"}, "refused"),
    "integrate_parts": ("calculus", "math_integrate", {"expression": "x (x+1)^(10^29)", "parts_u": "x"}, "refused"),
    "ode": ("alevel_calculus", "math_solve_ode", {"rhs": "(x+1)^(10^29)"}, "refused"),
    # a huge value substituted into a power
    "differentiate_at": ("calculus", "math_differentiate", {"expression": "2^x", "at": BIG}, "refused"),
    "differentiate_at_expression": (
        "calculus",
        "math_differentiate",
        {"expression": "3^x", "at": "10^29"},
        "refused",
    ),
    "differentiate_implicit_point": (
        "calculus",
        "math_differentiate",
        {"mode": "implicit", "expression": "2^x + y = 1", "point": [BIG, "1"]},
        "refused",
    ),
    "differentiate_parametric_at": (
        "calculus",
        "math_differentiate",
        {"mode": "parametric", "x_expression": "2^t", "y_expression": "t", "at": BIG},
        "refused",
    ),
    "integrate_definite": ("calculus", "math_integrate", {"expression": "2^x", "lower": 0, "upper": BIG}, "refused"),
    "integrate_trapezium": (
        "calculus",
        "math_integrate",
        {"expression": "2^x", "method": "trapezium", "strips": 4, "lower": 0, "upper": BIG},
        "refused",
    ),
    "integrate_volume": (
        "calculus",
        "math_integrate",
        {"expression": "2^x", "volume": "x_axis", "lower": 0, "upper": BIG},
        "refused",
    ),
    "integrate_parts_limits": (
        "calculus",
        "math_integrate",
        {"expression": "x 2^x", "parts_u": "x", "lower": 0, "upper": BIG},
        "refused",
    ),
    "integrate_substitution_limits": (
        "calculus",
        "math_integrate",
        {"expression": "2^(2x)", "substitution": "u = 2x", "lower": 0, "upper": BIG},
        "refused",
    ),
    "ode_at": ("alevel_calculus", "math_solve_ode", {"rhs": "2^x", "condition": [0, 2], "at": BIG}, "refused"),
    "ode_condition": (
        "alevel_calculus",
        "math_solve_ode",
        {"rhs": "2^x", "condition": [BIG, 2], "at": 1},
        "refused",
    ),
    "solve_quantity": (
        "maths",
        "math_solve",
        {"equations": ["y = 2^n"], "unknowns": ["y"], "quantities": {"n": BIG}, "units": {"y": "1"}},
        "refused",
    ),
    "solve_sign_change": (
        "maths",
        "math_solve",
        {"equations": ["2^x - 3 = 0"], "method": "sign_change", "interval": [0, BIG]},
        "refused",
    ),
    "solve_newton_raphson_start": (
        "maths",
        "math_solve",
        {"equations": ["2^x - 3 = 0"], "method": "newton_raphson", "start": BIG, "steps": 3},
        "answered",
    ),
    "solve_iteration_start": (
        "maths",
        "math_solve",
        {"equations": ["x = 2^x"], "method": "iteration", "g": "2^x", "start": BIG, "steps": 2},
        "answered",
    ),
    # only sampled, never expanded: still answered
    "equivalence_real": ("maths", "math_check_equivalence", {"a": "(x+1)^(10^29)", "b": "x"}, "answered"),
    "answer_expanded_form": (
        "answers",
        "math_check_answer",
        {"student": "(x+1)^(10^29)", "key": "x", "rule": {"form": "expanded"}},
        "answered",
    ),
    "differentiate_student": (
        "calculus",
        "math_differentiate",
        {"expression": "x^2", "student": "(x+1)^(10^29)"},
        "answered",
    ),
    "integrate_student": (
        "calculus",
        "math_integrate",
        {"expression": "x^2", "student": "(x+1)^(10^29)"},
        "answered",
    ),
    "answer_factorised_form": (
        "answers",
        "math_check_answer",
        {"student": "(x+1)^(10^29)", "key": "(x+1)^(10^29)", "rule": {"form": "factorised"}},
        "answered",
    ),
    "answer_simplest_form": (
        "answers",
        "math_check_answer",
        {"student": "(x+1)^(10^29)/(x+1)", "key": "(x+1)^(10^29-1)", "rule": {"form": "simplest"}},
        "answered",
    ),
    # an equation is solved, not sampled: a huge power there is undecided, and answered
    "equivalence_relation": ("maths", "math_check_equivalence", {"a": "(x+1)^(10^29) = 2", "b": "x = 1"}, "answered"),
    "answer_relation": ("answers", "math_check_answer", {"student": "(x+1)^(10^29) = 2", "key": "x = 1"}, "answered"),
    "parse": ("maths", "math_parse", {"text": "(x+1)^(10^29)"}, "answered"),
}

TIMEOUT_S = 60  # from the start of all the children, which share the machine


def _script(module: str, function: str, args: dict[str, Any]) -> str:
    return (
        "import json\n"
        "from tool_worker.protocol import WorkerError\n"
        "from tool_worker.registry import CallContext\n"
        f"from tool_worker.functions.{module} import {function}\n"
        "context = CallContext('x', 't', {}, {}, lambda: False)\n"
        "try:\n"
        f"    {function}(json.loads({json.dumps(args)!r}), context)\n"
        "    print(json.dumps({'outcome': 'answered'}))\n"
        "except WorkerError as error:\n"
        "    print(json.dumps({'outcome': 'refused', 'code': int(error.code)}))\n"
    )


@pytest.fixture(scope="module")
def children() -> Iterator[dict[str, subprocess.Popen[str]]]:
    started = {
        case: subprocess.Popen(
            [sys.executable, "-c", _script(module, function, args)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for case, (module, function, args, _) in _CASES.items()
    }
    yield started
    for child in started.values():
        child.kill()
        child.communicate()


@pytest.fixture(scope="module")
def deadline(children: dict[str, subprocess.Popen[str]]) -> float:
    return time.monotonic() + TIMEOUT_S


@pytest.mark.parametrize("case", sorted(_CASES))
def test_huge_powers_answer_promptly(case: str, children: dict[str, subprocess.Popen[str]], deadline: float) -> None:
    child = children[case]
    try:
        out, err = child.communicate(timeout=max(1.0, deadline - time.monotonic()))
    except subprocess.TimeoutExpired:
        pytest.fail(f"{case} ran past {TIMEOUT_S} s: the computation escaped the budget")
    assert child.returncode == 0, err.strip().splitlines()[-1] if err.strip() else "no output"
    found = json.loads(out.strip().splitlines()[-1])
    expected = _CASES[case][3]
    assert found == ({"outcome": "refused", "code": LIMIT_EXCEEDED} if expected == "refused" else {"outcome": expected})
