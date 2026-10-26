"""Decoding schemas are self-contained: a provider's structured output and llama.cpp's grammar resolve only local
references, so every reference to another contract document is copied in, with the same verdicts as the contract."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from agent_core.contracts._validation import errors as contract_errors
from agent_core.engine.assembly import bundled_schemas
from jsonschema import Draft202012Validator

FIXTURES = Path(__file__).resolve().parents[3] / "evals" / "contracts"


def _refs(node: object) -> list[str]:
    if isinstance(node, dict):
        return [v for k, v in node.items() if k == "$ref" and isinstance(v, str)] + [
            r for v in node.values() for r in _refs(v)
        ]
    return [r for v in node for r in _refs(v)] if isinstance(node, list) else []


def test_every_decoding_schema_refers_only_to_itself() -> None:
    for name, schema in bundled_schemas().items():
        outside = [ref for ref in _refs(schema) if not ref.startswith("#")]
        assert outside == [], f"{name} still refers to another document: {outside[:3]}"
        Draft202012Validator.check_schema(schema)


@pytest.mark.parametrize("contract", ["agents/tutor-turn", "agents/diagnosis", "agents/solution-plan"])
def test_self_contained_schema_gives_the_contracts_verdicts(contract: str) -> None:
    schema = json.loads(json.dumps(bundled_schemas()[contract]))
    if contract == "agents/tutor-turn":
        schema["properties"]["sketch_wanted"] = {"type": "boolean"}  # dropped for decoding only (VSL-01)
    copy = Draft202012Validator(schema)
    folder = FIXTURES / contract
    cases = sorted(folder.glob("*/*.json"))
    assert cases, f"no fixtures for {contract}"
    for case in cases:
        instance = json.loads(case.read_text())
        instance = instance.get("instance", instance) if isinstance(instance, dict) else instance
        assert (not list(copy.iter_errors(instance))) == (not contract_errors(contract, instance)), case.name
