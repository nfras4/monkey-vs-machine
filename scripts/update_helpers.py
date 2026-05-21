"""Small helpers consumed by update.ps1 — keeps PowerShell parser happy.

Subcommands print a single line of plain output (or JSON for list-shaped data)
so the .ps1 doesn't have to embed multi-line python snippets.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path


def _open(db: Path) -> sqlite3.Connection:
    if not db.exists():
        print(f"ERR: no DB at {db}", file=sys.stderr)
        sys.exit(1)
    return sqlite3.connect(db)


def cmd_last_ok_date(args) -> int:
    conn = _open(args.db)
    row = conn.execute(
        "SELECT date FROM ticks WHERE status='ok' ORDER BY date DESC LIMIT 1"
    ).fetchone()
    print(row[0] if row else "")
    return 0


def cmd_ok_dates(args) -> int:
    conn = _open(args.db)
    rows = conn.execute(
        "SELECT date FROM ticks WHERE status='ok' ORDER BY date"
    ).fetchall()
    print(json.dumps([r[0] for r in rows]))
    return 0


def cmd_picks(args) -> int:
    """Print up to N top AI holdings as 'TICKER WEIGHT%' lines."""
    conn = _open(args.db)
    rows = conn.execute(
        """
        SELECT ticker, ROUND(weight * 100, 1) AS pct
        FROM ai_portfolio_history
        WHERE date=? AND model_id=?
        ORDER BY weight DESC
        LIMIT ?
        """,
        (args.date, args.model_id, args.limit),
    ).fetchall()
    if not rows:
        print(f"  (no portfolio rows for {args.date})")
        return 0
    for ticker, pct in rows:
        print(f"  {ticker:<8} {pct:>5}%")
    return 0


def cmd_snapshot(args) -> int:
    """One-line summary: AI equity, median monkey, count above starting."""
    conn = _open(args.db)
    ai = conn.execute(
        "SELECT equity FROM ai_portfolio_equity WHERE date=? AND model_id=?",
        (args.date, args.model_id),
    ).fetchone()
    agg = conn.execute(
        """
        SELECT monkey_median, n_monkeys_above_starting, n_monkeys
        FROM daily_aggregates WHERE date=?
        """,
        (args.date,),
    ).fetchone()
    ai_str = f"${ai[0]:,.0f}" if ai and ai[0] is not None else "-"
    if agg:
        med = f"${agg[0]:,.0f}" if agg[0] is not None else "-"
        above = f"{agg[1]:,}" if agg[1] is not None else "0"
        total = f"{agg[2]:,}" if agg[2] is not None else "?"
        print(f"  AI {ai_str} | median monkey {med} | {above}/{total} above starting")
    else:
        print(f"  AI {ai_str} | (no aggregates row for {args.date})")
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--db", type=Path, default=Path("data/state.db"))
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("last_ok_date")
    sub.add_parser("ok_dates")

    picks = sub.add_parser("picks")
    picks.add_argument("--date", required=True)
    picks.add_argument("--model-id", default="hgb_v1")
    picks.add_argument("--limit", type=int, default=5)

    snap = sub.add_parser("snapshot")
    snap.add_argument("--date", required=True)
    snap.add_argument("--model-id", default="hgb_v1")

    args = p.parse_args()
    dispatch = {
        "last_ok_date": cmd_last_ok_date,
        "ok_dates": cmd_ok_dates,
        "picks": cmd_picks,
        "snapshot": cmd_snapshot,
    }
    return dispatch[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
