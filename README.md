# Monkey vs Machine

An AI trader vs 100,000 random monkeys, racing on real historical S&P 500 data.

## What it does

- Downloads 5 years of daily S&P 500 prices (yfinance, cached locally).
- Trains a gradient-boosting classifier on engineered price features + price-derived attention proxies; rebalances weekly into the top-K predicted winners.
- Simulates 100,000 random "monkey" traders on the same universe with the same starting capital.
- Backtests both against SPY buy-and-hold and renders the race in a Streamlit dashboard.

## Quickstart

```powershell
cd D:\claudecode\monkey-vs-machine
python -m pip install -r requirements.txt
python scripts/run_experiment.py --quick     # smoke test, ~10 tickers, fast
python scripts/run_experiment.py             # full run, default 100 tickers
streamlit run app/dashboard.py
```

## How "sentiment" works here

yfinance `.news` only exposes the *recent* headlines per ticker, not a historical archive. That makes it useless for honest backtesting (you can't time-travel news to 2022). Two compromises:

- **In the backtest**, we use *price-derived attention proxies* (volume z-score, overnight gap, abnormal-return spike). These behave like a noisy sentiment surrogate and don't leak future information.
- **In the dashboard's "Today's read" tab**, we *do* use yfinance live news + VADER. Those scores feed the AI's "what would I buy tomorrow" panel only — never the historical race.

Slots are stubbed for swapping in GDELT, NewsAPI, or Reddit Pushshift later if you want a real historical sentiment feed.

## Real money (later)

`src/mvm/broker.py` has a stub interface. A future iteration can wire Alpaca's paper trading API to act on the AI's daily output. **Not** wired in v1 — by design.

## Project layout

```
src/mvm/
  data/           # prices, news, sentiment, universe
  backtest/       # shared engine + metrics
  models/         # monkey + ai_trader
  features.py     # feature engineering
  runner.py       # orchestrate full experiment
app/dashboard.py  # Streamlit UI
scripts/          # CLI entrypoints
```

## Known limitations

- Survivorship bias: we use the *current* S&P 500 constituents. Companies that dropped out are missing.
- No intra-day, no fundamentals, no options.
- Transaction cost is a flat 5 bps per turnover unit (no spread modelling).
- Walk-forward retraining uses a single split + quarterly refresh; not full purged-CV.

## Perpetual mode

The one-shot Streamlit pipeline above is the original episodic experiment. The
**perpetual mode** keeps the simulation alive day-over-day on a dedicated Linux
box ("openclaw"), publishing to a Cloudflare-hosted SvelteKit dashboard.

### Architecture in one sentence

openclaw (Python + sklearn + SQLite) runs one tick per US trading day → pushes
aggregates + 10 named-monkey histories to Cloudflare D1 → SvelteKit dashboard
on Cloudflare Pages reads D1 and renders the public view.

### Key files

| File | Purpose |
|---|---|
| `src/mvm/state/schema.sql` | SQLite source-of-truth schema (model-keyed AI tables) |
| `src/mvm/runner_tick.py` | Two-transaction per-day orchestrator (prices upsert, then simulation) |
| `src/mvm/models/registry.py` | `MODELS = {"hgb_v1": build_hgb_v1}` — adding a new family is one entry |
| `src/mvm/runtime_fingerprint.py` | Captures the (python, lib, lockfile, BLAS) fingerprint per tick |
| `scripts/bootstrap_genesis.py` | One-shot DB seed + warmup price fetch + 3 personality monkey picks |
| `scripts/run_tick.py` | CLI for one tick |
| `scripts/catchup.py` | Replays missing ticks after an outage |
| `scripts/push_to_d1.py` / `scripts/rebuild_d1.py` | D1 egress |
| `dashboard/` | SvelteKit + Pages Function ingest + D1 migrations |
| `deploy/openclaw/` | systemd units + install.sh + token rotation + provisioning README |
| `DETERMINISM.md` | The bit-identical-rerun contract and its scope |

### Local quickstart

```powershell
# Bootstrap a tiny genesis (10 tickers, 1k monkeys, 90d warmup)
python scripts/bootstrap_genesis.py --start-date 2026-05-15 --n-monkeys 1000 --universe-size 10 --warmup-days 90 --force
# Run a tick
python scripts/run_tick.py --date 2026-05-18
# Test re-run is byte-identical
python scripts/run_tick.py --date 2026-05-18 --force
# All tests
python -m pip install -r requirements-dev.txt
python -m pytest tests/ -v
```

### Production deploy (sketch)

On openclaw:
```bash
git clone <repo> ~/monkey-vs-machine && cd ~/monkey-vs-machine
sudo bash deploy/openclaw/install.sh
sudo nano /etc/openclaw/secrets.env   # PAGES_URL, MVM_INGEST_TOKEN
sudo -u mvm /opt/mvm/.venv/bin/python /opt/mvm/scripts/bootstrap_genesis.py --start-date $(date -u +%Y-%m-%d)
```

On the dashboard side:
```bash
cd dashboard
wrangler d1 create mvm-prod    # capture the ID, paste into wrangler.toml
wrangler d1 execute mvm-prod --file=migrations/0001_init.sql
bun install
bun run deploy
wrangler pages secret put MVM_INGEST_TOKEN   # same value as in /etc/openclaw/secrets.env
```

See `deploy/openclaw/README.md` for the full operational runbook, including a
documented v1 gap: no SQLite backup is configured by default.

### Determinism contract (short version)

For a fixed `model_id` + fixed `runtime_fingerprint`, running `run_tick(date=D)`
twice produces byte-identical rows. Cross-family equivalence is NOT promised
(swapping HistGBM for LightGBM creates a new `model_id`). Lockfile bumps mean
prior rows are still valid for forward simulation but bit-identical replay is
no longer guaranteed across the boundary. See [`DETERMINISM.md`](./DETERMINISM.md).
