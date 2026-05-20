"""S&P 500 ticker universe.

Primary: scrape Wikipedia constituents.
Fallback: a hardcoded list of large-cap names that should always resolve on yfinance.
"""
from __future__ import annotations

import logging
import re
from io import StringIO
from typing import List

import pandas as pd
import requests

log = logging.getLogger(__name__)

# Whitelist for ticker symbols read from external sources. yfinance accepts
# letters, digits, and '-'; everything else is treated as a poisoned row.
_TICKER_RE = re.compile(r"^[A-Z0-9\-]{1,8}$")

# Stable fallback — 100 large-cap S&P tickers. Used if Wikipedia scrape fails.
FALLBACK_SP100: List[str] = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "GOOG", "AMZN", "META", "TSLA", "BRK-B", "AVGO",
    "JPM", "LLY", "V", "WMT", "XOM", "UNH", "MA", "JNJ", "PG", "ORCL",
    "HD", "COST", "ABBV", "BAC", "KO", "MRK", "CVX", "ADBE", "PEP", "AMD",
    "NFLX", "CRM", "ACN", "MCD", "TMO", "LIN", "ABT", "CSCO", "WFC", "DHR",
    "GE", "DIS", "AMGN", "VZ", "PM", "INTU", "TXN", "IBM", "QCOM", "CAT",
    "BX", "ISRG", "GS", "RTX", "NOW", "PFE", "T", "SPGI", "AXP", "NEE",
    "BKNG", "AMAT", "SYK", "MS", "C", "HON", "UBER", "BLK", "TJX", "LOW",
    "PLD", "SCHW", "MDT", "ETN", "PGR", "ADP", "DE", "ANET", "VRTX", "BSX",
    "TMUS", "GILD", "REGN", "CB", "MMC", "ELV", "ADI", "LMT", "MU", "PANW",
    "BMY", "MO", "FI", "SO", "SBUX", "ZTS", "CI", "INTC", "DUK", "EQIX",
]


def get_sp500_tickers_wikipedia(timeout: float = 10.0) -> List[str]:
    """Try to scrape current S&P 500 constituents from Wikipedia. Raise on failure.

    Uses an explicit `requests` fetch (so we control TLS verification + timeout +
    UA) and applies a strict ticker whitelist before returning. This prevents a
    poisoned row from leaking into filesystem-bound code downstream.
    """
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    headers = {"User-Agent": "monkey-vs-machine/0.1 (+https://example.invalid)"}
    resp = requests.get(url, timeout=timeout, headers=headers)
    resp.raise_for_status()
    tables = pd.read_html(StringIO(resp.text))
    df = tables[0]
    raw = (df["Symbol"].astype(str).str.replace(".", "-", regex=False)).tolist()
    tickers = [t for t in raw if _TICKER_RE.fullmatch(t)]
    dropped = len(raw) - len(tickers)
    if dropped:
        log.warning("Dropped %d non-whitelisted ticker symbols from Wikipedia scrape", dropped)
    if len(tickers) < 400:
        raise RuntimeError(f"Wikipedia scrape returned only {len(tickers)} valid tickers")
    return tickers


def get_universe(size: int = 100, use_wikipedia: bool = False) -> List[str]:
    """Return up to `size` tickers. Uses Wikipedia when requested, else fallback.

    Wikipedia is opt-in because it requires `lxml` / `html5lib` and a network hit;
    the fallback list is plenty for v1.
    """
    if use_wikipedia:
        try:
            tickers = get_sp500_tickers_wikipedia()
            log.info("Loaded %d tickers from Wikipedia", len(tickers))
        except Exception as e:
            log.warning("Wikipedia scrape failed (%s); using fallback list", e)
            tickers = FALLBACK_SP100
    else:
        tickers = FALLBACK_SP100
    return tickers[:size]
