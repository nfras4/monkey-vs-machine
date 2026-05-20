"""Price data loader with parquet caching."""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, List, Optional

import pandas as pd
import yfinance as yf

from ..config import CACHE_DIR

log = logging.getLogger(__name__)

_SAFE_TAG = re.compile(r"^[A-Za-z0-9_\-]+$")


def _cache_path(tag: str) -> Path:
    # Refuse anything that could traverse the filesystem.
    if not _SAFE_TAG.fullmatch(tag):
        raise ValueError(f"unsafe cache tag: {tag!r}")
    return CACHE_DIR / f"prices_{tag}.parquet"


def _is_fresh(path: Path, max_age_hours: int = 18) -> bool:
    if not path.exists():
        return False
    age = datetime.now() - datetime.fromtimestamp(path.stat().st_mtime)
    return age < timedelta(hours=max_age_hours)


def download_prices(
    tickers: Iterable[str],
    years: int = 5,
    end: Optional[datetime] = None,
) -> pd.DataFrame:
    """Batch-download adjusted close + volume from yfinance.

    Returns a long DataFrame indexed by (Date, Ticker) with columns
    [open, high, low, close, volume]. Adjusted prices (auto_adjust=True).
    """
    tickers = list(tickers)
    end = end or datetime.now()
    start = end - timedelta(days=int(365.25 * years) + 5)

    log.info("Downloading %d tickers from %s to %s", len(tickers), start.date(), end.date())
    raw = yf.download(
        tickers=tickers,
        start=start.strftime("%Y-%m-%d"),
        end=end.strftime("%Y-%m-%d"),
        auto_adjust=True,
        progress=False,
        group_by="ticker",
        threads=True,
    )

    if raw.empty:
        raise RuntimeError("yfinance returned no data")

    # yfinance returns a MultiIndex (Ticker, Field) on columns when multiple tickers.
    # When only one ticker, columns are flat — normalise both shapes.
    frames: List[pd.DataFrame] = []
    if isinstance(raw.columns, pd.MultiIndex):
        for ticker in tickers:
            if ticker not in raw.columns.get_level_values(0):
                continue
            sub = raw[ticker].copy()
            sub.columns = [c.lower() for c in sub.columns]
            sub["ticker"] = ticker
            frames.append(sub.reset_index().rename(columns={"Date": "date"}))
    else:
        sub = raw.copy()
        sub.columns = [c.lower() for c in sub.columns]
        sub["ticker"] = tickers[0]
        frames.append(sub.reset_index().rename(columns={"Date": "date"}))

    if not frames:
        raise RuntimeError("No usable price data after download")

    long_df = pd.concat(frames, ignore_index=True)
    long_df = long_df.dropna(subset=["close"])
    long_df["date"] = pd.to_datetime(long_df["date"]).dt.tz_localize(None)
    return long_df.set_index(["date", "ticker"]).sort_index()


def load_prices(
    tickers: Iterable[str],
    years: int = 5,
    refresh: bool = False,
    cache_tag: Optional[str] = None,
) -> pd.DataFrame:
    """Load (and cache) a panel of prices.

    Returns the same long-form DataFrame as `download_prices`.
    """
    tickers = list(tickers)
    tag = cache_tag or f"{len(tickers)}t_{years}y"
    path = _cache_path(tag)

    if not refresh and _is_fresh(path):
        log.info("Using cached prices: %s", path.name)
        return pd.read_parquet(path)

    df = download_prices(tickers, years=years)
    # Atomic write: avoid corrupted cache if a concurrent process / hard kill
    # interrupts a partial parquet write on Windows.
    tmp = path.with_suffix(path.suffix + ".tmp")
    df.to_parquet(tmp)
    os.replace(tmp, path)
    log.info("Cached %d rows -> %s", len(df), path.name)
    return df


def to_close_panel(long_df: pd.DataFrame) -> pd.DataFrame:
    """Convert long-form (date, ticker) -> wide [date x ticker] close prices."""
    panel = long_df["close"].unstack("ticker").sort_index()
    # Coverage is measured on RAW data — if we ffill first, a recently-listed
    # ticker with a long ffilled tail can sneak past the threshold.
    coverage = panel.notna().mean()
    keep = coverage[coverage >= 0.9].index
    panel = panel[keep]
    # Now fill modest gaps for the survivors so downstream returns are clean.
    panel = panel.ffill(limit=5)
    # Drop dates that are still entirely NaN.
    panel = panel.dropna(how="all")
    return panel


def to_volume_panel(long_df: pd.DataFrame) -> pd.DataFrame:
    panel = long_df["volume"].unstack("ticker").sort_index()
    panel = panel.ffill(limit=5).fillna(0)
    return panel
