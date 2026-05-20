"""Feature engineering for the AI trader.

Produces a long-form DataFrame indexed by (date, ticker) with feature columns
plus a forward-return target. Only past-and-present information is used per row.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _rsi(close: pd.DataFrame, window: int = 14) -> pd.DataFrame:
    delta = close.diff()
    up = delta.clip(lower=0.0)
    down = -delta.clip(upper=0.0)
    roll_up = up.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()
    roll_down = down.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()
    rs = roll_up / roll_down.replace(0, np.nan)
    rsi = 100 - 100 / (1 + rs)
    # By convention: pure-uptrend window -> 100, pure-downtrend -> 0, flat -> 50.
    rsi = rsi.where(~((roll_down == 0) & (roll_up > 0)), 100.0)
    rsi = rsi.where(~((roll_up == 0) & (roll_down > 0)), 0.0)
    rsi = rsi.where(~((roll_up == 0) & (roll_down == 0)), 50.0)
    return rsi


def _macd_signal(close: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    return (macd - signal_line) / close.replace(0, np.nan)


def _volume_zscore(volume: pd.DataFrame, window: int = 20) -> pd.DataFrame:
    mean = volume.rolling(window=window, min_periods=window).mean()
    std = volume.rolling(window=window, min_periods=window).std().replace(0, np.nan)
    return (volume - mean) / std


FEATURE_COLS = ["ret_1d", "ret_5d", "ret_20d", "vol_20", "vol_60",
                "rsi_14", "macd_sig", "vol_z", "abn_ret"]


def build_feature_panel(
    close_panel: pd.DataFrame,
    volume_panel: pd.DataFrame,
    forward_horizon: int = 5,
) -> pd.DataFrame:
    """Return the long-form (date, ticker) feature frame WITHOUT dropping NaN-target rows.

    Used by the perpetual tick runner so the predict-date rows (which have
    no forward target yet) survive into prediction-time slicing. The training
    slicer in `models/ai_step.py` is responsible for excluding those rows.
    """
    ret_1d = close_panel.pct_change(1)
    ret_5d = close_panel.pct_change(5)
    ret_20d = close_panel.pct_change(20)
    vol_20 = ret_1d.rolling(20).std()
    vol_60 = ret_1d.rolling(60).std()
    rsi_14 = _rsi(close_panel, 14)
    macd_sig = _macd_signal(close_panel)
    vol_z = _volume_zscore(volume_panel, 20)
    abn_ret = ret_1d - ret_1d.rolling(20).mean()

    fwd_ret = close_panel.pct_change(forward_horizon).shift(-forward_horizon)
    y_up = (fwd_ret > 0).astype("float64").where(fwd_ret.notna())

    frames = {
        "ret_1d": ret_1d,
        "ret_5d": ret_5d,
        "ret_20d": ret_20d,
        "vol_20": vol_20,
        "vol_60": vol_60,
        "rsi_14": rsi_14,
        "macd_sig": macd_sig,
        "vol_z": vol_z,
        "abn_ret": abn_ret,
        "fwd_ret": fwd_ret,
        "y_up": y_up,
    }

    longs = []
    for name, df in frames.items():
        s = df.stack(future_stack=True).rename(name)
        longs.append(s)
    feat = pd.concat(longs, axis=1)
    feat.index.names = ["date", "ticker"]
    # Drop rows where features themselves are NaN (warmup period). KEEP rows
    # where only `y_up`/`fwd_ret` are NaN — they're the prediction frontier.
    return feat.dropna(subset=FEATURE_COLS)


def build_features(
    close_panel: pd.DataFrame,
    volume_panel: pd.DataFrame,
    forward_horizon: int = 5,
) -> pd.DataFrame:
    """Backwards-compatible variant: drops rows where the forward target is NaN.

    Used by the Streamlit one-shot pipeline that does batch walk-forward training.
    """
    panel = build_feature_panel(close_panel, volume_panel, forward_horizon=forward_horizon)
    return panel.dropna(subset=["y_up"])
