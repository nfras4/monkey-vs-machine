"""Pure per-day monkey stepper used by the perpetual tick.

The batch `simulate_monkeys` entrypoint in `monkey.py` is preserved for the
local Streamlit one-shot path. This module is the API used by `runner_tick.py`.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    import pandas as pd
    from .personality import Personality


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


def apply_personality_overrides(
    actions: np.ndarray,
    prices_today: np.ndarray,
    cash: np.ndarray,
    shares: np.ndarray,
    pos: np.ndarray,
    *,
    named_personalities: "dict[int, tuple[str, Personality]]",
    pre_step_state: "dict[int, tuple[float, float, int]]",
    rng_named: np.random.Generator,
    date: str,
    close_filled: "pd.DataFrame",
    universe: list[str],
    cost_bps: float = 5.0,
) -> None:
    """Overwrite the vector-path decisions for the ~8 named-personality monkeys.

    The 99,992 unnamed monkeys are left exactly as `step_monkeys_one_day`
    produced. For each named monkey:

    1. Revert cash/shares/pos to their pre-step values (from `pre_step_state`).
    2. Reset actions[mid] = 0 (hold).
    3. Call personality.decide(...) with the independent `rng_named` stream.
    4. Apply the resulting Decision (sell or buy) using the same cost model
       as the main vector path.

    All mutations are in-place. The function is iterating dict-order-stable
    (named_personalities is sorted by monkey_id at load time), so the RNG
    stream advances in a deterministic order.
    """
    cost = cost_bps / 10_000.0
    for mid, (_name, personality) in named_personalities.items():
        # Event-only personalities (Lakers Joe, Weekend Wendy) keep whatever
        # decision the main vector path made for them. Equity adjustment runs
        # later in runner_tick.py.
        if not getattr(personality, "affects_trades", True):
            continue

        pre_cash, pre_shares, pre_pos = pre_step_state[mid]
        cash[mid] = pre_cash
        shares[mid] = pre_shares
        pos[mid] = pre_pos
        actions[mid] = 0  # default hold

        has_pos = pre_pos >= 0
        decision = personality.decide(
            rng_named, date, close_filled, universe, int(pre_pos), bool(has_pos),
        )
        if decision.action == 1 and has_pos:  # SELL
            sell_price = float(prices_today[pre_pos])
            if np.isfinite(sell_price) and sell_price > 0:
                proceeds = pre_shares * sell_price * (1.0 - cost)
                cash[mid] = pre_cash + proceeds
                shares[mid] = 0.0
                pos[mid] = -1
                actions[mid] = 1
        elif decision.action == 2 and not has_pos:  # BUY
            tix = decision.ticker_idx
            if 0 <= tix < len(universe):
                buy_price = float(prices_today[tix])
                if buy_price <= 0 or not np.isfinite(buy_price):
                    buy_price = 1.0
                amount = pre_cash * (1.0 - cost)
                new_shares = amount / buy_price
                shares[mid] = new_shares
                pos[mid] = np.int32(tix)
                cash[mid] = 0.0
                actions[mid] = 2
