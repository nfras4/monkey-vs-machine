"""Per-tick orchestrator for the perpetual simulation.

Tx 1 (prices): fetch the new daily bar(s) up to `date`, upsert into `prices`.
              If no bar resolved for `date`, write ticks.status='skipped_no_bar'
              and exit (no simulation transaction is ever opened).
Tx 2 (simulation, BEGIN IMMEDIATE): for each model_id in MODELS, train +
              predict + rebalance forward from current holdings. Step monkeys.
              Compute aggregates. Refresh named monkeys. Write ticks.status='ok'.

Any exception inside Tx 2 → ROLLBACK → ticks.status='failed' written in a
new tiny tx → re-raise.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from .config import DEFAULT_STARTING_CASH
from .data.prices import download_prices
from .features import build_feature_panel
from .models.ai_step import (
    apply_rebalance,
    predict_ranking,
    slice_predict,
    slice_train,
    to_xy,
)
from .models.monkey_step import compute_equity, step_monkeys_one_day
from .models.registry import CHAMPION_MODEL_ID, MODELS
from .runtime_fingerprint import runtime_fingerprint
from .state.db import get_conn, transaction
from .state.features_hash import features_hash
from .state.hash_seed import hash_seed
from .state.snapshots import (
    get_ai_holdings,
    refresh_named_monkeys,
    upsert_monkey_state,
    upsert_prices,
    write_ai_model_row,
    write_ai_portfolio,
    write_aggregates_row,
)

log = logging.getLogger(__name__)

AI_TOP_K = 10
BENCHMARK_TICKER = "SPY"  # fetched alongside the universe, never traded


@dataclass
class TickResult:
    status: str
    date: str
    duration_seconds: float
    note: Optional[str] = None


def _genesis_metadata(conn: sqlite3.Connection) -> Dict:
    row = conn.execute("SELECT * FROM genesis_log WHERE id=1").fetchone()
    if row is None:
        raise RuntimeError("genesis_log is empty — run scripts/bootstrap_genesis.py first")
    return {
        "start_date": row["start_date"],
        "seed_string": row["seed_string"],
        "warmup_days": int(row["warmup_days"]),
        "n_monkeys": int(row["n_monkeys"]),
        "universe_tickers": json.loads(row["universe_tickers_json"]),
        "personality_monkey_ids": json.loads(row["personality_monkey_ids_json"]),
    }


def _load_close_volume_panels(conn: sqlite3.Connection, universe: List[str], cutoff_date: str):
    """Return (close_panel, volume_panel) wide DataFrames up to and including cutoff_date."""
    placeholders = ",".join(["?"] * len(universe))
    sql = f"""
        SELECT date, ticker, close, COALESCE(volume, 0) AS volume
        FROM prices
        WHERE ticker IN ({placeholders}) AND date <= ?
        ORDER BY date
    """
    rows = conn.execute(sql, (*universe, cutoff_date)).fetchall()
    if not rows:
        return None, None
    df = pd.DataFrame(rows, columns=["date", "ticker", "close", "volume"])
    df["date"] = pd.to_datetime(df["date"])
    close = df.pivot(index="date", columns="ticker", values="close").sort_index().astype("float64")
    volume = df.pivot(index="date", columns="ticker", values="volume").sort_index().astype("float64")
    # Ensure column order matches the universe (some tickers may have missing rows on early dates).
    close = close.reindex(columns=universe)
    volume = volume.reindex(columns=universe).fillna(0.0)
    # Forward-fill short gaps in close. No bfill — we never let future prices
    # leak backwards into a warmup row.
    close = close.ffill(limit=5)
    return close, volume


def _load_monkey_state(
    conn: sqlite3.Connection,
    universe: List[str],
    n_monkeys: int,
    target_date: str,
    starting_cash: float,
):
    """Return (cash, shares, pos) as of the close of the most recent date BEFORE `target_date`.

    Loading from `monkey_history` rather than the mutable `monkeys` table keeps
    re-running a tick idempotent: a rerun of date D always sees the same
    "yesterday" snapshot. If no history row exists yet (i.e. this is the very
    first tick), all monkeys start at the genesis defaults.
    """
    ticker_to_idx = {t: i for i, t in enumerate(universe)}
    cash = np.full(n_monkeys, float(starting_cash), dtype=np.float64)
    shares = np.zeros(n_monkeys, dtype=np.float64)
    pos = np.full(n_monkeys, -1, dtype=np.int32)

    row = conn.execute(
        "SELECT MAX(date) AS d FROM monkey_history WHERE date < ?", (target_date,),
    ).fetchone()
    if row is None or row["d"] is None:
        return cash, shares, pos  # genesis defaults

    yesterday = row["d"]
    cur = conn.execute(
        "SELECT monkey_id, cash, shares, position_ticker FROM monkey_history WHERE date=? ORDER BY monkey_id",
        (yesterday,),
    )
    seen = 0
    for r in cur:
        mid = int(r["monkey_id"])
        cash[mid] = float(r["cash"])
        shares[mid] = float(r["shares"])
        if r["position_ticker"] is not None:
            pos[mid] = ticker_to_idx.get(r["position_ticker"], -1)
        seen += 1
    if seen != n_monkeys:
        raise RuntimeError(f"Expected {n_monkeys} monkey rows for {yesterday}, found {seen}")
    return cash, shares, pos


def _yesterday_equity(conn: sqlite3.Connection, date: str, n_monkeys: int) -> Optional[np.ndarray]:
    row = conn.execute(
        "SELECT MAX(date) AS d FROM monkey_history WHERE date < ?",
        (date,),
    ).fetchone()
    if row is None or row["d"] is None:
        return None
    yesterday = row["d"]
    cur = conn.execute(
        "SELECT monkey_id, equity FROM monkey_history WHERE date=? ORDER BY monkey_id",
        (yesterday,),
    )
    eq = np.zeros(n_monkeys, dtype=np.float64)
    for r in cur:
        eq[int(r["monkey_id"])] = float(r["equity"])
    return eq


def _persist_ticks_row(
    conn: sqlite3.Connection,
    date: str,
    status: str,
    started_at: str,
    duration: float,
    note: Optional[str] = None,
) -> None:
    conn.execute(
        """
        INSERT INTO ticks (date, status, started_at, finished_at, duration_seconds, note)
        VALUES (?, ?, ?, datetime('now'), ?, ?)
        ON CONFLICT(date) DO UPDATE SET
            status=excluded.status,
            finished_at=excluded.finished_at,
            duration_seconds=excluded.duration_seconds,
            note=excluded.note
        """,
        (date, status, started_at, duration, note),
    )


def _fetch_prices_for_tick(universe: List[str], date: str) -> pd.DataFrame:
    """Download a small window ending at `date` and return long-form rows.

    The benchmark (SPY) is fetched alongside the universe so the daily
    aggregates can compute `spy_equity`. SPY is NOT in the universe — never
    traded by AI or monkeys.
    """
    end_dt = datetime.strptime(date, "%Y-%m-%d") + timedelta(days=1)
    fetch_list = list(universe) + [BENCHMARK_TICKER]
    return download_prices(fetch_list, years=1, end=end_dt)


def run_tick(date: str, *, db_path=None) -> TickResult:
    """Run one tick for `date`. Returns a TickResult; never raises on skipped paths."""
    started_at = datetime.utcnow().isoformat()
    t0 = time.perf_counter()

    with get_conn(db_path) as conn:
        meta = _genesis_metadata(conn)
        universe = meta["universe_tickers"]
        n_monkeys = meta["n_monkeys"]
        seed_string = meta["seed_string"]

        # === Tx 1: prices upsert ===
        # Skip the fetch entirely if `date` is already in prices (rerun, or
        # bootstrap already loaded it). Historical bars are write-once
        # (INSERT OR IGNORE) so a re-fetch can't drift AI training inputs.
        date_ts = pd.to_datetime(date)
        existing_today = conn.execute(
            "SELECT 1 FROM prices WHERE date=? LIMIT 1", (date,),
        ).fetchone()

        if not existing_today:
            try:
                prices_long = _fetch_prices_for_tick(universe, date)
            except Exception as e:  # noqa: BLE001
                duration = time.perf_counter() - t0
                with transaction(conn):
                    _persist_ticks_row(conn, date, "failed", started_at, duration, f"price_fetch_error: {e}")
                raise

            with transaction(conn):
                by_date: Dict[str, List] = {}
                for (d_idx, t_idx), r in prices_long.iterrows():
                    d_str = d_idx.strftime("%Y-%m-%d") if hasattr(d_idx, "strftime") else str(d_idx)
                    by_date.setdefault(d_str, []).append((
                        t_idx,
                        float(r.get("open", float("nan"))),
                        float(r.get("high", float("nan"))),
                        float(r.get("low", float("nan"))),
                        float(r["close"]),
                        float(r.get("volume", 0.0)),
                    ))
                for d_str, rs in by_date.items():
                    upsert_prices(conn, d_str, rs)  # INSERT OR IGNORE — historical writes once

            existing_today = conn.execute(
                "SELECT 1 FROM prices WHERE date=? LIMIT 1", (date,),
            ).fetchone()

        if not existing_today:
            duration = time.perf_counter() - t0
            with transaction(conn):
                _persist_ticks_row(
                    conn, date, "skipped_no_bar", started_at, duration,
                    f"yfinance returned no bar for {date} (weekend/holiday/early-fetch)",
                )
            log.warning("No bar for %s — skipped", date)
            return TickResult(status="skipped_no_bar", date=date, duration_seconds=duration)

        # === Tx 2: simulation ===
        try:
            with transaction(conn):
                # Load close+volume panels up to and including `date`
                close, volume = _load_close_volume_panels(conn, universe, date)
                if close is None or close.empty:
                    raise RuntimeError(f"No prices loaded for tick {date}")
                # Forward-fill only — NEVER bfill, which would leak future prices
                # backwards into warmup rows. Today's row is guaranteed by the
                # Tx 1 price upsert above, so monkey indexing for `date` is safe.
                close_filled = close.ffill()

                # Build feature panel (KEEP predict-date rows with NaN y_up)
                panel = build_feature_panel(close_filled, volume)
                features_hash_str = features_hash(panel)
                fp = runtime_fingerprint()

                date_ts = pd.to_datetime(date)

                # === AI: per-model train + predict + rebalance ===
                for model_id, builder_fn in MODELS.items():
                    train_rows = slice_train(panel, date_ts)
                    predict_rows = slice_predict(panel, date_ts)
                    if train_rows.empty or predict_rows.empty:
                        log.warning("model %s: insufficient data (train=%d, predict=%d) — skipping AI",
                                    model_id, len(train_rows), len(predict_rows))
                        continue
                    X_train, y_train, _ = to_xy(train_rows)
                    X_today, _y_today, tickers_today = to_xy(predict_rows)

                    builder = builder_fn()
                    seed = hash_seed("ai_train", model_id, date, seed_string=seed_string)
                    t_train = time.perf_counter()
                    diagnostics = builder.fit(X_train, y_train, seed=seed)
                    training_seconds = time.perf_counter() - t_train

                    ranking = predict_ranking(builder, X_today, tickers_today)
                    # Strictly-before to keep reruns idempotent.
                    current_holdings = get_ai_holdings(conn, model_id, strictly_before=date)
                    new_holdings, _turnover = apply_rebalance(current_holdings, ranking, AI_TOP_K)

                    train_window_end = str(train_rows.index.get_level_values("date").max().date())
                    write_ai_model_row(
                        conn=conn, date=date, model_id=model_id,
                        model_family=getattr(builder, "family", "unknown"),
                        config=getattr(builder, "config", {}),
                        diagnostics=diagnostics,
                        runtime_fingerprint=fp,
                        features_hash=features_hash_str,
                        train_window_end=train_window_end,
                        training_seconds=float(training_seconds),
                    )
                    write_ai_portfolio(conn, date, model_id, new_holdings)

                    # Compute and store the AI portfolio equity for this model
                    _update_ai_equity(conn, date, model_id, new_holdings, close_filled)

                # === Monkeys: step forward one day ===
                # Yesterday's snapshot — NOT the mutable `monkeys` table — so a rerun is idempotent.
                cash, shares, pos = _load_monkey_state(
                    conn, universe, n_monkeys, date, DEFAULT_STARTING_CASH,
                )
                prices_today_arr = close_filled.loc[date_ts].to_numpy(dtype=np.float64)
                # Replace NaN/0 with 1.0 just for safety in mark-to-market (shouldn't hit)
                prices_today_arr = np.where(np.isfinite(prices_today_arr) & (prices_today_arr > 0),
                                            prices_today_arr, 1.0)

                monkey_seed = hash_seed("monkey_tick", date, seed_string=seed_string)
                rng = np.random.default_rng(monkey_seed)
                actions = step_monkeys_one_day(prices_today_arr, cash, shares, pos, rng=rng)
                equity = compute_equity(prices_today_arr, cash, shares, pos)

                # === Snapshot writers ===
                upsert_monkey_state(conn, date, cash, shares, pos, equity, actions, universe)
                yesterday_eq = _yesterday_equity(conn, date, n_monkeys)
                refresh_named_monkeys(conn, date, equity, yesterday_eq)

                # Aggregates
                p5, p25, p50, p75, p95 = np.percentile(equity, [5, 25, 50, 75, 95])

                # SPY benchmark equity: anchored at genesis.spy_anchor_close.
                # `spy_equity[date] = starting_cash * close[SPY, date] / anchor_close`.
                spy_anchor_close_row = conn.execute(
                    "SELECT spy_anchor_close FROM genesis_log WHERE id=1",
                ).fetchone()
                anchor = spy_anchor_close_row["spy_anchor_close"] if spy_anchor_close_row else None
                spy_today = conn.execute(
                    "SELECT close FROM prices WHERE ticker=? AND date=?",
                    (BENCHMARK_TICKER, date),
                ).fetchone()
                if anchor and spy_today and spy_today["close"] > 0:
                    spy_equity = DEFAULT_STARTING_CASH * float(spy_today["close"]) / float(anchor)
                else:
                    spy_equity = None  # missing benchmark data: render as null on the dashboard

                write_aggregates_row(conn, "daily_aggregates", date, {
                    "monkey_mean": float(np.mean(equity)),
                    "monkey_median": float(p50),
                    "monkey_p5": float(p5),
                    "monkey_p25": float(p25),
                    "monkey_p75": float(p75),
                    "monkey_p95": float(p95),
                    "monkey_best": float(np.max(equity)),
                    "monkey_worst": float(np.min(equity)),
                    "n_monkeys": int(n_monkeys),
                    "n_monkeys_above_starting": int((equity > DEFAULT_STARTING_CASH).sum()),
                    "spy_equity": spy_equity,
                })

                # Tick row
                duration = time.perf_counter() - t0
                _persist_ticks_row(conn, date, "ok", started_at, duration)

        except BaseException as e:
            duration = time.perf_counter() - t0
            # Tx already rolled back by `transaction` context manager.
            with transaction(conn):
                _persist_ticks_row(conn, date, "failed", started_at, duration, f"{type(e).__name__}: {e}")
            raise

    duration = time.perf_counter() - t0
    log.info("Tick %s completed in %.2fs", date, duration)
    return TickResult(status="ok", date=date, duration_seconds=duration)


def _update_ai_equity(
    conn: sqlite3.Connection,
    date: str,
    model_id: str,
    new_holdings: Dict[str, float],
    close_panel: pd.DataFrame,
) -> None:
    """Compute today's AI portfolio equity using yesterday's held weights × today's return.

    Starts from `DEFAULT_STARTING_CASH` on the first row for this model_id.
    """
    # Get the most recent equity row for this model STRICTLY BEFORE `date` —
    # so rerunning the same date reads yesterday's row, not the one this
    # current run is about to write/replace.
    row = conn.execute(
        "SELECT date, equity FROM ai_portfolio_equity WHERE model_id=? AND date < ? "
        "ORDER BY date DESC LIMIT 1",
        (model_id, date),
    ).fetchone()
    if row is None:
        # First tick for this model — seed at starting cash, no return.
        equity = DEFAULT_STARTING_CASH
        daily_return = 0.0
    else:
        yesterday_eq = float(row["equity"])
        yesterday_date = row["date"]
        # Reconstruct yesterday's held weights (rebalances happen at close of t-1).
        cur = conn.execute(
            "SELECT ticker, weight FROM ai_portfolio_history WHERE model_id=? AND date=?",
            (model_id, yesterday_date),
        )
        held = {r["ticker"]: float(r["weight"]) for r in cur.fetchall()}
        # Today's per-ticker return = close[date]/close[yesterday] - 1.
        # Both dates MUST be in the panel — fail loud if not, rather than silently
        # zeroing the return (which would freeze the AI equity curve invisibly).
        today_ts = pd.to_datetime(date)
        yesterday_ts = pd.to_datetime(yesterday_date)
        if today_ts not in close_panel.index or yesterday_ts not in close_panel.index:
            raise RuntimeError(
                f"AI equity update: missing close panel rows "
                f"(today={today_ts.date() if today_ts in close_panel.index else 'MISSING'}, "
                f"yesterday={yesterday_ts.date() if yesterday_ts in close_panel.index else 'MISSING'}). "
                "This is a programmer error — close_panel is built from the prices table "
                "via `_load_close_volume_panels`, so both dates should be present."
            )
        today_close = close_panel.loc[today_ts]
        yesterday_close = close_panel.loc[yesterday_ts]
        rets = (today_close / yesterday_close - 1.0).fillna(0.0)
        port_return = sum(w * float(rets.get(t, 0.0)) for t, w in held.items())
        equity = yesterday_eq * (1.0 + port_return)
        daily_return = port_return

    conn.execute(
        """
        INSERT INTO ai_portfolio_equity (date, model_id, equity, daily_return)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(date, model_id) DO UPDATE SET
            equity=excluded.equity, daily_return=excluded.daily_return
        """,
        (date, model_id, float(equity), float(daily_return)),
    )
