"""No tool schema offered to a model refers to itself (SPEC §16): Muse Spark answers 400 "Recursive JSON schemas are
not currently supported" to the whole request, so a physics Solver offered phys_circuit could not call any tool."""

from __future__ import annotations

from typing import Any

import pytest
import yaml
from agent_core.tools.generated.worker_schemas import WORKER_SCHEMAS
from agent_core.tools.spec import InitCtx
from agent_core.tools.specs import HOST_AND_CLIENT_PARAMS, specs
from agent_core.tools.unroll import DEPTH, unrolled
from jana_tools import REPO_ROOT
from jsonschema import Draft202012Validator

FIXTURES = REPO_ROOT / "services" / "agent-core" / "agent_core" / "tools" / "fixtures"
GOLDEN = REPO_ROOT / "services" / "tool-worker" / "tool_worker" / "golden" / "phys_circuit.yaml"


def _recursive_refs(schema: dict[str, Any]) -> set[str]:
    """Every `$ref` met again while resolving itself, following references from the root (an independent check)."""

    def resolve(ref: str) -> Any:
        node: Any = schema
        for part in ref.removeprefix("#").strip("/").split("/") if ref != "#" else []:
            node = node[part.replace("~1", "/").replace("~0", "~")]
        return node

    found: set[str] = set()

    def walk(node: Any, stack: tuple[str, ...]) -> None:
        if isinstance(node, dict):
            ref = node.get("$ref")
            if isinstance(ref, str):
                if ref in stack:
                    found.add(ref)
                else:
                    walk(resolve(ref), (*stack, ref))
            for key, value in node.items():
                if key != "$defs":
                    walk(value, stack)
        elif isinstance(node, list):
            for value in node:
                walk(value, stack)

    walk(schema, ())
    return found


def _network(depth: int) -> dict[str, Any]:
    """A cell in series with `depth` nested groups, alternating parallel and series, around two resistors."""
    inner: Any = "R1"
    for level in range(depth - 1):
        inner = {("parallel" if level % 2 == 0 else "series"): [inner, f"R{level + 2}"]}
    return {"series": ["B", inner]}


def _circuit(depth: int) -> dict[str, Any]:
    ids = ["R1", *(f"R{i + 2}" for i in range(depth - 1))]
    components = [{"id": "B", "kind": "cell", "emf": 6}, *({"id": i, "kind": "resistor", "resistance": 2} for i in ids)]
    return {"components": components, "network": _network(depth)}


def test_the_check_finds_the_worker_schema_recursive() -> None:
    assert _recursive_refs(WORKER_SCHEMAS["phys_circuit"]) == {"#/$defs/group"}


def test_no_offered_tool_schema_is_recursive() -> None:
    """Every role is offered a subset of the build's specs, in either profile, through `model_definition`."""
    recursive = {
        f"{spec.name}:{profile}": sorted(refs)
        for spec in specs()
        for profile in ("full", "small")
        if (refs := _recursive_refs(spec.model_definition(InitCtx(profile=profile))["parameters"]))
    }
    assert recursive == {}


def test_no_tool_schema_of_a_later_stage_reaches_a_model_recursive() -> None:
    """The worker and host schemas of tools not offered yet, as `model_definition` will show them."""
    schemas = {**WORKER_SCHEMAS, **HOST_AND_CLIENT_PARAMS}
    assert {name: sorted(refs) for name, s in schemas.items() if (refs := _recursive_refs(unrolled(s)))} == {}


def test_only_recursive_schemas_change() -> None:
    """The other tools reach the model exactly as before, so their prompts and fingerprints do not move."""
    for name, schema in WORKER_SCHEMAS.items():
        if name != "phys_circuit":
            assert unrolled(schema) is schema, name


def test_the_unrolled_circuit_schema_is_valid_and_keeps_the_worker_schema() -> None:
    spec = next(s for s in specs() if s.name == "phys_circuit")
    assert spec.params is WORKER_SCHEMAS["phys_circuit"]  # the worker's own, compared by schema_sha256
    params = spec.model_definition(InitCtx())["parameters"]
    Draft202012Validator.check_schema(params)
    assert params["properties"]["network"] == {"$ref": "#/$defs/group_1"}
    assert sorted(params["$defs"]) == sorted(
        ["number", "terminal", *(f"{d}_{level}" for d in ("group", "members") for level in range(1, DEPTH + 1))]
    )


def test_the_unrolled_circuit_schema_accepts_every_fixture_and_golden_case() -> None:
    model = Draft202012Validator(unrolled(WORKER_SCHEMAS["phys_circuit"]))
    worker = Draft202012Validator(WORKER_SCHEMAS["phys_circuit"])
    fixtures = yaml.safe_load((FIXTURES / "phys_circuit.yaml").read_text())
    cases = [*fixtures["valid_args"], *(c["args"] for c in yaml.safe_load(GOLDEN.read_text())["cases"])]
    assert len(cases) > 50
    for args in cases:
        assert model.is_valid(args) == worker.is_valid(args), args
    for args in fixtures["invalid_args"]:
        assert not model.is_valid(args), args


def test_groups_nest_to_the_depth_and_no_further() -> None:
    model = Draft202012Validator(unrolled(WORKER_SCHEMAS["phys_circuit"]))
    worker = Draft202012Validator(WORKER_SCHEMAS["phys_circuit"])
    assert model.is_valid(_circuit(DEPTH)) and worker.is_valid(_circuit(DEPTH))
    assert not model.is_valid(_circuit(DEPTH + 1)) and worker.is_valid(_circuit(DEPTH + 1))


def test_a_loop_that_cannot_be_cut_is_refused() -> None:
    schema = {"type": "object", "properties": {"node": {"$ref": "#/$defs/node"}},
              "$defs": {"node": {"type": "object", "properties": {"next": {"$ref": "#/$defs/node"}}}}}  # fmt: skip
    with pytest.raises(ValueError, match="anyOf or oneOf"):
        unrolled(schema)
