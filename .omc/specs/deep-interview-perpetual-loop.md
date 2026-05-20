# Deep Interview Spec: Perpetual Monkey-vs-Machine

## Metadata
- Interview ID: perpetual-loop-2026-05-20
- Rounds: 5
- Final Ambiguity Score: 18.5%
- Type: brownfield
- Generated: 2026-05-20
- Threshold: 20%
- Status: PASSED

## Clarity Breakdown
| Dimension | Score | Weight | Weighted |
|---|---|---|---|
| Goal Clarity | 0.90 | 0.35 | 0.315 |
| Constraint Clarity | 0.85 | 0.25 | 0.213 |
| Success Criteria | 0.70 | 0.25 | 0.175 |
| Context Clarity | 0.75 | 0.15 | 0.113 |
| **Total Clarity** | | | **0.815** |
| **Ambiguity** | | | **0.185** |

## Topology

| Component | Status | Description | Coverage / Deferral Note |
|---|---|---|---|
| `scheduler` | active | Triggers one tick per day after US market close | Cron / systemd timer on openclaw |
| `persistent-state` | active | SQLite on openclaw holds full per-monkey + AI portfolio state day-over-day | Aggregates streamed to D1; full state local-only |
| `tick-execution` | active | One tick = fetch new bar, retrain AI, AI rebalances forward from current holdings, monkeys roll dice forward from current holdings, snapshot | Hybrid semantics: monkeys persist, AI model retrained, AI portfolio carries forward |
| `dashboard` | active | SvelteKit on Cloudflare Pages, reads from D1 via Pages Functions | Public read-only; AI vs SPY chart, monkey aggregates, 10 named monkey personalities |
| `real-broker-bridge` | **deferred** | Alpaca paper-trading mirror of the AI | Deferred from v1 by user — interfaces stubbed but not wired |

## Goal

Convert the existing `monkey-vs-machine` Python project from a one-shot experiment into a **perpetual living simulation** that runs once per trading day on a dedicated Linux box ("openclaw"), evolves persistent monkey + AI portfolios forward in time, and publishes a live read-only dashboard to a Cloudflare-hosted public website (SvelteKit + Pages + D1).

The system must produce, every trading day, the same dashboard surface refreshed with one new bar of evolution:
- AI portfolio equity vs SPY benchmark, full history since genesis
- Monkey pack aggregates (mean, median, 5/25/75/95 percentiles, count above SPY)
- 10 named monkey "characters" with continuous trade histories (top-3 lifetime, bottom-3 lifetime, 3 fixed genesis-picked personalities, today's biggest 1-day mover)
- AI's current holdings + feature importances for the latest retrain

## Constraints

- **Compute lives off Cloudflare.** Python+sklearn+yfinance run on the openclaw box, not Workers. Cloudflare hosts only the read-side (Pages + D1).
- **Cadence is one tick per trading day after US market close.** No intra-day ticks (daily bars don't update intra-day). AI is retrained every tick.
- **Persistence boundary**: full per-monkey state lives ONLY on openclaw (SQLite). D1 receives aggregates + the 10 named personalities only. D1 is treated as a publish target, not a system-of-record.
- **No data backfill from external news archives in v1.** Backtest sentiment remains price-derived (volume z-score, gap, abnormal return). Live yfinance + VADER sentiment continues to power the dashboard's "today's read" panel only.
- **No real money in v1.** The real-broker bridge component exists in the topology but its acceptance criteria are not in v1 scope.
- **Cost target**: < $5/month total. D1 free tier (5GB storage, 5M reads/day) is sufficient given aggregates-only egress.
- **State retention**: full daily history on openclaw indefinitely (rotate at 5-year mark with a rolling-window job, but not for v1). D1 retains all aggregates (small).
- **Genesis is one-shot.** Once the simulation starts, the 100k monkey identities are stable forever. The 3 genesis-picked personalities are chosen at genesis and never re-rolled.
- **Tick must be idempotent for a given date.** Re-running a tick for 2026-06-01 must produce the same state as the first run (deterministic monkey RNG seeded by `(monkey_id, date)`).

## Non-Goals (v1)

- Real-broker integration (Alpaca paper). Deferred to v2.
- Arbitrary monkey lookup by ID from the public dashboard. (Top-K only.)
- Intra-day data / sub-daily ticks. Daily bars only.
- Historical news / sentiment backfill from GDELT / Reddit / NewsAPI.
- Multiple competing AI variants ("model league"). Single AI in v1.
- Survivorship bias correction (still uses current S&P 500 constituents).
- Auth on the public dashboard. Read-only, anyone can view.
- Mobile-first design. Desktop is acceptable for v1.

## Acceptance Criteria

- [ ] One tick runs end-to-end on openclaw in < 5 minutes wall-clock (fetch yfinance → retrain AI → simulate monkeys → snapshot → push aggregates to D1).
- [ ] Tick is idempotent: running the same date twice produces identical SQLite state and identical D1 rows.
- [ ] SQLite schema has tables: `prices`, `monkeys` (current state), `monkey_history` (daily snapshots), `ai_model_history`, `ai_portfolio_history`, `ticks` (run log).
- [ ] D1 schema has tables: `daily_aggregates`, `ai_history`, `ai_holdings_current`, `named_monkeys`, `named_monkey_history`, `tick_log`.
- [ ] systemd timer (or cron) fires the tick at 06:00 AEST daily; failed tick alerts to a log file.
- [ ] An egress script pushes aggregates to D1 over HTTPS using a scoped API token; secrets live in `/etc/openclaw/secrets.env`, NEVER committed.
- [ ] SvelteKit dashboard at `monkeys.nickwfraser.dev` (or similar) deploys to Cloudflare Pages.
- [ ] Dashboard renders 4 tabs: Race, Aggregates, Named Monkeys, AI Internals.
- [ ] Each tab reads D1 via a Pages Function and renders within 1s on a cold load.
- [ ] Bootstrap script can wipe openclaw state and re-bootstrap a fresh genesis from a configurable start date with a single command.
- [ ] Genesis monkeys' RNG seed is reproducible: rebuilding the same genesis date produces the same 100k monkeys.
- [ ] Real-broker bridge interface is stubbed (`mvm/broker/base.py` with `submit_order`, `get_positions`, `get_account`) but unwired; passing test confirms the interface exists.
- [ ] README documents how to spin up the box, run a tick manually, deploy the dashboard, and rotate D1 tokens.

## Assumptions Exposed & Resolved

| Assumption | Challenge | Resolution |
|---|---|---|
| "Perpetual" means episodic re-runs | Hybrid mode picked: monkeys carry forward, AI retrained | Real simulation forward in time |
| Multiple ticks/day adds signal | Daily bars don't update intra-day | One tick/day after US close |
| Cloudflare hosts compute | Python+sklearn can't live on Workers | Compute on openclaw, CF hosts publish/read |
| All 100k portfolios are public | Cost + UX cost of arbitrary lookup | Aggregates + 10 named monkeys only |
| Real-broker is v1 scope | "For fun" + cost-conscious | Stubbed interface, deferred actual wiring |
| Need historical news data | yfinance archive doesn't exist | Use price-derived proxies; live news for "today" tab only |

## Technical Context

Brownfield. Existing code at `D:\claudecode\monkey-vs-machine`:
- `src/mvm/data/{prices,news,sentiment,universe}.py` — yfinance + parquet cache + VADER + S&P-500 fallback list
- `src/mvm/backtest/{engine,metrics}.py` — weight-driven backtest, CAGR/Sharpe/maxDD/turnover
- `src/mvm/models/{monkey,ai_trader}.py` — numpy-vectorized 100k monkeys, walk-forward HistGradientBoostingClassifier
- `src/mvm/features.py` — RSI/MACD/momentum/vol/volume-z/abnormal-return
- `src/mvm/runner.py` — orchestrator
- `app/dashboard.py` — Streamlit (will be supplanted by the SvelteKit public dashboard but kept for local diagnostics)

**Reusable as-is**: features, backtest engine, monkey numpy core, AI trainer.
**Needs replacement / addition**: runner (now becomes a "tick" runner with persistent state), Streamlit (kept local; new SvelteKit dashboard for public), data layer (parquet still fine for prices, new SQLite schema for portfolios).

## Ontology (Key Entities)

| Entity | Type | Fields | Relationships |
|---|---|---|---|
| Tick | core | tick_id, date, started_at, finished_at, ai_train_score, n_monkeys, status | snapshots N Monkey, 1 AIModel; logs 1 TickEvent |
| Monkey | core | monkey_id, cash, position_ticker, shares, genesis_date, rng_seed | has many MonkeyDailySnapshot |
| MonkeyDailySnapshot | core | monkey_id, date, equity, position_ticker, shares, cash, action_today | belongs to Monkey, belongs to Tick |
| AIModel | core | model_id, trained_at, feature_importances, hyperparams | has many AIPrediction; belongs to Tick |
| AIHolding | core | ticker, weight, target_weight, last_rebalance_date | belongs to AIModel |
| NamedMonkey | core | name, monkey_id, category (top/bottom/personality/mover), pinned_at | belongs to Monkey |
| Aggregate | core | date, mean, median, p5, p25, p75, p95, n_beating_spy, ai_equity, spy_equity | belongs to Tick |
| BrokerInterface | external (stubbed) | submit_order, get_positions, get_account | future binding to Alpaca paper |

## Ontology Convergence

| Round | Entities | New | Changed | Stable | Stability |
|---|---|---|---|---|---|
| 0 | 5 | 5 | – | – | – |
| 1 | 6 | 1 | – | 5 | 83% |
| 2 | 6 | 0 | – | 6 | 100% |
| 3 | 7 | 1 (NamedMonkey) | – | 6 | 86% |
| 4 | 8 | 1 (Tick) | – | 7 | 88% |
| 5 | 8 | 0 | – | 8 | 100% |

Ontology converged by Round 5.

## Implementation Sketch (informational)

1. **State layer** — `src/mvm/state/` new module: `sqlite.py` (genesis bootstrap, tick read/write, snapshot writer), `d1_client.py` (egress over HTTPS to a Cloudflare Pages-Function `/admin/ingest` endpoint with bearer auth), `schema.sql`.
2. **Tick runner** — `scripts/run_tick.py`: idempotent per-date. Steps: fetch bar → retrain AI on history-to-date → rebalance AI from current holdings → roll monkey dice → write SQLite snapshot → push aggregates to D1.
3. **Genesis** — `scripts/bootstrap.py`: one-shot create of 100k monkeys with `rng_seed = hash(monkey_id, "genesis-2026-05-20")`, initial $10,000 each, pick 3 personality monkeys, seed first SQLite + D1 rows.
4. **Scheduler** — `deploy/openclaw/mvm-tick.timer` + `mvm-tick.service` (systemd). Logs to `/var/log/mvm/tick-YYYY-MM-DD.log`.
5. **Public dashboard** — separate SvelteKit project (`dashboard-svelte/` or new sibling repo): `routes/+page.svelte` (race), `routes/aggregates`, `routes/monkeys/[name]`, `routes/ai`. Server endpoints call D1 via the Pages-Functions binding. Deploy to `monkeys.nickwfraser.dev` (CNAME → CF Pages).
6. **Broker stub** — `src/mvm/broker/{base.py,alpaca.py}` — base abstract class, alpaca raises NotImplementedError. v2 will fill in.

## Interview Transcript
<details>
<summary>5 rounds</summary>

**Round 0 — Topology confirmation**
Q: Is this 4-component topology (scheduler / persistent state / tick execution / dashboard) right?
A: Add a 5th: real-broker bridge.

**Round 1 — Tick semantics (Goal)**
Q: When a tick fires, what happens to monkey #42's portfolio?
A: Hybrid: monkeys persist with continuous histories; AI gets retrained; AI portfolio carries forward.

**Round 2 — Hosting (Constraints)**
Q: Where should this run perpetually, given Python+sklearn can't live on Cloudflare Workers?
A: Build for a separate openclaw box; data flows off it to a Cloudflare-hosted website.

**Round 3 — Done feels like (Success Criteria)**
Q: What's the moment that makes v1 feel "done"?
A: Live leaderboard + AI vs market chart + average of all monkeys + a few outliers shown. (Real-broker, arbitrary lookup, model-evolution rejected for v1.)

**Round 4 — Cadence (Goal)**
Q: How often should a tick fire, given the daily-bar data constraint?
A: One tick daily, AI retrains after each day.

**Round 5 — Persistence + egress (Constraints)**
Q: What persists on the openclaw box vs what flows out to Cloudflare?
A: Full state local, aggregates only to D1.

Settled by default (not asked): dashboard tech = SvelteKit on CF Pages reading D1. "Outliers" = 10 named monkeys (top-3 + bottom-3 + 3 personalities + today's mover).
</details>

## Status: pending approval

Awaiting explicit execution approval. Recommended next step: `/oh-my-claudecode:plan --consensus --direct` to run Planner / Architect / Critic over this spec before any code is written.
