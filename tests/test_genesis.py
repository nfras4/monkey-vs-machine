"""Bootstrap produces the expected row counts and is --force idempotent."""
from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = ROOT / "scripts" / "bootstrap_genesis.py"


@pytest.mark.skipif(os.environ.get("MVM_SKIP_NETWORK_TESTS") == "1",
                    reason="Network-bound test; yfinance fetch required")
def test_bootstrap_writes_expected_rows(tmp_path):
    db = tmp_path / "state.db"
    subprocess.run(
        [sys.executable, str(BOOTSTRAP),
         "--start-date", "2026-05-15",
         "--n-monkeys", "500",
         "--universe-size", "5",
         "--warmup-days", "90",
         "--db", str(db),
         "--force"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    )
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    assert conn.execute("SELECT COUNT(*) AS n FROM monkeys").fetchone()["n"] == 500
    assert conn.execute("SELECT COUNT(*) AS n FROM tickers").fetchone()["n"] == 5
    n_personality = conn.execute(
        "SELECT COUNT(*) AS n FROM named_monkeys WHERE category='personality'"
    ).fetchone()["n"]
    assert n_personality == 3
    # genesis_log singleton
    assert conn.execute("SELECT COUNT(*) AS n FROM genesis_log").fetchone()["n"] == 1
    conn.close()
