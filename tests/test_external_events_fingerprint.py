"""External-events fingerprint guard: mutating the table between ticks must
raise DeterminismError on the next run.
"""
from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
BOOTSTRAP = ROOT / "scripts" / "bootstrap_genesis.py"

from mvm.runner_tick import DeterminismError, run_tick  # noqa: E402


@pytest.mark.skipif(os.environ.get("MVM_SKIP_NETWORK_TESTS") == "1",
                    reason="Network-bound: yfinance fetch required for bootstrap")
def test_fingerprint_mismatch_raises(tmp_path):
    db = tmp_path / "scratch.db"
    subprocess.run(
        [sys.executable, str(BOOTSTRAP),
         "--start-date", "2026-05-15", "--n-monkeys", "500",
         "--universe-size", "5", "--warmup-days", "90",
         "--db", str(db), "--force"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    )

    # Baseline: bootstrap wrote the fingerprint, so a tick is allowed.
    result = run_tick("2026-05-18", db_path=db)
    assert result.status in ("ok", "skipped_no_bar")

    # Inject a row, breaking the fingerprint deterministically.
    c = sqlite3.connect(str(db))
    c.execute(
        "INSERT OR REPLACE INTO external_events (date, event_kind, outcome, payload_json) "
        "VALUES ('2025-01-01', 'unauthorized_event', 1, NULL)"
    )
    c.commit()
    c.close()

    # Next tick must refuse rather than silently apply the drifted state.
    with pytest.raises(DeterminismError) as exc_info:
        run_tick("2026-05-19", db_path=db)
    assert "fingerprint mismatch" in str(exc_info.value)
