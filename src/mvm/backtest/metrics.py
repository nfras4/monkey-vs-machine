"""Standard backtest performance metrics."""
from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd

from ..config import TRADING_DAYS_PER_YEAR


def cagr(equity: pd.Series) -> float:
    if len(equity) < 2:
        return 0.0
    n_years = len(equity) / TRADING_DAYS_PER_YEAR
    if n_years <= 0:
        return 0.0
    ratio = equity.iloc[-1] / equity.iloc[0]
    if ratio <= 0:
        return -1.0
    return ratio ** (1 / n_years) - 1


def annualised_sharpe(returns: pd.Series, rf: float = 0.0) -> float:
    excess = returns - rf / TRADING_DAYS_PER_YEAR
    std = excess.std()
    if std == 0 or np.isnan(std):
        return 0.0
    return float(excess.mean() / std * np.sqrt(TRADING_DAYS_PER_YEAR))


def max_drawdown(equity: pd.Series) -> float:
    running_max = equity.cummax()
    drawdown = equity / running_max - 1.0
    return float(drawdown.min())


def hit_rate(returns: pd.Series) -> float:
    if returns.empty:
        return 0.0
    return float((returns > 0).mean())


def summarise(equity: pd.Series, returns: pd.Series, turnover: pd.Series | None = None) -> Dict:
    return {
        "final_equity": float(equity.iloc[-1]) if len(equity) else 0.0,
        "cagr": cagr(equity),
        "sharpe": annualised_sharpe(returns),
        "max_drawdown": max_drawdown(equity),
        "hit_rate": hit_rate(returns),
        "avg_turnover": float(turnover.mean()) if turnover is not None and len(turnover) else 0.0,
    }
