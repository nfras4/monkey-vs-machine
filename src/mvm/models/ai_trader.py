"""Gradient-boosting AI trader with walk-forward retraining.

Each trading day we predict P(forward-5d return > 0) for every ticker.
On rebalance days, we hold the top-K predicted equal-weighted.
The model is retrained every `retrain_every` days using all data up to that day,
strictly avoiding lookahead.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier

from ..config import (
    DEFAULT_REBALANCE_EVERY,
    DEFAULT_RETRAIN_EVERY,
    DEFAULT_TOP_K,
    DEFAULT_TRAIN_FRAC,
)

FEATURE_COLS = [
    "ret_1d", "ret_5d", "ret_20d",
    "vol_20", "vol_60",
    "rsi_14", "macd_sig",
    "vol_z", "abn_ret",
]

# Must match the `forward_horizon` used by `build_features`. The training-window
# cutoff is shifted back by this many trading days so the label's lookahead
# window never overlaps the prediction date.
FORWARD_HORIZON = 5


@dataclass
class AIResult:
    weights: pd.DataFrame
    predictions: pd.DataFrame      # [date x ticker] P(up), only on prediction days
    feature_importance: Dict[str, float]
    metadata: Dict


def _fit_model(X: np.ndarray, y: np.ndarray) -> HistGradientBoostingClassifier:
    model = HistGradientBoostingClassifier(
        max_iter=200,
        learning_rate=0.05,
        max_depth=6,
        min_samples_leaf=50,
        random_state=42,
    )
    model.fit(X, y)
    return model


def _permutation_importance(model, X: np.ndarray, y: np.ndarray, feature_names: List[str], n_repeats: int = 3, seed: int = 0) -> Dict[str, float]:
    rng = np.random.default_rng(seed)
    base = model.score(X, y)
    imps: Dict[str, float] = {}
    for j, name in enumerate(feature_names):
        drops = []
        for _ in range(n_repeats):
            X_shuf = X.copy()
            rng.shuffle(X_shuf[:, j])
            drops.append(base - model.score(X_shuf, y))
        imps[name] = float(np.mean(drops))
    return imps


def run_ai_trader(
    features: pd.DataFrame,
    close_panel: pd.DataFrame,
    top_k: int = DEFAULT_TOP_K,
    rebalance_every: int = DEFAULT_REBALANCE_EVERY,
    retrain_every: int = DEFAULT_RETRAIN_EVERY,
    train_frac: float = DEFAULT_TRAIN_FRAC,
) -> AIResult:
    """Walk-forward training + ranking.

    features: long-form (date, ticker) frame from `build_features`.
    close_panel: wide [date x ticker] used to know the universe per day.

    Returns weights aligned to `close_panel`'s index/columns.
    """
    if features.empty:
        raise ValueError("No features to train on")

    dates = sorted(features.index.get_level_values("date").unique())
    if len(dates) < 100:
        raise ValueError(f"Not enough dates for walk-forward: {len(dates)}")

    n_train_initial = max(60, int(len(dates) * train_frac))
    train_end_idx = n_train_initial
    # Shift back by FORWARD_HORIZON so the label's lookahead window doesn't
    # overlap any prediction date. (Critical: prevents target leakage at the
    # training-window edge.)
    safe_initial_end_idx = max(60, train_end_idx - FORWARD_HORIZON)
    train_end_date = dates[train_end_idx - 1]
    safe_initial_end_date = dates[safe_initial_end_idx - 1]

    pred_dates = dates[train_end_idx:]

    # Pre-stack features as a numpy array indexed (date, ticker) for fast slicing
    feat_arr = features[FEATURE_COLS]
    y_all = features["y_up"].astype(int)

    # Initial train: only rows whose forward target window has already resolved.
    train_mask = features.index.get_level_values("date") <= safe_initial_end_date
    X_train = feat_arr.loc[train_mask].to_numpy()
    y_train = y_all.loc[train_mask].to_numpy()

    model = _fit_model(X_train, y_train)
    last_retrain_idx = train_end_idx
    feature_importance = _permutation_importance(model, X_train, y_train, FEATURE_COLS)

    predictions: List[pd.Series] = []

    # Build prediction set day-by-day. For speed, group by date once.
    feat_by_date = {d: g for d, g in feat_arr.groupby(level="date")}

    weights = pd.DataFrame(0.0, index=close_panel.index, columns=close_panel.columns)

    current_picks: List[str] = []

    for i, d in enumerate(pred_dates):
        abs_idx = i + train_end_idx  # absolute index of `d` within `dates`

        # Retrain check — train only on rows whose forward target has resolved
        # strictly before `d`.
        days_since_retrain = abs_idx - last_retrain_idx
        if days_since_retrain >= retrain_every and d != pred_dates[-1]:
            safe_train_idx = max(0, abs_idx - FORWARD_HORIZON)
            if safe_train_idx > 0:
                train_cutoff_date = dates[safe_train_idx - 1]
                train_mask = features.index.get_level_values("date") <= train_cutoff_date
                if train_mask.sum() > 100:
                    Xt = feat_arr.loc[train_mask].to_numpy()
                    yt = y_all.loc[train_mask].to_numpy()
                    model = _fit_model(Xt, yt)
                    last_retrain_idx = abs_idx

        g = feat_by_date.get(d)
        if g is not None and not g.empty:
            X_today = g.to_numpy()
            if hasattr(model, "predict_proba"):
                proba = model.predict_proba(X_today)[:, 1]
            else:
                proba = model.predict(X_today).astype(float)

            tickers_today = g.index.get_level_values("ticker").tolist()
            pred_series = pd.Series(proba, index=tickers_today, name=d)
            predictions.append(pred_series)

            # Rebalance on the first day and every `rebalance_every` days
            if i % rebalance_every == 0:
                ranked = pred_series.sort_values(ascending=False)
                current_picks = ranked.head(top_k).index.tolist()

        # Stamp the full weight row each day: explicit zeros for non-picks so
        # rebalancing actually sells old positions. (No ffill — that hid the
        # "sells" and let positions accumulate across rebalances.)
        if current_picks and d in weights.index:
            w = 1.0 / len(current_picks)
            weights.loc[d, :] = 0.0
            weights.loc[d, current_picks] = w

    # Build prediction frame [date x ticker] from list of Series
    if predictions:
        pred_df = pd.DataFrame(predictions).sort_index()
    else:
        pred_df = pd.DataFrame()

    metadata = {
        "n_train_initial": int(n_train_initial),
        "n_pred_days": len(pred_dates),
        "train_end_date": str(train_end_date.date()) if hasattr(train_end_date, "date") else str(train_end_date),
        "top_k": top_k,
        "rebalance_every": rebalance_every,
        "retrain_every": retrain_every,
    }

    return AIResult(
        weights=weights,
        predictions=pred_df,
        feature_importance=feature_importance,
        metadata=metadata,
    )
