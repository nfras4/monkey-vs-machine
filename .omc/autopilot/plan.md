# Implementation Plan

## Phase A — Scaffolding (done in this turn)
- [x] Project tree under `D:/claudecode/monkey-vs-machine`
- [x] `pyproject.toml` + `requirements.txt`
- [x] `README.md`, `.gitignore`

## Phase B — Data layer
- `src/mvm/data/universe.py` — S&P 500 ticker fetch (Wikipedia) + 100-ticker fallback list.
- `src/mvm/data/prices.py` — yfinance batch download, parquet cache, refresh-if-stale.
- `src/mvm/data/news.py` — yfinance `.news` per ticker (live only).
- `src/mvm/data/sentiment.py` — VADER wrapper.

## Phase C — Backtest engine
- `src/mvm/backtest/engine.py` — `run_weights_backtest(prices, weights, cost_bps)` returning equity curve + metrics.
- `src/mvm/backtest/metrics.py` — CAGR / Sharpe / drawdown / turnover.

## Phase D — Models
- `src/mvm/models/monkey.py` — `simulate_monkeys(prices, n=100_000, ...)` numpy-vectorized.
- `src/mvm/features.py` — feature engineering across the price panel.
- `src/mvm/models/ai_trader.py` — walk-forward sklearn `HistGradientBoostingClassifier`, weekly rebalance, top-K equal weight.

## Phase E — Orchestration + dashboard
- `src/mvm/runner.py` — high-level `run_experiment(...)` that orchestrates data → AI → monkeys → benchmark and packages a result dict.
- `scripts/run_experiment.py` — CLI smoke test.
- `app/dashboard.py` — Streamlit UI with 4 tabs.

## Phase F — QA cycle
- `python -m pip install -r requirements.txt`
- `python scripts/run_experiment.py --quick`
- `streamlit run app/dashboard.py` (smoke check launch + render)

## Phase G — Validation
- Spawn code-reviewer + security-reviewer subagents over the finished code, fix anything flagged.
