"""Show the inference ledger, and release unresolved holds once provider billing shows they were never charged.

    uv run python -m cloud_gateway.holds --config services/cloud-gateway/deploy/meta-dev.toml
    uv run python -m cloud_gateway.holds --config ... --release-all

A call that fails, times out or ends without usage keeps its full upper bound so an unknown charge can never be
overspent. Releasing is the operator's reconciliation step: check the provider's usage page first. Settled spend is
never changed here; only holds are released.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from cloud_gateway.config import load_config
from cloud_gateway.inference_budget import InferenceBudget
from cloud_gateway.store import GatewayStore


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--release-all", action="store_true", help="release every unresolved hold")
    args = parser.parse_args()
    config = load_config(args.config)
    store = GatewayStore(config.storage_dir)
    try:
        budget = InferenceBudget(config, store, time.time)
        if args.release_all:
            count, held = budget.release_all()
            print(f"released {count} holds (${held:.4f})")
        snapshot = budget.snapshot()
        print(f"spent ${snapshot['spent_usd']:.4f} in total, ${snapshot['today_usd']:.4f} today (UTC); "
              f"held ${snapshot['held_usd']:.4f}")  # fmt: skip
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
