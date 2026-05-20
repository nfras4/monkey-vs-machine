"""One-shot genesis: create the SQLite db, mint 100k monkeys, fetch warmup prices.

Usage:
    python scripts/bootstrap_genesis.py --start-date 2026-05-20
    python scripts/bootstrap_genesis.py --start-date 2026-05-20 --n-monkeys 1000 --universe-size 10 --warmup-days 90
    python scripts/bootstrap_genesis.py --force  # wipe existing DB and re-bootstrap
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mvm.config import DEFAULT_STARTING_CASH  # noqa: E402
from mvm.data.prices import download_prices  # noqa: E402
from mvm.data.universe import get_universe  # noqa: E402
from mvm.state.db import DEFAULT_DB_PATH, get_conn  # noqa: E402
from mvm.state.hash_seed import hash_seed  # noqa: E402

log = logging.getLogger(__name__)

DEFAULT_WARMUP_DAYS = 180
DEFAULT_N_MONKEYS = 100_000
DEFAULT_UNIVERSE_SIZE = 50
DEFAULT_PERSONALITY_NAMES = ["alice", "bob", "carol"]
BENCHMARK_TICKER = "SPY"  # tracked alongside the universe but never traded


def _seed_string_for(start_date: str) -> str:
    return f"mvm-genesis-{start_date}"


def bootstrap(
    start_date: str,
    n_monkeys: int,
    universe_size: int,
    warmup_days: int,
    starting_cash: float,
    force: bool,
    db_path: Path,
) -> None:
    if db_path.exists() and not force:
        log.error("State db already exists at %s. Pass --force to overwrite.", db_path)
        sys.exit(2)
    if db_path.exists():
        log.warning("Removing existing db at %s", db_path)
        db_path.unlink()
        # WAL/SHM sidecars
        for suffix in ("-wal", "-shm"):
            sibling = db_path.with_name(db_path.name + suffix)
            if sibling.exists():
                sibling.unlink()

    seed_string = _seed_string_for(start_date)
    log.info("Genesis seed: %s", seed_string)

    # Build deterministic monkey IDs + personality picks
    rng = np.random.default_rng(seed=hash_seed("personality_pick", seed_string=seed_string))
    personality_ids = sorted(rng.choice(n_monkeys, size=len(DEFAULT_PERSONALITY_NAMES), replace=False).tolist())
    log.info("Personality monkey_ids: %s", personality_ids)

    # Universe + warmup price fetch
    tickers = get_universe(size=universe_size)
    log.info("Universe (%d tickers): %s%s", len(tickers), tickers[:5], "..." if len(tickers) > 5 else "")

    # Fetch the benchmark alongside the universe but keep it OUT of the
    # `universe_tickers_json` so it's never traded by AI/monkeys.
    fetch_list = tickers + [BENCHMARK_TICKER]
    log.info("Plus benchmark: %s", BENCHMARK_TICKER)

    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = start_dt
    log.info("Fetching %d days of warmup prices through %s", warmup_days, end_dt.date())
    years_for_fetch = max(1, int(np.ceil(warmup_days / 252.0)) + 1)
    prices_long = download_prices(fetch_list, years=years_for_fetch, end=end_dt)
    log.info("Fetched %d price rows (universe + benchmark)", len(prices_long))

    # Anchor: latest SPY close on-or-before start_date. Used by every tick to
    # compute spy_equity = starting_cash * close[date] / anchor_close.
    spy_rows = prices_long.xs(BENCHMARK_TICKER, level="ticker")
    spy_rows = spy_rows[spy_rows.index <= pd.Timestamp(start_date)]
    if spy_rows.empty:
        raise RuntimeError(f"No {BENCHMARK_TICKER} data on or before {start_date}; cannot anchor benchmark")
    spy_anchor_ts = spy_rows.index.max()
    spy_anchor_date = spy_anchor_ts.strftime("%Y-%m-%d")
    spy_anchor_close = float(spy_rows.loc[spy_anchor_ts, "close"])
    log.info("SPY anchor: %s @ $%.2f", spy_anchor_date, spy_anchor_close)

    # Atomic bootstrap: write everything to a temp DB path, then os.replace
    # into place. If we crash mid-bootstrap, the original path is either
    # untouched (didn't exist) or still represents the previous genesis.
    import os as _os
    tmp_path = db_path.with_name(db_path.name + ".genesis.tmp")
    if tmp_path.exists():
        tmp_path.unlink()
    for suffix in ("-wal", "-shm"):
        sib = tmp_path.with_name(tmp_path.name + suffix)
        if sib.exists():
            sib.unlink()

    from mvm.state.db import transaction  # local import to avoid cycle at module top

    with get_conn(tmp_path, init=True) as conn:
        with transaction(conn):
            conn.executemany(
                "INSERT OR IGNORE INTO tickers (ticker) VALUES (?)",
                [(t,) for t in tickers],
            )

            price_rows = []
            for (date_idx, ticker_idx), row in prices_long.iterrows():
                date_str = date_idx.strftime("%Y-%m-%d") if hasattr(date_idx, "strftime") else str(date_idx)
                price_rows.append((
                    date_str, ticker_idx,
                    float(row.get("open", float("nan"))),
                    float(row.get("high", float("nan"))),
                    float(row.get("low", float("nan"))),
                    float(row["close"]),
                    float(row.get("volume", 0.0)),
                ))
            conn.executemany(
                """
                INSERT INTO prices (date, ticker, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(date, ticker) DO UPDATE SET
                    open=excluded.open, high=excluded.high, low=excluded.low,
                    close=excluded.close, volume=excluded.volume
                """,
                price_rows,
            )
            log.info("Wrote %d price rows", len(price_rows))

            monkey_rows = [
                (i, float(starting_cash), 0.0, None, float(starting_cash), None)
                for i in range(n_monkeys)
            ]
            conn.executemany(
                "INSERT INTO monkeys (monkey_id, cash, shares, position_ticker, equity, last_date) VALUES (?, ?, ?, ?, ?, ?)",
                monkey_rows,
            )
            log.info("Inserted %d monkeys", n_monkeys)

            for name, mid in zip(DEFAULT_PERSONALITY_NAMES, personality_ids):
                conn.execute(
                    "INSERT INTO named_monkeys (name, monkey_id, category) VALUES (?, ?, 'personality')",
                    (name, int(mid)),
                )

            conn.execute(
                """
                INSERT INTO genesis_log
                    (id, start_date, seed_string, warmup_days, n_monkeys,
                     universe_tickers_json, personality_monkey_ids_json,
                     spy_anchor_date, spy_anchor_close)
                VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    start_date, seed_string, warmup_days, n_monkeys,
                    json.dumps(tickers),  # benchmark NOT in here
                    json.dumps([int(x) for x in personality_ids]),
                    spy_anchor_date, spy_anchor_close,
                ),
            )

    # Promote the tmp DB to its final path. SQLite checkpoint first so the WAL
    # doesn't have uncheckpointed pages we'd leave behind.
    with get_conn(tmp_path, enforce_single_writer=False) as conn:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")

    _os.replace(str(tmp_path), str(db_path))
    for suffix in ("-wal", "-shm"):
        sib = tmp_path.with_name(tmp_path.name + suffix)
        if sib.exists():
            sib.unlink()

    log.info("Genesis complete at %s", db_path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-date", required=True, help="ISO date e.g. 2026-05-20")
    parser.add_argument("--n-monkeys", type=int, default=DEFAULT_N_MONKEYS)
    parser.add_argument("--universe-size", type=int, default=DEFAULT_UNIVERSE_SIZE)
    parser.add_argument("--warmup-days", type=int, default=DEFAULT_WARMUP_DAYS)
    parser.add_argument("--starting-cash", type=float, default=DEFAULT_STARTING_CASH)
    parser.add_argument("--force", action="store_true", help="Overwrite an existing state.db")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    bootstrap(
        start_date=args.start_date,
        n_monkeys=args.n_monkeys,
        universe_size=args.universe_size,
        warmup_days=args.warmup_days,
        starting_cash=args.starting_cash,
        force=args.force,
        db_path=args.db,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
