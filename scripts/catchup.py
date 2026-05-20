"""CLI: catch up missing ticks from --since up to yesterday (US/Eastern).

For each business day between `since` and yesterday that has no `ticks.status='ok'`
row, runs the tick. Stops on first failure.
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mvm.runner_tick import run_tick  # noqa: E402
from mvm.state.db import DEFAULT_DB_PATH, get_conn  # noqa: E402


def _us_today_date() -> str:
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    except Exception:  # noqa: BLE001
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def existing_tick_dates(db_path: Path):
    with get_conn(db_path, enforce_single_writer=False) as conn:
        rows = conn.execute("SELECT date FROM ticks WHERE status='ok'").fetchall()
    return {row["date"] for row in rows}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--since", required=True, help="YYYY-MM-DD inclusive")
    parser.add_argument("--until", default=None, help="YYYY-MM-DD inclusive (defaults to today US/Eastern)")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    start = datetime.strptime(args.since, "%Y-%m-%d").date()
    end = datetime.strptime(args.until, "%Y-%m-%d").date() if args.until else datetime.strptime(_us_today_date(), "%Y-%m-%d").date()
    existing = existing_tick_dates(args.db)

    cur = start
    ran = 0
    skipped = 0
    while cur <= end:
        # Skip weekends — yfinance won't return a bar; the tick would just write skipped_no_bar.
        if cur.weekday() < 5:
            d = cur.strftime("%Y-%m-%d")
            if d not in existing:
                logging.info("Running tick for %s", d)
                try:
                    result = run_tick(d, db_path=args.db)
                except Exception:
                    logging.exception("Tick for %s failed — stopping catchup", d)
                    return 1
                if result.status == "ok":
                    ran += 1
                else:
                    skipped += 1
        cur += timedelta(days=1)

    logging.info("Catchup complete: %d ticks ran, %d skipped", ran, skipped)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
