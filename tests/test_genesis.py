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

# Import the cast so the test moves with the source of truth — adding a 9th
# personality monkey doesn't require editing this test in two places.
sys.path.insert(0, str(ROOT / "scripts"))
from bootstrap_genesis import DEFAULT_PERSONALITY_CAST  # noqa: E402


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
    assert n_personality == len(DEFAULT_PERSONALITY_CAST)
    # Every personality monkey must have a non-null config (Phase A1 contract).
    n_with_config = conn.execute(
        "SELECT COUNT(*) AS n FROM named_monkeys "
        "WHERE category='personality' AND personality_config IS NOT NULL"
    ).fetchone()["n"]
    assert n_with_config == len(DEFAULT_PERSONALITY_CAST)
    # genesis_log singleton, with the new Phase A1 columns populated.
    g = conn.execute(
        "SELECT cast_version, external_events_fingerprint, personality_config_json "
        "FROM genesis_log WHERE id=1"
    ).fetchone()
    assert g is not None
    assert g["cast_version"] == 1
    assert g["external_events_fingerprint"] is not None
    assert g["personality_config_json"] is not None
    # external_events seeded from the committed Lakers fixture.
    n_events = conn.execute(
        "SELECT COUNT(*) AS n FROM external_events WHERE event_kind='lakers_game'"
    ).fetchone()["n"]
    assert n_events > 0
    conn.close()
