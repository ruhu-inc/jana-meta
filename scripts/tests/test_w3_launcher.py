"""W3 (SPEC §7): the browser host's launcher starts Muse Glimmer 30B with its own chat template, its vision projector
and its DFlash draft, never with reasoning turned off, and only from files matching their pinned SHA-256."""

from __future__ import annotations

from pathlib import Path

import pytest
from jana_tools import hackathon_dev
from jana_tools.hackathon_dev import DRAFT, PROJECTOR, runtime_arguments, verify_model

WEIGHTS = "Muse-Glimmer-30B-KQuant-17GB-Q4_K_M.gguf"


def test_glimmer_runs_with_its_template_projector_and_dflash_draft(tmp_path: Path) -> None:
    model = tmp_path / WEIGHTS
    for name in (WEIGHTS, PROJECTOR, DRAFT):
        (tmp_path / name).write_bytes(b"")
    args = runtime_arguments(model, 18090, tmp_path / "key")
    assert "--jinja" in args and "--reasoning" not in args
    assert args[args.index("--alias") + 1].split(",")[0] == hackathon_dev.MODEL == "muse-glimmer-30b"
    assert args[args.index("--mmproj") + 1] == str(tmp_path / PROJECTOR)
    assert args[args.index("--model-draft") + 1] == str(tmp_path / DRAFT)
    assert args[args.index("--spec-type") + 1] == "draft-dflash"
    assert args[args.index("--spec-draft-n-max") + 1] == "4"
    assert int(args[args.index("--parallel") + 1]) >= 4  # coach, solver, diagnoser and the auxiliary roles
    (tmp_path / DRAFT).unlink()  # no draft: plain decoding
    assert "--model-draft" not in runtime_arguments(model, 18090, tmp_path / "key")


def test_only_pinned_files_load(tmp_path: Path) -> None:
    stranger = tmp_path / "other.gguf"
    stranger.write_bytes(b"x")
    with pytest.raises(ValueError, match="not a pinned"):
        verify_model(stranger)
    changed = tmp_path / WEIGHTS
    changed.write_bytes(b"x")
    with pytest.raises(ValueError, match="pinned SHA-256"):
        verify_model(changed)
