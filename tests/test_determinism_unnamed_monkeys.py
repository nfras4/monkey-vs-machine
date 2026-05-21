"""Two independent bootstrap+tick sequences must produce identical monkey_history
for the 99,992 unnamed monkeys. Catches RNG-stream drift that the simple
"hash state.db" check would miss.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = ROOT / "scripts" / "bootstrap_genesis.py"
RUN_TICK = ROOT / "scripts" / "run_tick.py"


def _hash_unnamed_rows(db: Path, date: str) -> str:
    c = sqlite3.connect(str(db))
    c.row_factory = sqlite3.Row
    named = {int(r["monkey_id"]) for r in c.execute("SELECT monkey_id FROM named_monkeys").fetchall()}
    rows = c.execute(
        "SELECT monkey_id, cash, shares, position_ticker, equity, action "
        "FROM monkey_history WHERE date=? ORDER BY monkey_id",
        (date,),
    ).fetchall()
    payload = [tuple(r) for r in rows if int(r["monkey_id"]) not in named]
    c.close()
    return hashlib.sha256(repr(payload).encode("utf-8")).hexdigest()


@pytest.mark.skipif(os.environ.get("MVM_SKIP_NETWORK_TESTS") == "1",
                    reason="Network-bound: yfinance fetch required for bootstrap")
def test_unnamed_monkeys_bit_identical_across_independent_runs(tmp_path):
    db_a = tmp_path / "scratch_a.db"
    db_b = tmp_path / "scratch_b.db"

    common_args = [
        sys.executable, str(BOOTSTRAP),
        "--start-date", "2026-05-15",
        "--n-monkeys", "500",
        "--universe-size", "5",
        "--warmup-days", "90",
        "--force",
    ]
    # Bootstrap A
    subprocess.run(common_args + ["--db", str(db_a)], cwd=ROOT, check=True, capture_output=True, text=True)
    # Bootstrap B (independent)
    subprocess.run(common_args + ["--db", str(db_b)], cwd=ROOT, check=True, capture_output=True, text=True)

    # Tick both DBs on a known weekday with bars (2026-05-18 was the last
    # successful tick in the live DB, so a fresh bootstrap can resolve a bar).
    tick_date = "2026-05-18"
    for db in (db_a, db_b):
        result = subprocess.run(
            [sys.executable, str(RUN_TICK), "--date", tick_date, "--db", str(db)],
            cwd=ROOT, capture_output=True, text=True,
        )
        # Exit 0 (ok) or 3 (skipped_no_bar); fail noisily on 1/2.
        assert result.returncode in (0, 3), f"run_tick failed for {db}: {result.stderr}"
        if result.returncode == 3:
            pytest.skip(f"No bar for {tick_date} — can't compare drift on a skipped tick")

    h_a = _hash_unnamed_rows(db_a, tick_date)
    h_b = _hash_unnamed_rows(db_b, tick_date)
    assert h_a == h_b, (
        f"Unnamed-monkey RNG drift detected: {h_a[:16]} != {h_b[:16]}. "
        "Phase 2 has shifted the 99,992-monkey vector decisions, "
        "violating DETERMINISM.md."
    )
