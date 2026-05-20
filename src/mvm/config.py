from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
CACHE_DIR = DATA_DIR / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_YEARS = 5
DEFAULT_UNIVERSE_SIZE = 100
DEFAULT_N_MONKEYS = 100_000
DEFAULT_TOP_K = 10
DEFAULT_REBALANCE_EVERY = 5         # trading days
DEFAULT_RETRAIN_EVERY = 63          # ~quarter
DEFAULT_TRAIN_FRAC = 0.6
DEFAULT_COST_BPS = 5.0
DEFAULT_STARTING_CASH = 10_000.0
TRADING_DAYS_PER_YEAR = 252
