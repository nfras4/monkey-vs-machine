"""Idempotent INSERT ... ON CONFLICT writers for the per-tick history tables."""
from __future__ import annotations

import json
import sqlite3
from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np


def _date_str(date) -> str:
    return str(date) if isinstance(date, str) else date.strftime("%Y-%m-%d")


def upsert_prices(
    conn: sqlite3.Connection,
    date,
    rows: Sequence[Tuple[str, float, float, float, float, float]],
    *,
    overwrite: bool = False,
) -> None:
    """rows = list of (ticker, open, high, low, close, volume).

    Default behaviour is INSERT OR IGNORE — historical bars are write-once so a
    re-fetch with revised adjusted-close values cannot drift the AI's training
    data and break idempotency. Pass `overwrite=True` only for bootstrap or
    explicit correction.
    """
    d = _date_str(date)
    if overwrite:
        conn.executemany(
            """
            INSERT INTO prices (date, ticker, open, high, low, close, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(date, ticker) DO UPDATE SET
                open=excluded.open, high=excluded.high, low=excluded.low,
                close=excluded.close, volume=excluded.volume
            """,
            [(d, t, o, h, l, c, v) for (t, o, h, l, c, v) in rows],
        )
    else:
        conn.executemany(
            """
            INSERT OR IGNORE INTO prices (date, ticker, open, high, low, close, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [(d, t, o, h, l, c, v) for (t, o, h, l, c, v) in rows],
        )


def upsert_monkey_state(
    conn: sqlite3.Connection,
    date,
    cash: np.ndarray,
    shares: np.ndarray,
    pos: np.ndarray,
    equity: np.ndarray,
    actions: np.ndarray,
    tickers: List[str],
) -> None:
    """Write `monkey_history` rows for `date` and update `monkeys` current state.

    `pos` is int (ticker index) with -1 = cash-only. `tickers` is the universe list
    indexed by `pos`.
    """
    d = _date_str(date)
    n = cash.shape[0]
    history_rows = []
    monkey_rows = []
    action_names = {0: "hold", 1: "sell", 2: "buy"}
    for i in range(n):
        p_idx = int(pos[i])
        position_ticker = tickers[p_idx] if p_idx >= 0 else None
        history_rows.append((
            d, i,
            float(cash[i]), float(shares[i]),
            position_ticker, float(equity[i]),
            action_names.get(int(actions[i]), "hold"),
        ))
        monkey_rows.append((
            i,
            float(cash[i]), float(shares[i]),
            position_ticker, float(equity[i]), d,
        ))

    conn.executemany(
        """
        INSERT INTO monkey_history (date, monkey_id, cash, shares, position_ticker, equity, action)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(date, monkey_id) DO UPDATE SET
            cash=excluded.cash, shares=excluded.shares,
            position_ticker=excluded.position_ticker,
            equity=excluded.equity, action=excluded.action
        """,
        history_rows,
    )
    conn.executemany(
        """
        INSERT INTO monkeys (monkey_id, cash, shares, position_ticker, equity, last_date)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(monkey_id) DO UPDATE SET
            cash=excluded.cash, shares=excluded.shares,
            position_ticker=excluded.position_ticker,
            equity=excluded.equity, last_date=excluded.last_date
        """,
        monkey_rows,
    )


def write_ai_model_row(
    conn: sqlite3.Connection,
    date,
    model_id: str,
    model_family: str,
    config: Dict,
    diagnostics: Dict,
    runtime_fingerprint: Dict,
    features_hash: str,
    train_window_end: str,
    training_seconds: float,
) -> None:
    d = _date_str(date)
    conn.execute(
        """
        INSERT INTO ai_model_history
            (date, model_id, model_family, config_json, diagnostics_json,
             runtime_fingerprint, features_hash, train_window_end, training_seconds)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(date, model_id) DO UPDATE SET
            model_family=excluded.model_family,
            config_json=excluded.config_json,
            diagnostics_json=excluded.diagnostics_json,
            runtime_fingerprint=excluded.runtime_fingerprint,
            features_hash=excluded.features_hash,
            train_window_end=excluded.train_window_end,
            training_seconds=excluded.training_seconds
        """,
        (
            d, model_id, model_family,
            json.dumps(config, sort_keys=True),
            json.dumps(diagnostics, sort_keys=True, default=str),
            json.dumps(runtime_fingerprint, sort_keys=True),
            features_hash, train_window_end, training_seconds,
        ),
    )


def write_ai_portfolio(
    conn: sqlite3.Connection,
    date,
    model_id: str,
    holdings: Dict[str, float],
) -> None:
    """Replace today's portfolio rows for this (date, model_id)."""
    d = _date_str(date)
    # First delete any existing rows for (date, model_id) so an empty `holdings` results in zero rows.
    conn.execute(
        "DELETE FROM ai_portfolio_history WHERE date=? AND model_id=?",
        (d, model_id),
    )
    rows = [(d, t, model_id, float(w)) for t, w in holdings.items()]
    if rows:
        conn.executemany(
            "INSERT INTO ai_portfolio_history (date, ticker, model_id, weight) VALUES (?, ?, ?, ?)",
            rows,
        )


def get_ai_holdings(
    conn: sqlite3.Connection,
    model_id: str,
    as_of_date: str | None = None,
    *,
    strictly_before: str | None = None,
) -> Dict[str, float]:
    """Parameterised replacement for the dropped `ai_holdings_current` view.

    By default returns the most recent portfolio for `model_id`. Pass
    `strictly_before='YYYY-MM-DD'` to get the most recent portfolio dated
    BEFORE that day — needed by the tick runner so a rerun reads yesterday's
    holdings, not the (potentially already-written) today's.
    """
    if as_of_date is None:
        if strictly_before is not None:
            row = conn.execute(
                "SELECT MAX(date) AS d FROM ai_portfolio_history WHERE model_id=? AND date < ?",
                (model_id, strictly_before),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT MAX(date) AS d FROM ai_portfolio_history WHERE model_id=?",
                (model_id,),
            ).fetchone()
        if row is None or row["d"] is None:
            return {}
        as_of_date = row["d"]
    cur = conn.execute(
        "SELECT ticker, weight FROM ai_portfolio_history WHERE model_id=? AND date=?",
        (model_id, as_of_date),
    )
    return {row["ticker"]: float(row["weight"]) for row in cur.fetchall()}


def write_aggregates_row(
    conn: sqlite3.Connection,
    table: str,
    date,
    payload: Dict[str, float | int | str],
) -> None:
    """Generic single-row upsert for a date-keyed table (for future aggregates table)."""
    d = _date_str(date)
    cols = list(payload.keys())
    placeholders = ", ".join(["?"] * (len(cols) + 1))
    set_clause = ", ".join(f"{c}=excluded.{c}" for c in cols)
    conn.execute(
        f"INSERT INTO {table} (date, {', '.join(cols)}) VALUES ({placeholders}) "
        f"ON CONFLICT(date) DO UPDATE SET {set_clause}",
        (d, *payload.values()),
    )


def refresh_named_monkeys(
    conn: sqlite3.Connection,
    date,
    equity_today: np.ndarray,
    equity_yesterday: np.ndarray | None,
) -> List[Tuple[str, int, str, float]]:
    """Update `named_monkeys` (current) + append `named_monkey_history` rows.

    Personality picks are fixed at genesis (already in `named_monkeys` with
    category='personality'). Top/bottom/mover are recomputed here.
    Returns the rows written to history this tick as
    [(name, monkey_id, category, equity), ...] for convenient logging / push.
    """
    d = _date_str(date)
    # Read fixed personality picks from named_monkeys (set at genesis)
    personalities = [
        (row["name"], row["monkey_id"])
        for row in conn.execute(
            "SELECT name, monkey_id FROM named_monkeys WHERE category='personality' ORDER BY name"
        ).fetchall()
    ]

    n = equity_today.shape[0]
    sorted_ids_desc = np.argsort(-equity_today)
    top3 = sorted_ids_desc[:3].tolist()
    bottom3 = sorted_ids_desc[-3:][::-1].tolist()  # worst first

    # Today's biggest absolute mover (vs yesterday)
    if equity_yesterday is not None and equity_yesterday.shape[0] == n:
        delta = np.abs(equity_today - equity_yesterday)
        mover_id = int(np.argmax(delta))
    else:
        mover_id = int(sorted_ids_desc[0])  # fall back to top monkey on day 1

    rows_to_write: List[Tuple[str, int, str, float]] = []
    # Personalities
    for name, mid in personalities:
        rows_to_write.append((name, int(mid), "personality", float(equity_today[mid])))
    # Top 3
    for rank, mid in enumerate(top3, start=1):
        rows_to_write.append((f"top_{rank}", int(mid), "top", float(equity_today[mid])))
    # Bottom 3
    for rank, mid in enumerate(bottom3, start=1):
        rows_to_write.append((f"bottom_{rank}", int(mid), "bottom", float(equity_today[mid])))
    # Mover
    rows_to_write.append(("today_mover", mover_id, "mover", float(equity_today[mover_id])))

    # Refresh current table: keep personalities, replace others
    conn.execute("DELETE FROM named_monkeys WHERE category != 'personality'")
    for name, mid, cat, _eq in rows_to_write:
        if cat == "personality":
            continue
        conn.execute(
            """
            INSERT INTO named_monkeys (name, monkey_id, category)
            VALUES (?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET monkey_id=excluded.monkey_id, category=excluded.category
            """,
            (name, mid, cat),
        )

    # Append history rows
    conn.executemany(
        """
        INSERT INTO named_monkey_history (date, name, monkey_id, category, equity)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(date, name) DO UPDATE SET
            monkey_id=excluded.monkey_id, category=excluded.category, equity=excluded.equity
        """,
        [(d, n, m, c, e) for (n, m, c, e) in rows_to_write],
    )

    return rows_to_write
