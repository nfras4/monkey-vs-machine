"""Weight-based backtest driver shared by all strategies."""
from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd

from ..config import DEFAULT_COST_BPS, DEFAULT_STARTING_CASH
from .metrics import summarise


def run_weights_backtest(
    prices: pd.DataFrame,
    target_weights: pd.DataFrame,
    cost_bps: float = DEFAULT_COST_BPS,
    starting_cash: float = DEFAULT_STARTING_CASH,
) -> Dict:
    """Backtest from a target-weights matrix.

    prices: wide DataFrame [date x ticker] of close prices.
    target_weights: wide DataFrame [date x ticker], rows sum to <= 1.
    Weights are read at the close of day t and earn day t+1's return (no look-ahead).
    Costs are charged on the turnover entering day t+1.
    """
    # Align weights to price index/columns
    weights = target_weights.reindex(index=prices.index, columns=prices.columns).fillna(0.0)

    # Daily returns of each ticker
    rets = prices.pct_change().fillna(0.0)

    # Held weights: shift forward by 1 day so today's return uses yesterday's
    # target (no look-ahead).
    held = weights.shift(1).fillna(0.0)

    # Strategy return before costs.
    gross_ret = (held * rets).sum(axis=1)

    # Turnover at day t = change in held position from t-1 to t.
    # Conventional one-way turnover = 0.5 * sum(|Δw|) because each
    # rebalance counts both the sell and the offsetting buy.
    turnover = 0.5 * held.diff().abs().sum(axis=1).fillna(0.0)
    cost_drag = turnover * (cost_bps / 10_000.0)

    net_ret = gross_ret - cost_drag

    equity = starting_cash * (1.0 + net_ret).cumprod()

    return {
        "equity": equity,
        "returns": net_ret,
        "turnover": turnover,
        "metrics": summarise(equity, net_ret, turnover),
        "weights": weights,
    }


def buy_and_hold_weights(prices: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """Convenience: build a 100%-in-one-ticker weights matrix for a benchmark."""
    weights = pd.DataFrame(0.0, index=prices.index, columns=prices.columns)
    if ticker in weights.columns:
        weights[ticker] = 1.0
    return weights
