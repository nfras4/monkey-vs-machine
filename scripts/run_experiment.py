"""CLI smoke test for the full pipeline."""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Make `src/` importable without an install
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mvm.runner import run_experiment  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true", help="Tiny universe + few monkeys, for smoke testing")
    parser.add_argument("--universe-size", type=int, default=None)
    parser.add_argument("--years", type=int, default=None)
    parser.add_argument("--n-monkeys", type=int, default=None)
    parser.add_argument("--top-k", type=int, default=None)
    parser.add_argument("--refresh", action="store_true", help="Bypass parquet cache")
    parser.add_argument("--wikipedia", action="store_true", help="Use Wikipedia for ticker list")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    if args.quick:
        cfg = dict(universe_size=10, years=2, n_monkeys=2_000, top_k=3)
    else:
        cfg = {}
    if args.universe_size is not None:
        cfg["universe_size"] = args.universe_size
    if args.years is not None:
        cfg["years"] = args.years
    if args.n_monkeys is not None:
        cfg["n_monkeys"] = args.n_monkeys
    if args.top_k is not None:
        cfg["top_k"] = args.top_k

    result = run_experiment(refresh=args.refresh, use_wikipedia=args.wikipedia, **cfg)

    print("\n=== AI Trader ===")
    for k, v in result.ai_backtest["metrics"].items():
        print(f"  {k:>16}: {v:>10.4f}")

    print("\n=== Monkey Pack ===")
    for k, v in result.monkeys.metadata.items():
        if isinstance(v, float):
            print(f"  {k:>16}: {v:>10.4f}")
        else:
            print(f"  {k:>16}: {v}")

    if result.spy_backtest is not None:
        print("\n=== SPY Benchmark ===")
        for k, v in result.spy_backtest["metrics"].items():
            print(f"  {k:>16}: {v:>10.4f}")

    print("\n=== AI Feature Importances ===")
    for name, val in sorted(result.ai.feature_importance.items(), key=lambda kv: -kv[1]):
        print(f"  {name:>10}: {val:>+.4f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
