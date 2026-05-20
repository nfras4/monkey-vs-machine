# Monkey vs Machine — Spec

## Goal
A simulated stock-trading playground that pits two strategies against each other on real historical S&P 500 data:

1. **AI Trader** — a classical-ML trader (gradient boosting) that uses engineered price features plus a sentiment-style signal, retrained walk-forward.
2. **Monkey Army** — 100,000 random traders, each picking tickers and buy/sell/hold actions at random.

Both are scored on the same backtest engine against an SPY buy-and-hold benchmark. A Streamlit dashboard visualises equity curves, leaderboard, and the distribution of monkey outcomes.

## Non-goals (v1)
- No live trading. The "real broker" path is a stub for later (Alpaca paper API earmarked).
- No intra-day data. Daily bars only.
- No historical news archive. yfinance `.news` is recent-only; backtest uses price-derived attention proxies (volume z-score, gap returns). Live VADER sentiment on yfinance headlines powers a "today's picks" panel only.
- No survivorship-bias correction in v1 (current S&P 500 constituents only). Documented as a known limitation.

## Stack
- Python 3.11+ (works on 3.13)
- yfinance (price + recent news)
- pandas, numpy (data + vectorized monkeys)
- scikit-learn (gradient boosting) with lightgbm as optional accelerator
- vaderSentiment (offline lexicon, no API key)
- Streamlit + Plotly (dashboard)
- pyarrow (parquet caching)

## Data
- **Universe**: configurable subset of S&P 500 (default 100 tickers; can scale to 500). Pulled from Wikipedia constituents list with a local fallback.
- **Bars**: 5 years daily OHLCV, cached to `data/cache/prices.parquet`.
- **Sentiment-style proxy (backtest)**: volume z-score, overnight gap, intraday range, abnormal-return spike.
- **Live news (dashboard only)**: yfinance `.news` headlines + VADER compound score per ticker, refreshed on demand.

## AI Trader
- Features (per ticker, per day): returns_1d/5d/20d, RSI_14, MACD signal, vol_20/60, volume z-score, gap_ret, abnormal_return.
- Target: forward 5-day return > 0 (binary classifier).
- Training: walk-forward — first 60% of dates train, rolling retrain every quarter on the remainder.
- Decision: each day, rank predicted P(up) across the universe; hold top-K equal-weighted (K = 10 by default). Rebalance weekly.
- Cost model: 5 bps per turnover unit.

## Monkey Army
- N = 100,000 monkeys, each starts with $10,000 cash.
- Single-position-at-a-time rule (keeps state O(N), not O(N·K)).
- Each trading day, each monkey acts with probability `p_trade` (default 0.05):
  - If holding nothing: buy a uniformly-random ticker with all cash.
  - If holding something: sell with probability 0.5, else hold.
- Vectorized with numpy; expected runtime < 10s on a laptop.
- Outputs: final equity per monkey, equity curves for top-K + median.

## Backtest engine
- Shared driver for both models: takes a target-weights matrix `[T, K]` (rows=days, cols=tickers, weights sum ≤ 1) and produces equity curve + metrics.
- Metrics: CAGR, annualised Sharpe (rf=0), max drawdown, hit rate, turnover.
- Benchmark: SPY buy-and-hold over the same window.
- Monkey path uses a direct cash+holdings simulator (not the weights driver) because their state is discrete.

## Dashboard
- Sidebar controls: date range, universe size, monkey count, AI top-K, "refresh data" button.
- Tabs:
  1. **Race** — equity curves: AI / best monkey / median monkey / SPY.
  2. **Monkey distribution** — histogram of final equities + percentile of AI vs the monkey pack.
  3. **AI internals** — feature importances + recent picks table.
  4. **Today's read** — live VADER sentiment + AI's top picks for the next session.

## Quality bar
- `python scripts/run_experiment.py --quick` runs end-to-end on a 10-ticker subset in < 60s with no errors.
- Streamlit app launches and renders all 4 tabs without errors.
- Backtest metrics are sensible: SPY benchmark CAGR within a few % of known value; monkey median ≈ market return; ≥ a handful of monkeys beat SPY by luck alone.
