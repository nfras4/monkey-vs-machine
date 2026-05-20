"""Top-level orchestration: data -> AI -> monkeys -> benchmark."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import pandas as pd

from .backtest.engine import buy_and_hold_weights, run_weights_backtest
from .config import (
    DEFAULT_N_MONKEYS,
    DEFAULT_STARTING_CASH,
    DEFAULT_TOP_K,
    DEFAULT_UNIVERSE_SIZE,
    DEFAULT_YEARS,
)
from .data.prices import load_prices, to_close_panel, to_volume_panel
from .data.universe import get_universe
from .features import build_features
from .models.ai_trader import AIResult, run_ai_trader
from .models.monkey import MonkeyResult, simulate_monkeys

log = logging.getLogger(__name__)


@dataclass
class ExperimentResult:
    close_panel: pd.DataFrame
    volume_panel: pd.DataFrame
    tickers: List[str]
    ai: AIResult
    ai_backtest: Dict
    spy_backtest: Optional[Dict]
    monkeys: MonkeyResult
    config: Dict = field(default_factory=dict)


def run_experiment(
    universe_size: int = DEFAULT_UNIVERSE_SIZE,
    years: int = DEFAULT_YEARS,
    n_monkeys: int = DEFAULT_N_MONKEYS,
    top_k: int = DEFAULT_TOP_K,
    starting_cash: float = DEFAULT_STARTING_CASH,
    refresh: bool = False,
    include_benchmark: bool = True,
    use_wikipedia: bool = False,
) -> ExperimentResult:
    log.info("Building universe (size=%d)", universe_size)
    tickers = get_universe(size=universe_size, use_wikipedia=use_wikipedia)

    log.info("Loading prices: %d tickers x %d years", len(tickers), years)
    long_df = load_prices(tickers, years=years, refresh=refresh)
    close = to_close_panel(long_df)
    volume = to_volume_panel(long_df).reindex(index=close.index, columns=close.columns).fillna(0)

    log.info("Close panel shape: %s", close.shape)

    log.info("Computing features")
    feats = build_features(close, volume)

    log.info("Training AI trader")
    ai = run_ai_trader(feats, close, top_k=top_k)

    log.info("Backtesting AI weights")
    ai_bt = run_weights_backtest(close, ai.weights, starting_cash=starting_cash)

    spy_bt = None
    if include_benchmark:
        log.info("Loading SPY benchmark")
        try:
            spy_long = load_prices(["SPY"], years=years, refresh=refresh, cache_tag="spy_only")
            spy_close = to_close_panel(spy_long)
            spy_close = spy_close.reindex(close.index).ffill()
            spy_weights = buy_and_hold_weights(spy_close, "SPY")
            spy_bt = run_weights_backtest(spy_close, spy_weights, starting_cash=starting_cash, cost_bps=0.0)
        except Exception as e:
            log.warning("SPY benchmark unavailable: %s", e)
            spy_bt = None

    log.info("Simulating %d monkeys", n_monkeys)
    monkeys = simulate_monkeys(close, n_monkeys=n_monkeys, starting_cash=starting_cash)

    return ExperimentResult(
        close_panel=close,
        volume_panel=volume,
        tickers=list(close.columns),
        ai=ai,
        ai_backtest=ai_bt,
        spy_backtest=spy_bt,
        monkeys=monkeys,
        config={
            "universe_size": universe_size,
            "years": years,
            "n_monkeys": n_monkeys,
            "top_k": top_k,
            "starting_cash": starting_cash,
        },
    )
