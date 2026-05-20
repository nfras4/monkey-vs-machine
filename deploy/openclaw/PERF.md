# openclaw tick performance baseline

Populated from `ticks.duration_seconds` after the first 10 production ticks.

## Local Windows smoke (10 tickers × 90 warmup days × 1000 monkeys)
- First tick:  ~3.6s
- Second day:  ~3.7s
- Re-run:      ~2.6s (cached prices, no yfinance fetch)

## openclaw production targets

| Profile | Universe | Monkeys | Median tick (s) | Notes |
|---|---|---|---|---|
| v1 default | 50 | 100,000 | TBD | populate after 10 ticks |
| v1 scaled | 500 (full SP500) | 100,000 | TBD | when wired |

Soft target per plan A2: median of first 10 measured tick durations < 300s on
modest hardware. Hard cap in `mvm-tick.service`: `TimeoutStartSec=900`.
