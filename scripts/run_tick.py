"""CLI: run one perpetual-mode tick for a given date.

Exit codes:
    0  ok
    1  failed (exception)
    2  already-ran (use --force to re-run)
    3  skipped (no bar for that date — weekend / holiday)
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mvm.runner_tick import run_tick  # noqa: E402
from mvm.state.db import DEFAULT_DB_PATH, get_conn  # noqa: E402


def _us_today_date() -> str:
    """Return today's date in US/Eastern. Daily bars are stamped to ET close."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    except Exception:  # noqa: BLE001
        # Fallback to UTC-5 approximation
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def already_ran(date: str, db_path: Path) -> bool:
    with get_conn(db_path, enforce_single_writer=False) as conn:
        row = conn.execute("SELECT status FROM ticks WHERE date=?", (date,)).fetchone()
    return row is not None and row["status"] == "ok"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None, help="YYYY-MM-DD (defaults to today US/Eastern)")
    parser.add_argument("--force", action="store_true", help="Re-run a date that already has status='ok'")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    date = args.date or _us_today_date()

    if already_ran(date, args.db) and not args.force:
        logging.info("Tick for %s already ran (status=ok). Use --force to re-run.", date)
        return 2

    try:
        result = run_tick(date, db_path=args.db)
    except Exception:
        logging.exception("Tick failed")
        return 1

    if result.status == "skipped_no_bar":
        return 3
    if result.status == "ok":
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
