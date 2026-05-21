"""One-shot genesis: create the SQLite db, mint 100k monkeys, fetch warmup prices.

Usage:
    python scripts/bootstrap_genesis.py --start-date 2026-05-20
    python scripts/bootstrap_genesis.py --start-date 2026-05-20 --n-monkeys 1000 --universe-size 10 --warmup-days 90
    python scripts/bootstrap_genesis.py --force  # wipe existing DB and re-bootstrap
"""
from __future__ import annotations

import argparse
import hashlib
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
BENCHMARK_TICKER = "SPY"  # tracked alongside the universe but never traded

# Pre-v3 personality cast (alice/bob/carol). Kept as a constant so the
# migration helper can DELETE them by name without re-deriving the list.
LEGACY_PERSONALITY_NAMES = ["alice", "bob", "carol"]

# v3 personality cast: 8 named monkeys with deterministic quirks. The list
# order is part of the determinism contract — picking N monkey_ids is
# rng.choice(n_monkeys, size=N) followed by sorted(), and the (name, config)
# pairs are zipped against the sorted IDs in this list's order.
DEFAULT_PERSONALITY_CAST = [
    {
        "name": "Bob the Tech Investor",
        "config": {
            "kind": "tech_lover",
            "tickers": ["AAPL", "MSFT", "GOOG", "NVDA", "AMZN", "META", "AVGO", "TXN"],
            "bias": 0.7,
        },
    },
    {
        "name": "Valerie the Value Hunter",
        "config": {
            "kind": "value_hunter",
            "tickers": ["KO", "JNJ", "PG", "WMT", "MCD", "GE", "BAC", "XOM"],
            "bias": 0.7,
            "max_tech_hold_days": 5,
            "tech_blacklist": ["AAPL", "MSFT", "GOOG", "NVDA", "AMZN", "META", "AVGO", "TXN"],
        },
    },
    {
        "name": "Monday Marge",
        "config": {
            "kind": "weekday_trader",
            "trade_days": [0],  # Monday
            "trade_prob": 0.3,
        },
    },
    {
        "name": "Friday Frankie",
        "config": {
            "kind": "contrarian_weekday",
            "buy_days": [0],   # Monday
            "sell_days": [4],  # Friday
        },
    },
    {
        "name": "Dip Daniel",
        "config": {
            "kind": "dip_buyer",
            "lookback": 3,
            "threshold": -0.02,
        },
    },
    {
        "name": "Momentum Mike",
        "config": {
            "kind": "momentum_chaser",
            "lookback": 5,
            "buy_threshold": 0.05,
            "sell_threshold": -0.05,
        },
    },
    {
        "name": "Lakers Joe",
        "config": {
            "kind": "lakers_fan",
            "event_kind": "lakers_game",
            "win_bonus": 100.0,
            "loss_penalty": -50.0,
            "floor": 0.0,
        },
    },
    {
        "name": "Weekend Wendy",
        "config": {
            "kind": "babysitter",
            "credit_amount": 25.0,
            "credit_day": 0,  # Monday following the weekend
        },
    },
]
DEFAULT_PERSONALITY_NAMES = [c["name"] for c in DEFAULT_PERSONALITY_CAST]

FIXTURE_PATH = ROOT / "data" / "fixtures" / "lakers_2023_2025.json"


def pick_personality_cast(rng: np.random.Generator, n_monkeys: int) -> list[tuple[int, str, dict]]:
    """Pick the 8 personality monkey IDs and zip them with names + configs.

    Returns a sorted-by-monkey_id list of (monkey_id, name, config_dict).
    Sharing this between bootstrap and migrate guarantees both converge to
    the same (monkey_id -> name -> config) mapping for a given seed.
    """
    cast_size = len(DEFAULT_PERSONALITY_CAST)
    ids = sorted(rng.choice(n_monkeys, size=cast_size, replace=False).tolist())
    return [
        (int(mid), entry["name"], dict(entry["config"]))
        for mid, entry in zip(ids, DEFAULT_PERSONALITY_CAST)
    ]


def load_lakers_fixture() -> list[dict]:
    """Load the committed fixture and validate row shape."""
    if not FIXTURE_PATH.exists():
        raise FileNotFoundError(
            f"Lakers fixture missing at {FIXTURE_PATH}. Run scripts/fetch_nba_history.py --refresh."
        )
    with FIXTURE_PATH.open("r", encoding="utf-8") as fh:
        rows = json.load(fh)
    required = {"date", "outcome", "payload"}
    for i, row in enumerate(rows):
        missing = required - row.keys()
        if missing or row["outcome"] not in (0, 1):
            raise ValueError(f"Bad fixture row {i}: {row}")
    return rows


def compute_external_events_fingerprint(conn) -> str:
    """SHA256 of canonical (date, event_kind, outcome) tuples in sort order."""
    rows = conn.execute(
        "SELECT date, event_kind, outcome FROM external_events ORDER BY date, event_kind"
    ).fetchall()
    h = hashlib.sha256()
    for date, kind, outcome in rows:
        h.update(f"{date}|{kind}|{outcome}\n".encode("utf-8"))
    return h.hexdigest()


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

    # Build deterministic monkey IDs + personality picks. Shared helper so
    # migrate_personality_cast.py converges to the same mapping.
    rng = np.random.default_rng(seed=hash_seed("personality_pick", seed_string=seed_string))
    cast = pick_personality_cast(rng, n_monkeys)  # [(monkey_id, name, config), ...]
    personality_ids = [mid for mid, _, _ in cast]
    log.info("Personality monkey_ids (%d): %s", len(personality_ids), personality_ids)

    # Lakers fixture — read here so genesis fails fast if the committed file is
    # malformed (rather than failing partway through DB writes).
    lakers_rows = load_lakers_fixture()
    log.info("Lakers fixture: %d rows (%d wins)", len(lakers_rows), sum(r["outcome"] for r in lakers_rows))

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

            for mid, name, config in cast:
                conn.execute(
                    """
                    INSERT INTO named_monkeys (name, monkey_id, category, personality_config)
                    VALUES (?, ?, 'personality', ?)
                    """,
                    (name, int(mid), json.dumps(config, sort_keys=True)),
                )

            # Seed external_events from the committed fixture so Lakers Joe has
            # historical scoreboard to react to from day one.
            conn.executemany(
                """
                INSERT INTO external_events (date, event_kind, outcome, payload_json)
                VALUES (?, 'lakers_game', ?, ?)
                """,
                [
                    (r["date"], int(r["outcome"]), json.dumps(r["payload"], sort_keys=True))
                    for r in lakers_rows
                ],
            )

            fingerprint = compute_external_events_fingerprint(conn)
            cast_json = json.dumps(
                [{"name": n, "monkey_id": m, "config": c} for m, n, c in cast],
                sort_keys=True,
            )

            conn.execute(
                """
                INSERT INTO genesis_log
                    (id, start_date, seed_string, warmup_days, n_monkeys,
                     universe_tickers_json, personality_monkey_ids_json,
                     spy_anchor_date, spy_anchor_close,
                     external_events_fingerprint, cast_version,
                     personality_config_json)
                VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
                """,
                (
                    start_date, seed_string, warmup_days, n_monkeys,
                    json.dumps(tickers),  # benchmark NOT in here
                    json.dumps([int(x) for x in personality_ids]),
                    spy_anchor_date, spy_anchor_close,
                    fingerprint,
                    cast_json,
                ),
            )
            log.info("Genesis cast_version=1, fingerprint=%s...", fingerprint[:12])

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
