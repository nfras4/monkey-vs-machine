"""Per-day AI training + ranking + rebalance helpers (pure functions).

Used by `runner_tick.py` to fit one model on history-to-date, predict today,
and produce target holdings. The batch `run_ai_trader` in `ai_trader.py` is
preserved for the Streamlit one-shot path.
"""
from __future__ import annotations

from typing import Dict, List

import numpy as np
import pandas as pd

from .ai_trader import FEATURE_COLS, FORWARD_HORIZON


def slice_train(features: pd.DataFrame, predict_date) -> pd.DataFrame:
    """Return rows whose forward-horizon target window has already resolved by `predict_date`.

    `features` is a long-form (date, ticker) DataFrame that already includes
    `y_up`. We exclude the last `FORWARD_HORIZON` trading days before
    `predict_date` from training so the label doesn't peek at the prediction
    window.
    """
    dates = sorted(features.index.get_level_values("date").unique())
    if predict_date not in dates:
        # Use up to the last available date < predict_date as the cutoff anchor.
        future = [d for d in dates if d < predict_date]
        if not future:
            return features.iloc[0:0]
        anchor = future[-1]
    else:
        anchor = predict_date
    anchor_idx = dates.index(anchor)
    cutoff_idx = anchor_idx - FORWARD_HORIZON
    if cutoff_idx <= 0:
        return features.iloc[0:0]
    cutoff_date = dates[cutoff_idx - 1]
    mask = features.index.get_level_values("date") <= cutoff_date
    return features.loc[mask]


def slice_predict(features: pd.DataFrame, predict_date) -> pd.DataFrame:
    """Return rows for the prediction date itself."""
    if predict_date not in features.index.get_level_values("date"):
        return features.iloc[0:0]
    return features.loc[features.index.get_level_values("date") == predict_date]


def to_xy(rows: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, List[str]]:
    X = rows[FEATURE_COLS].to_numpy()
    # Predict rows may have NaN y_up (target hasn't resolved yet) — coerce to 0.
    # Training rows are already NaN-free thanks to slice_train.
    if "y_up" in rows.columns:
        y = rows["y_up"].fillna(0).astype(int).to_numpy()
    else:
        y = np.zeros(len(rows), dtype=int)
    tickers = rows.index.get_level_values("ticker").tolist()
    return X, y, tickers


def predict_ranking(builder, X_today: np.ndarray, tickers_today: List[str]) -> pd.Series:
    """Return P(up) per ticker, descending."""
    proba = builder.predict_proba(X_today)
    if proba.ndim == 2 and proba.shape[1] >= 2:
        scores = proba[:, 1]
    else:
        scores = proba.ravel()
    return pd.Series(scores, index=tickers_today).sort_values(ascending=False)


def apply_rebalance(
    current_holdings: Dict[str, float],
    ranking: pd.Series,
    top_k: int,
) -> tuple[Dict[str, float], float]:
    """Build new equal-weight top-K holdings; return (new_holdings, turnover).

    Turnover is one-way: 0.5 * sum(|new_w - old_w|).
    """
    picks = ranking.head(top_k).index.tolist()
    if not picks:
        new_holdings: Dict[str, float] = {}
    else:
        w = 1.0 / len(picks)
        new_holdings = {t: w for t in picks}

    all_tickers = set(current_holdings) | set(new_holdings)
    diff = sum(abs(new_holdings.get(t, 0.0) - current_holdings.get(t, 0.0)) for t in all_tickers)
    turnover = 0.5 * diff
    return new_holdings, turnover
