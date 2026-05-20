"""Pure per-day monkey stepper used by the perpetual tick.

The batch `simulate_monkeys` entrypoint in `monkey.py` is preserved for the
local Streamlit one-shot path. This module is the API used by `runner_tick.py`.
"""
from __future__ import annotations

import numpy as np


def step_monkeys_one_day(
    prices_today: np.ndarray,
    cash: np.ndarray,
    shares: np.ndarray,
    pos: np.ndarray,
    *,
    rng: np.random.Generator,
    p_trade: float = 0.05,
    p_sell: float = 0.5,
    cost_bps: float = 5.0,
) -> np.ndarray:
    """Advance all monkeys by one trading day. Mutates arrays in place.

    Args:
        prices_today: shape (K,) close prices for every ticker (NaN-free).
        cash:         shape (N,) per-monkey cash, mutated.
        shares:       shape (N,) per-monkey shares of `pos[i]`, mutated.
        pos:          shape (N,) int32, ticker index in [0, K) or -1 for cash-only. Mutated.
        rng:          a seeded numpy Generator.
        p_trade:      probability each monkey acts today.
        p_sell:       probability a holder sells (conditional on acting).
        cost_bps:     basis-point transaction cost.

    Returns: shape (N,) int8 action codes: 0=hold, 1=sell, 2=buy.
    """
    n = cash.shape[0]
    k = prices_today.shape[0]
    cost = cost_bps / 10_000.0
    actions = np.zeros(n, dtype=np.int8)

    has_pos = pos >= 0
    trade_roll = rng.random(n)
    trade_mask = trade_roll < p_trade

    sell_roll = rng.random(n)
    sell_mask = trade_mask & has_pos & (sell_roll < p_sell)
    buy_mask = trade_mask & ~has_pos

    if sell_mask.any():
        idx = np.where(sell_mask)[0]
        sell_pos = pos[idx]
        # Defensive NaN/zero guard symmetric with the buy branch below — the
        # docstring promises NaN-free input but a misconfigured caller would
        # otherwise zero out cash silently on sell.
        sell_prices = prices_today[sell_pos]
        sell_prices = np.where(np.isfinite(sell_prices) & (sell_prices > 0), sell_prices, 0.0)
        proceeds = shares[idx] * sell_prices * (1.0 - cost)
        cash[idx] += proceeds
        shares[idx] = 0.0
        pos[idx] = -1
        actions[idx] = 1

    if buy_mask.any():
        idx = np.where(buy_mask)[0]
        new_tickers = rng.integers(0, k, size=idx.size).astype(np.int32)
        buy_prices = prices_today[new_tickers]
        buy_prices = np.where(buy_prices > 0, buy_prices, 1.0)
        amount = cash[idx] * (1.0 - cost)
        new_shares = amount / buy_prices
        shares[idx] = new_shares
        pos[idx] = new_tickers
        cash[idx] = 0.0
        actions[idx] = 2

    return actions


def compute_equity(
    prices_today: np.ndarray,
    cash: np.ndarray,
    shares: np.ndarray,
    pos: np.ndarray,
) -> np.ndarray:
    """Mark monkeys to today's close. Returns equity[N]."""
    has_pos = pos >= 0
    pos_safe = np.where(has_pos, pos, 0)
    mark = np.where(has_pos, shares * prices_today[pos_safe], 0.0)
    return cash + mark
