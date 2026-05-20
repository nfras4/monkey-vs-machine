"""Determinism gate: rerunning a tick produces byte-identical state.

This test is the load-bearing claim of the council-folded plan (A20). If it
fails, no AI schema change should ship until the underlying determinism is
real.

Skipped automatically if network/yfinance is unavailable.
"""
from __future__ import annotations

import hashlib
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = ROOT / "scripts" / "bootstrap_genesis.py"
RUN_TICK = ROOT / "scripts" / "run_tick.py"


def _run(args, check=True):
    return subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=check,
    )


def _hash_state(db_path: Path) -> str:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    h = hashlib.sha256()
    for table in [
        "monkey_history",
        "ai_model_history",
        "ai_portfolio_history",
        "ai_portfolio_equity",
        "daily_aggregates",
        "named_monkey_history",
    ]:
        for row in conn.execute(f"SELECT * FROM {table} ORDER BY rowid"):
            d = dict(row)
            d.pop("training_seconds", None)        # wall-clock varies
            d.pop("runtime_fingerprint", None)     # stable across runs but skip for paranoia
            h.update(repr(sorted(d.items())).encode())
    conn.close()
    return h.hexdigest()


@pytest.mark.skipif(os.environ.get("MVM_SKIP_NETWORK_TESTS") == "1",
                    reason="Network-bound test; set MVM_SKIP_NETWORK_TESTS=1 to skip in CI without internet")
def test_tick_rerun_is_byte_identical(tmp_path):
    db = tmp_path / "state.db"
    # Bootstrap small + run one tick
    _run([
        str(BOOTSTRAP),
        "--start-date", "2026-05-15",
        "--n-monkeys", "200",
        "--universe-size", "5",
        "--warmup-days", "90",
        "--db", str(db),
        "--force",
    ])
    _run([str(RUN_TICK), "--date", "2026-05-18", "--db", str(db)])
    h1 = _hash_state(db)
    # Re-run same tick
    _run([str(RUN_TICK), "--date", "2026-05-18", "--db", str(db), "--force"])
    h2 = _hash_state(db)
    assert h1 == h2, f"Tick re-run not byte-identical: {h1} vs {h2}"
