"""Vectorized 100,000-monkey random trader simulation.

Each monkey holds at most one ticker at a time (keeps memory O(N) instead of O(N*K)).
Each trading day, every monkey acts with probability `p_trade`:
  - if cash-only: buy a uniformly-random ticker with all cash
  - if holding:   sell with probability `p_sell`, else hold
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import numpy as np
import pandas as pd

from ..config import DEFAULT_COST_BPS, DEFAULT_N_MONKEYS, DEFAULT_STARTING_CASH


@dataclass
class MonkeyResult:
    final_equity: np.ndarray              # [N]
    percentile_history: pd.DataFrame      # [T, levels]  -- equity percentiles per day
    top_equity_history: pd.DataFrame      # [T, top_k]   -- equity paths of top-K monkeys
    metadata: Dict


def simulate_monkeys(
    close_panel: pd.DataFrame,
    n_monkeys: int = DEFAULT_N_MONKEYS,
    starting_cash: float = DEFAULT_STARTING_CASH,
    p_trade: float = 0.05,
    p_sell: float = 0.5,
    cost_bps: float = DEFAULT_COST_BPS,
    top_k_paths: int = 10,
    seed: int = 42,
    percentile_levels: List[int] = (5, 25, 50, 75, 95),
) -> MonkeyResult:
    if close_panel.isna().any().any():
        # forward-fill any remaining gaps to avoid NaN propagation in shares calc
        close_panel = close_panel.ffill().bfill()

    px = close_panel.values.astype(np.float64)  # [T, K]
    T, K = px.shape
    if K == 0 or T == 0:
        raise ValueError("Empty price panel; nothing to simulate")

    rng = np.random.default_rng(seed)

    cash = np.full(n_monkeys, float(starting_cash))
    shares = np.zeros(n_monkeys, dtype=np.float64)
    pos = np.full(n_monkeys, -1, dtype=np.int32)  # -1 = no position
    cost = cost_bps / 10_000.0

    percentile_levels = list(percentile_levels)
    pct_history = np.zeros((T, len(percentile_levels)), dtype=np.float64)
    # Track top-K monkeys by FINAL equity — we don't know who they are yet,
    # so record EVERY monkey's equity coarsely (every 5 days) and rebuild top-K paths at the end.
    snapshot_stride = max(1, T // 252)  # ~weekly snapshots
    snap_t = list(range(0, T, snapshot_stride)) + [T - 1]
    snap_t = sorted(set(snap_t))
    equity_snapshots = np.zeros((len(snap_t), n_monkeys), dtype=np.float32)
    next_snap_i = 0

    for t in range(T):
        prices_t = px[t]
        has_pos = pos >= 0
        pos_safe = np.where(has_pos, pos, 0)
        mark = np.where(has_pos, shares * prices_t[pos_safe], 0.0)
        equity = cash + mark

        pct_history[t] = np.percentile(equity, percentile_levels)

        if next_snap_i < len(snap_t) and t == snap_t[next_snap_i]:
            equity_snapshots[next_snap_i] = equity.astype(np.float32)
            next_snap_i += 1

        # Decide who acts today
        action_roll = rng.random(n_monkeys)
        trade_mask = action_roll < p_trade

        # Sells: trading, has position, coin flip
        sell_roll = rng.random(n_monkeys)
        sell_mask = trade_mask & has_pos & (sell_roll < p_sell)

        # Buys: trading, no position
        buy_mask = trade_mask & ~has_pos

        if sell_mask.any():
            idx = np.where(sell_mask)[0]
            sell_pos = pos[idx]
            proceeds = shares[idx] * prices_t[sell_pos] * (1.0 - cost)
            cash[idx] += proceeds
            shares[idx] = 0.0
            pos[idx] = -1

        if buy_mask.any():
            idx = np.where(buy_mask)[0]
            new_tickers = rng.integers(0, K, size=idx.size).astype(np.int32)
            buy_prices = prices_t[new_tickers]
            # Skip any zero/NaN-priced ticker by clipping (shouldn't happen after ffill, but safe)
            buy_prices = np.where(buy_prices > 0, buy_prices, 1.0)
            amount = cash[idx] * (1.0 - cost)
            new_shares = amount / buy_prices
            shares[idx] = new_shares
            pos[idx] = new_tickers
            cash[idx] = 0.0

    # Final equity using last day's prices
    prices_T = px[-1]
    has_pos = pos >= 0
    pos_safe = np.where(has_pos, pos, 0)
    mark = np.where(has_pos, shares * prices_T[pos_safe], 0.0)
    final_equity = cash + mark

    # Build outputs
    dates = close_panel.index
    pct_df = pd.DataFrame(
        pct_history,
        index=dates,
        columns=[f"p{p}" for p in percentile_levels],
    )

    top_ids = np.argpartition(-final_equity, kth=min(top_k_paths, n_monkeys - 1))[:top_k_paths]
    # argpartition leaves the top-K unsorted — order them best-first so plots
    # and column labels are stable across runs.
    top_ids = top_ids[np.argsort(-final_equity[top_ids])]
    # snapshot index -> proper datetime
    snap_dates = dates[snap_t]
    top_equity_history = pd.DataFrame(
        equity_snapshots[:, top_ids],
        index=snap_dates,
        columns=[f"monkey_{i}" for i in top_ids],
    )

    metadata = {
        "n_monkeys": n_monkeys,
        "starting_cash": starting_cash,
        "p_trade": p_trade,
        "p_sell": p_sell,
        "cost_bps": cost_bps,
        "median_final": float(np.median(final_equity)),
        "mean_final": float(np.mean(final_equity)),
        "best_final": float(np.max(final_equity)),
        "worst_final": float(np.min(final_equity)),
        "frac_beat_starting": float((final_equity > starting_cash).mean()),
    }

    return MonkeyResult(
        final_equity=final_equity,
        percentile_history=pct_df,
        top_equity_history=top_equity_history,
        metadata=metadata,
    )
