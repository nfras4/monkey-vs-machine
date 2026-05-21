"""Joe's equity on a Lakers-win date must equal vector-path equity + $100 exactly.

Procedure:
1. Bootstrap a scratch DB with the v3 cast.
2. Find a Lakers-win date in external_events that's also reachable as a tick.
3. Save Joe's current personality_config; null it out (forces him onto the
   vanilla vector path).
4. Run the tick → capture Joe's monkey_history.equity as the baseline.
5. Wipe Joe's row + restore his personality_config; re-run the tick.
6. Capture Joe's equity again → must be baseline + 100.0 exactly.

Both runs traverse identical float arithmetic so == is safe (no FP drift).
"""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
BOOTSTRAP = ROOT / "scripts" / "bootstrap_genesis.py"

from mvm.runner_tick import run_tick  # noqa: E402


def _joe_row(db: Path, date: str):
    c = sqlite3.connect(str(db))
    c.row_factory = sqlite3.Row
    row = c.execute(
        "SELECT m.monkey_id, h.equity FROM named_monkeys m "
        "LEFT JOIN monkey_history h ON h.monkey_id=m.monkey_id AND h.date=? "
        "WHERE m.name='Lakers Joe'",
        (date,),
    ).fetchone()
    c.close()
    return row


def _find_lakers_win_date(db: Path, min_date: str) -> str | None:
    c = sqlite3.connect(str(db))
    row = c.execute(
        "SELECT date FROM external_events "
        "WHERE event_kind='lakers_game' AND outcome=1 AND date >= ? "
        "ORDER BY date LIMIT 1",
        (min_date,),
    ).fetchone()
    c.close()
    return row[0] if row else None


@pytest.mark.skipif(os.environ.get("MVM_SKIP_NETWORK_TESTS") == "1",
                    reason="Network-bound: yfinance fetch required for bootstrap")
def test_lakers_joe_equity_delta_is_exactly_win_bonus(tmp_path):
    db = tmp_path / "scratch.db"
    subprocess.run(
        [sys.executable, str(BOOTSTRAP),
         "--start-date", "2026-05-15", "--n-monkeys", "500",
         "--universe-size", "5", "--warmup-days", "90",
         "--db", str(db), "--force"],
        cwd=ROOT, check=True, capture_output=True, text=True,
    )

    # The fixture covers 2023-10 through 2025-06; pick a Lakers-win date that
    # also has price bars (i.e. within the warmup window from start-date).
    # We seeded with --start-date 2026-05-15 and 90 days warmup, so warmup
    # covers ~Feb 2026 through May 2026 — no Lakers regular-season games in
    # that window. Instead, run the tick on 2026-05-18 (a real weekday with
    # bars in the live DB) and inject a synthetic event on that date so the
    # test doesn't depend on the fixture window aligning with price coverage.
    tick_date = "2026-05-18"

    # Inject a synthetic Lakers win on tick_date and refresh the fingerprint.
    import hashlib
    c = sqlite3.connect(str(db))
    c.execute(
        "INSERT OR REPLACE INTO external_events (date, event_kind, outcome, payload_json) "
        "VALUES (?, 'lakers_game', 1, '{\"synthetic\": true}')",
        (tick_date,),
    )
    rows = c.execute(
        "SELECT date, event_kind, outcome FROM external_events ORDER BY date, event_kind"
    ).fetchall()
    h = hashlib.sha256()
    for d, k, o in rows:
        h.update(f"{d}|{k}|{o}\n".encode("utf-8"))
    c.execute("UPDATE genesis_log SET external_events_fingerprint=? WHERE id=1", (h.hexdigest(),))
    c.commit()

    # Save Joe's config so we can restore it for the second run.
    joe_row = c.execute(
        "SELECT monkey_id, personality_config FROM named_monkeys WHERE name='Lakers Joe'"
    ).fetchone()
    assert joe_row, "Lakers Joe not in named_monkeys — Phase 1 cast missing?"
    joe_id = joe_row[0]
    joe_config = joe_row[1]

    # === Run 1: Joe on the vanilla vector path (no bonus). ===
    c.execute("UPDATE named_monkeys SET personality_config=NULL WHERE name='Lakers Joe'")
    c.commit()
    c.close()

    result = run_tick(tick_date, db_path=db)
    if result.status == "skipped_no_bar":
        pytest.skip(f"No bar for {tick_date} — can't measure Joe's delta")
    assert result.status == "ok"
    baseline = _joe_row(db, tick_date)
    assert baseline is not None and baseline["equity"] is not None
    baseline_eq = float(baseline["equity"])

    # === Run 2: restore Joe's config, blow away the tick artefacts, re-run. ===
    c = sqlite3.connect(str(db))
    c.execute("UPDATE named_monkeys SET personality_config=? WHERE name='Lakers Joe'", (joe_config,))
    c.execute("DELETE FROM monkey_history WHERE date=?", (tick_date,))
    c.execute("DELETE FROM daily_aggregates WHERE date=?", (tick_date,))
    c.execute("DELETE FROM named_monkey_history WHERE date=?", (tick_date,))
    c.execute("DELETE FROM ai_portfolio_equity WHERE date=?", (tick_date,))
    c.execute("DELETE FROM ai_portfolio_history WHERE date=?", (tick_date,))
    c.execute("DELETE FROM ai_model_history WHERE date=?", (tick_date,))
    c.execute("DELETE FROM ticks WHERE date=?", (tick_date,))
    c.commit()
    c.close()

    result2 = run_tick(tick_date, db_path=db)
    assert result2.status == "ok"
    with_bonus = _joe_row(db, tick_date)
    assert with_bonus is not None
    bonus_eq = float(with_bonus["equity"])

    win_bonus = json.loads(joe_config)["win_bonus"]
    assert bonus_eq == pytest.approx(baseline_eq + win_bonus, abs=1e-9), (
        f"Joe's equity delta = {bonus_eq - baseline_eq}, expected = {win_bonus}"
    )
