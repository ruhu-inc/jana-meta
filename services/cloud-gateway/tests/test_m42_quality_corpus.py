"""The synthetic development corpus's inventory and its regression fixtures (no provider is called)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
CORPUS = ROOT / "evals/study/m42-quality.json"


def walk(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def test_m42_quality_corpus_inventory():
    corpus = json.loads(CORPUS.read_text())
    cases = corpus["cases"]
    assert corpus["synthetic"] and len(cases) >= 100
    assert len({c["id"] for c in cases}) == len(cases)
    assert all(re.fullmatch(r"[a-z0-9-]+", c["id"]) for c in cases)
    assert {c["kind"] for c in cases} == set(corpus["kinds"])
    for subject in ("biology", "chemistry", "mathematics", "physics", "accounting", "outside-syllabus"):
        assert {c["kind"] for c in cases if c["subject"] == subject} == set(corpus["kinds"])
    assert sum(c["expected"] == "insufficient_evidence" for c in cases) >= 10


def test_probability_regressions_preserve_original_observations_and_contrast_missing_premises():
    previous = json.loads((CORPUS.parent / "history/m42-quality-v2.json").read_text())
    current = json.loads((CORPUS.parent / "history/m42-quality-v3.json").read_text())
    original = {c["id"]: c for c in previous["cases"]}
    cases = {c["id"]: c for c in current["cases"]}
    assert current["version"] == 3 and len(cases) == len(original) + 4
    assert all(cases[key] == case for key, case in original.items() if key != "mth-probability-chat")
    assert cases["mth-probability-chat"] == {**original["mth-probability-chat"], "expected": "insufficient_evidence"}
    assert cases["mth-probability-stated-conditions-chat"]["sources"] == original["mth-probability-chat"]["sources"]
    assert cases["mth-probability-stated-conditions-chat"]["expected"] == "grounded"
    assert cases["mth-probability-explicit-explanation-chat"]["expected"] == "grounded"
    for key in ("mth-probability-missing-draw-rule-chat", "mth-probability-contradictory-draw-rule-chat"):
        assert cases[key]["expected"] == "insufficient_evidence"


def test_unicode_speed_fixture_defines_the_requested_quantity_and_retains_missing_definition_contrasts():
    previous = json.loads((CORPUS.parent / "history/m42-quality-v3.json").read_text())
    current = json.loads(CORPUS.read_text())
    old = {c["id"]: c for c in previous["cases"]}
    new = {c["id"]: c for c in current["cases"]}
    assert current["version"] == 4 and len(new) == len(old) + 3
    changed = {key for key in old if new[key] != old[key]}
    assert changed == {f"unicode-{kind.replace('_', '-')}" for kind in current["kinds"]}
    for key in changed:
        assert {k: v for k, v in new[key].items() if k != "sources"} == {
            k: v for k, v in old[key].items() if k != "sources"
        }
        assert "distance travelled" in new[key]["sources"][0]
        assert "defines the average speed v" in new[key]["sources"][0]
    for key in ("undefined-v-speed-chat", "undefined-v-value-chat", "undefined-v-flashcards"):
        assert new[key]["sources"] == old["unicode-chat"]["sources"]
    assert new["undefined-v-speed-chat"]["prompt"] == old["unicode-chat"]["prompt"]
    assert new["undefined-v-speed-chat"]["expected"] == "insufficient_evidence"
    assert new["undefined-v-value-chat"]["expected"] == new["undefined-v-flashcards"]["expected"] == "grounded"
