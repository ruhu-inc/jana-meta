"""On a many-core Linux server, native thread pools must not push a worker past its memory cap."""

from __future__ import annotations

import os
import subprocess
import sys


def test_the_worker_sets_one_thread_before_any_native_library_loads() -> None:
    env = {
        k: v for k, v in os.environ.items() if k not in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "OMP_THREAD_LIMIT")
    }
    code = (
        "import importlib, os, sys; importlib.import_module('study_worker.__main__'); "
        "print(os.environ['OPENBLAS_NUM_THREADS'], os.environ['OMP_NUM_THREADS'], os.environ['OMP_THREAD_LIMIT'])"
    )
    done = subprocess.run(
        [sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=120, check=True
    )
    assert done.stdout.split() == ["1", "1", "1"]
