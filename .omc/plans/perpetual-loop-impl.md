# Plan: Perpetual Monkey-vs-Machine

**Status**: pending approval — consensus reached on iteration 2; council-folded as v2.2
**Spec**: `.omc/specs/deep-interview-perpetual-loop.md`
**Mode**: RALPLAN-DR short
**Reviewers**: Architect (APPROVE iter 2), Critic (APPROVE iter 2), LLM Council (5 advisors + chairman, see `.omc/council/council-report-2026-05-20-1715.html`)

## Requirements Summary

Convert the existing one-shot `monkey-vs-machine` experiment into a perpetual simulation that:
- Runs one tick per US-trading-day after market close on an external "openclaw" Linux box.
- Persists per-monkey + AI portfolio state in SQLite on openclaw (full state local).
- Egresses small aggregates + 10 named-monkey histories to Cloudflare D1.
- Publishes a public read-only SvelteKit dashboard on Cloudflare Pages.
- Stubs (but does NOT wire) an Alpaca paper-broker interface for v2.

## RALPLAN-DR Summary

### Principles
1. **Compute lives off Cloudflare**. Python+sklearn run on openclaw; Cloudflare hosts publish/read only.
2. **SQLite is system-of-record**. D1 is a publish surface, rebuildable from SQLite at any time. Never read D1 to write SQLite.
3. **Ticks are idempotent and reproducible given identical input bars**. Prices are persisted to SQLite on first fetch; re-runs read from `prices` not yfinance. RNG seeded by `(monkey_id, date)` for monkeys, `("ai_train", date)` for the classifier.
4. **Genesis is one-shot and persisted**. Genesis date + RNG seed string live in a `genesis_log` row; reproducible re-bootstrap reads from that row, not from a literal in code.
5. **No secret leaves openclaw without an explicit egress**. Broker creds (when added) and D1 ingest tokens live in `/etc/openclaw/secrets.env` mode 0600; rotation is a one-command script.
6. **AI is a swappable family of models, not a fixed algorithm.** Every persisted AI row carries a `model_id` and a `runtime_fingerprint`. The determinism contract is *per-`model_id`* + *per-`runtime_fingerprint`*, not cross-family. Library swaps (LightGBM, XGBoost, NN, stacking) require a new `model_id`; lockfile bumps mean the old rows are still valid for forward simulation but no longer guaranteed bit-identical on replay. (Council, 2026-05-20.)

### Decision Drivers
1. **Cost ceiling < $5/month** — favours D1 free tier + Pages free tier; rules out always-on VPS for compute (openclaw is user-owned hardware).
2. **One developer, "for fun" project** — favours minimal moving parts, hand-runnable scripts, reversible decisions, narrow blast radius.
3. **Auditable evolution** — every tick produces a row in `ticks`; failures leave SQLite in pre-tick state via single-writer transaction.

### Viable Options (snapshot storage)

**Option A — Row-per-monkey-per-day in SQLite (recommended)**
- 100k rows × ~250 trading days/yr ≈ 25M rows/yr in `monkey_history`. Disk ≈ ~1 GB/yr (measured after first 30 ticks; estimate revised down from 2 GB after architect review).
- Pros: queryable with plain SQL; one storage system; trivial backup (rsync the .db); `ON CONFLICT DO UPDATE` makes idempotency explicit without FK cascade surprises.
- Cons: 100k INSERTs/tick — must batch via single `executemany` inside one transaction.

**Option B — SQLite for headline + Parquet snapshot per tick**
- Pros: smaller SQLite (<100 MB/yr); columnar parquet ideal for archival.
- Cons: two storage systems to keep in sync; ad-hoc queries need DuckDB. Architect flagged this is *not* strawmanned — DuckDB-over-parquet IS ad-hoc queryable; the real trade-off is "two stores vs one."
- Invalidation: one-developer principle favours single store; we accept the disk cost in trade.

**Option C — Compressed blob per tick in SQLite**
- Invalidated: opaque blob forecloses future per-monkey drill-in and provides no idempotency benefit over Option A with `ON CONFLICT`.

**Decision: Option A**, with explicit acceptance that disk cost dominates over query convenience for v1.

### Viable Options (D1 publish schema)

**Option A — Structured tables mirroring SQLite publish surface (recommended)**
- 6 D1 tables: `daily_aggregates`, `ai_history`, `ai_holdings_current`, `named_monkeys`, `named_monkey_history`, `tick_log`.
- Pros: idiomatic SQL queries in SvelteKit; columns are typed.
- Cons: schema must be kept in lockstep between SQLite and D1.

**Option B — Collapse to one `publish_rows(date, kind, payload_json)` table**
- Pros: one schema to evolve; dashboard parses JSON server-side.
- Cons: dashboard loses column-level SQL filtering; column drift hides instead of being typed.
- Invalidation: small dashboard surface; structured wins for query clarity at the cost of one extra schema-mirror discipline.

**Decision: Option A** with a `publish_schema_version` row written by every tick so drift between SQLite and D1 schemas is detectable in the log.

### Viable Options (D1 egress mechanism)

**Option A — openclaw POSTs to Pages Function `/admin/ingest` with bearer token (recommended)**
- Pros: function-scoped token (smaller blast radius than account-wide), Pages binding to D1 is native, ingest can dedupe/log.
**Option B — D1 HTTP API direct write from openclaw**
- Invalidation: account-scoped token blast radius is too large for "for fun" project hygiene.

**Decision: Option A.**

### Viable Options (dashboard data fetching)

**Option A — SvelteKit `+page.server.ts` server-load via D1 binding (recommended)**
- Pros: SSR first paint with real data; D1 never exposed client-side; matches Tally/GoCard pattern.
- Cons: every navigation hits a Pages Function (~50ms cold). Mitigated by Pages Function caching (`cache: { ttl: 60 }` on read endpoints since data only changes once/day).

**Decision: Option A** with per-route 60-second Pages cache so multiple visitors don't re-hit D1 within the same minute.

## Acceptance Criteria

- [ ] **A1**: `python scripts/bootstrap_genesis.py --start-date 2026-05-20 --n-monkeys 100000` creates `data/state.db`, populates 100k monkey rows with deterministic seeds, picks 3 personality monkey_ids via seeded shuffle of `range(n_monkeys)`, writes one `genesis_log` row whose `seed_string` literal is then read by all later RNG calls. Second invocation refuses unless `--force` and aborts with exit 2.
- [ ] **A2**: `python scripts/run_tick.py --date 2026-05-21` runs end-to-end and writes one new row to `ticks` with `status='ok'`. **Methodology**: timing is measured by the script itself (`time.perf_counter` from start to end of `runner_tick.run`), logged as `ticks.duration_seconds`. Initial soft target: median of first 10 measured tick durations < 300 s on the user's openclaw box; documented in `deploy/openclaw/PERF.md` as the realised baseline. No fixed wall-clock SLA.
- [ ] **A3**: Re-running `run_tick.py --date 2026-05-21` produces an identical set of new rows: `SELECT COUNT(*) FROM monkey_history WHERE date='2026-05-21'` returns exactly 100000; per-row equity values are byte-identical. **Idempotency boundary**: this holds *given identical input prices*. Prices are persisted to `prices` table on first fetch (`runner_tick` uses `UPSERT`); the second run reads from `prices`, not from yfinance.
- [ ] **A4**: SQLite schema includes: `tickers`, `prices`, `monkeys`, `monkey_history`, `ai_model_history`, `ai_portfolio_history`, `named_monkeys`, `named_monkey_history`, `ticks`, `genesis_log`, `d1_egress_log`. Every `*_history` table uses `INSERT ... ON CONFLICT(...) DO UPDATE` write semantics (no `OR REPLACE`). **AI tables are model-keyed (council-folded v2.2)**: `ai_model_history` PK is `(date, model_id)` with columns `model_id TEXT NOT NULL DEFAULT 'hgb_v1'`, `model_family TEXT NOT NULL DEFAULT 'sklearn_hgb'`, `config_json TEXT NOT NULL DEFAULT '{}'`, `diagnostics_json TEXT NOT NULL DEFAULT '{}'`, `runtime_fingerprint TEXT NOT NULL DEFAULT '{}'`, `features_hash TEXT NOT NULL DEFAULT ''`, `train_window_end TEXT NOT NULL DEFAULT ''`, `training_seconds REAL`. The typed columns `feature_importances`, `hyperparams`, `train_score` are NOT in the schema — their data lives inside `config_json` / `diagnostics_json`. `ai_portfolio_history` PK is `(date, ticker, model_id)` with `model_id TEXT NOT NULL DEFAULT 'hgb_v1'`. There is NO `ai_holdings_current` VIEW (council recommendation: a view that silently picks one model is a footgun once a league exists); current holdings are exposed via a parameterised query `get_ai_holdings(model_id, as_of_date)` in `state/snapshots.py`.
- [ ] **A5**: `python scripts/push_to_d1.py --date 2026-05-21` posts JSON to `${PAGES_URL}/admin/ingest` with `Authorization: Bearer ${MVM_INGEST_TOKEN}`; on 200 it writes a success row to `d1_egress_log`. Payload is at most ~150 KB (10 named-monkey rows + 1 aggregate row + 1 AI row + 10 holdings rows + 1 tick log row; well under Pages 100 MB limit). Failure is retried with exponential backoff up to 5 attempts; final failure writes `status='failed'` to `d1_egress_log` and exits non-zero.
- [ ] **A6**: D1 schema includes `daily_aggregates`, `ai_history`, `ai_holdings_current`, `named_monkeys`, `named_monkey_history`, `tick_log`, `publish_schema_version`. Projected total D1 storage at 5 years < 50 MB (one row/day × 6 small tables; named_monkey_history bounded at 10 monkeys × ~1250 trading days × 5 yr = 12.5k rows). Documented `publish_schema_version` value lives in `dashboard/migrations/0001_init.sql`.
- [ ] **A7**: systemd timer `mvm-tick.timer` with `Timezone=Australia/Sydney` and `OnCalendar=06:00` fires daily; `mvm-tick.service` runs `run_tick.py` then `push_to_d1.py`. Non-trading-day handling: tick runs unconditionally; if `prices` table gets no new row for that date (US holiday / weekend), `run_tick.py` exits with status `skipped` writing `ticks.status='skipped_no_bar'`. Output appended to `/var/log/mvm/tick-YYYY-MM-DD.log`. systemd `OnFailure=` invokes `mvm-tick-alert.service` which appends an `alert` line to journal.
- [ ] **A8**: SvelteKit project under `dashboard/` deploys to Cloudflare Pages with D1 binding `DB`. Four routes render with non-empty content from real D1 rows: `/` (race chart + `last_tick_at` panel sourced from `tick_log`), `/aggregates` (percentile bands + count beating SPY), `/monkeys` (10 named-monkey sparklines), `/ai` (current holdings table + feature-importance bar chart + retrain log). **Methodology**: load time measured as median of 5 cold-cache loads from Sydney via `curl -w '%{time_total}\n' https://${URL}/{route}`; documented in `dashboard/PERF.md`. No fixed SLA — record realised numbers.
- [ ] **A9**: `src/mvm/broker/base.py` defines abstract `Broker` with `submit_order(symbol, qty, side)`, `get_positions()`, `get_account()`. `src/mvm/broker/alpaca.py` implements the class; every method raises `NotImplementedError("Alpaca wiring is v2")`. `pytest tests/test_broker_interface.py` asserts class shape and that every method raises.
- [ ] **A10**: Root README adds a "Perpetual mode" section covering: openclaw provisioning checklist, manual tick command, deploy command, D1 token rotation procedure, catch-up procedure after multi-day outage, "what to do when an AI retrain fails" runbook.
- [ ] **A11**: A failed `run_tick.py` (any exception inside the SQLite transaction) leaves SQLite in pre-tick state (transactional rollback via `BEGIN IMMEDIATE` / `COMMIT` / explicit `ROLLBACK` on exception) and exits non-zero. `ticks.status='failed'` row is written *after* the rolled-back transaction, in a separate small transaction. **Scope note**: this covers `run_tick.py` only. `push_to_d1.py` is a separate process with its own retry/backoff (A5); a successful tick that fails to egress leaves SQLite committed and `d1_egress_log` records the failure — the next push retries from the same SQLite source of truth.
- [ ] **A12**: All RNG draws within a tick use `numpy.random.default_rng(seed=hash_seed("monkey", monkey_id, date))` for monkeys. AI builders receive `hash_seed("ai_train", model_id, date)` as their seed argument — every model family decides how to apply it (HistGBM passes it to `random_state`; LightGBM to `seed`; PyTorch sets `torch.manual_seed`). `hash_seed` is `int.from_bytes(hashlib.sha256(f"{seed_string}:{args}".encode()).digest()[:8], "big")` using the genesis `seed_string`. **Determinism scope (council-folded v2.2)**: bit-identical reruns are guaranteed *per `model_id`* *per `runtime_fingerprint`* given identical input prices — not cross-family, not across lockfile bumps. See `DETERMINISM.md`.
- [ ] **A13**: `python scripts/catchup.py --since 2026-05-21` re-runs ticks for every missing date between `since` and yesterday (US market timezone). For each missing date: fetch bar, run tick, push to D1. Stops on first failure with clear exit code. Idempotent — re-running with the same `--since` does nothing if all ticks already exist.
- [ ] **A14**: `python scripts/rebuild_d1.py --since 2026-05-21` replays the egress payload for every tick in SQLite from that date forward. Used when D1 has been wiped or schema has been re-migrated.
- [ ] **A15**: `deploy/openclaw/rotate_d1_token.sh` is a one-command rotation: prompts for new token, updates `/etc/openclaw/secrets.env`, restarts `mvm-tick.timer`, sends one test ingest to confirm the new token works.
- [ ] **A16**: AI warmup: bootstrap ingests historical prices from `start_date - DEFAULT_WARMUP_DAYS` (set to 180) so the AI has enough history to train on day 1. `bootstrap_genesis.py --start-date X` thus fetches bars from `X-180d` to `X` and writes them to `prices`. Tick day 1 starts with a trainable model. Documented in `genesis_log.warmup_days`.
- [ ] **A17**: `data/state.db`, `data/state.db-wal`, `data/state.db-shm`, `/etc/openclaw/`, `**/.env` are added to `.gitignore`. CI test asserts these patterns are present.
- [ ] **A18** (council-folded v2.2): `src/mvm/models/registry.py` exposes `MODELS: dict[str, Callable[[], ModelBuilder]]` with exactly one entry in v1: `{"hgb_v1": build_hgb_v1}`. A `ModelBuilder` is a duck-typed object exposing `.fit(X: ndarray, y: ndarray, seed: int) -> dict` (returns diagnostics) and `.predict_proba(X: ndarray) -> ndarray`. No ABC, no plugin loader, no YAML. Adding model #2 is one new entry in the dict; nothing else changes.
- [ ] **A19** (council-folded v2.2): `src/mvm/runtime_fingerprint.py` exposes `runtime_fingerprint() -> dict` returning a JSON-serialisable map with keys `python`, `numpy`, `sklearn`, `pandas`, `pyarrow`, `lockfile_sha256`, `blas`, `threads`. `lockfile_sha256` is SHA256 of `requirements.txt` after stripping comments + whitespace. Called once per tick per model, stored in `ai_model_history.runtime_fingerprint`.
- [ ] **A20** (council-folded v2.2): `tests/test_determinism.py` runs the tick for a fixed date D twice in one process, snapshotting state between runs, and asserts: (a) byte-identical `monkey_history` rows for D; (b) byte-identical `ai_portfolio_history.weight` for D for every `model_id`; (c) `diagnostics_json` after hashing is identical. Test runs in CI. If the test fails on the current code at any point, no AI schema change ships until it passes — the determinism contract must be tested before extended.
- [ ] **A21** (council-folded v2.2): `DETERMINISM.md` at project root documents the contract in <= 200 words: scoped per `model_id` and per `runtime_fingerprint`; lockfile bumps invalidate prior rows for replay (not forward simulation); adding a new family creates a new `model_id`, never reuses an existing one; cross-family equivalence is explicitly NOT promised.

## Implementation Steps

### Phase 1 — State + Genesis
1. **`src/mvm/state/schema.sql`** — full DDL for the 10 tables + 1 view. `PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL; PRAGMA foreign_keys=ON`. Every `*_history` table uses `PRIMARY KEY(date, <id>)`. `ai_holdings_current` is a VIEW.
2. **`src/mvm/state/db.py`** — `get_conn(path)` opens with WAL + sets pragmas + acquires a filesystem `fcntl.flock` on `{path}.lock` for the lifetime of the connection (single-writer enforcement, not just social contract).
3. **`src/mvm/state/hash_seed.py`** — `hash_seed(*args, seed_string)` returning uint64 from SHA256. Used by both monkey RNG and AI `random_state`.
4. **`scripts/bootstrap_genesis.py`** — accepts `--start-date`, `--n-monkeys`, `--seed-string` (default `"mvm-genesis-{start_date}"`), `--warmup-days` (default 180). Creates DB, inserts 100k monkeys with deterministic seeds, picks 3 personality monkeys by seeded shuffle of monkey IDs, writes `genesis_log(start_date, seed_string, warmup_days, n_monkeys, personality_monkey_ids)`, fetches and stores warmup prices.
5. **Update `requirements.txt` / `pyproject.toml`** — pin numpy, scikit-learn, yfinance, pandas to exact versions; add `pyarrow` to runtime deps (already present); document the pin rationale in a `## Pinned-for-determinism` comment in requirements.txt.
6. **Update `.gitignore`** — append the patterns from A17.
7. **Tests**: `tests/test_genesis.py` — assert idempotency (re-running with `--force` produces identical row hashes), row counts, RNG seed reproducibility, warmup price count.

### Phase 2 — Tick runner (depends on Phase 1)
8. **Refactor `src/mvm/models/monkey.py`** — extract three things in order:
   - **8a**: `step_monkeys_one_day(prices_today_array, cash, shares, pos, rng) -> (cash, shares, pos)` — pure per-day stepper, no side effects, mutates passed-in arrays. Returns same arrays for chainability.
   - **8b**: keep `simulate_monkeys` (the batch 5-year entrypoint) but reimplement it as a loop calling `step_monkeys_one_day`, plus the existing snapshot/percentile accumulators. Local Streamlit continues to work unchanged.
   - **8c**: snapshot logic (`percentile_history`, `top_equity_history`) moves into the batch function only; per-day stepper exposes raw arrays. The tick runner writes its own snapshots via `state/snapshots.py`.
9. **Refactor `src/mvm/models/ai_trader.py`** + introduce the registry (council-folded v2.2):
   - **9a**: Add `src/mvm/models/registry.py` with `MODELS = {"hgb_v1": build_hgb_v1}`. `build_hgb_v1` returns an object exposing `.fit(X, y, seed) -> diagnostics_dict` and `.predict_proba(X) -> ndarray`. Diagnostics dict has free-form keys (e.g. `feature_importances`, `train_score`, `model_family`); whatever the family naturally produces.
   - **9b**: Rewrite `ai_trader.py` so the existing `HistGradientBoostingClassifier` lives inside `build_hgb_v1` (no other call sites name the algorithm). Extract `predict_ranking(model, features_today)` and `apply_rebalance(current_holdings_dict, ranking_series, top_k) -> (new_holdings_dict, turnover_float)` as pure functions independent of the family.
   - **9c**: Add `src/mvm/runtime_fingerprint.py` exposing `runtime_fingerprint()` per A19.
   - **9d**: Add `src/mvm/state/features_hash.py` exposing `features_hash(features_df) -> str` (SHA256 of the canonicalised feature matrix per A4 schema requirement).
10. **`src/mvm/state/snapshots.py`** — `write_monkey_snapshot(conn, date, cash, shares, pos, rng_step_count)`, `write_ai_snapshot(conn, date, holdings, model_meta_dict, random_state)`, `write_aggregates(conn, date, monkey_equity_array, ai_equity, spy_equity)`. All `INSERT ... ON CONFLICT(date, ...) DO UPDATE`.
11. **`src/mvm/runner_tick.py`** — orchestrates one tick across two transactions. **Tx 1 (prices)**: fetch yesterday's-or-given bar, upsert into `prices` in its own small `BEGIN`/`COMMIT`. If no row available, write `ticks.status='skipped_no_bar'` and exit code 3 — no simulation tx is ever opened. **Tx 2 (simulation, BEGIN IMMEDIATE)**: (a) load yesterday's monkey + AI state. (b) build features for history-to-date; compute `features_hash`. (c) capture `runtime_fingerprint()` once for this tick. (d) **For each `(model_id, builder)` in `registry.MODELS.items()`** (council-folded v2.2): instantiate the builder, call `.fit(X_train, y_train, seed=hash_seed("ai_train", model_id, date))` measuring `training_seconds`, call `.predict_proba(X_today)` to get rankings, `apply_rebalance(current_holdings[model_id], ranking, AI_TOP_K)` (constant pinned at module top: `AI_TOP_K = 10`), write a row to `ai_model_history(date, model_id, model_family, config_json, diagnostics_json, runtime_fingerprint, features_hash, train_window_end, training_seconds)` and per-ticker rows to `ai_portfolio_history(date, ticker, model_id, weight)`. (e) step monkeys forward one day. (f) compute aggregates (using the "champion" `model_id` from config). (g) write monkey snapshots + refresh named-monkey selections. (h) write `ticks` row with `status='ok'`, COMMIT. Any exception inside Tx 2 → ROLLBACK → write `ticks.status='failed'` row in a new tiny transaction → re-raise. Splitting prices into its own tx makes the "skipped" path naturally idempotent. The v1 loop trivially has `len(MODELS) == 1`; the structural loop is what makes adding model #2 free.
12. **`scripts/run_tick.py`** — CLI: `--date YYYY-MM-DD` (defaults to today in US/Eastern). Exit codes: 0 ok, 2 already-ran (no `--force`), 3 skipped (no bar), 1 failure.
13. **Named-monkey refresh logic** (called inside step 11g):
    - **Personality monkeys**: 3 picked at genesis, fixed forever.
    - **Top-3 lifetime**: re-evaluated each tick = top 3 by current equity (`monkeys.equity` column).
    - **Bottom-3 lifetime**: same, bottom 3 by equity.
    - **Today's biggest mover**: monkey with max `|equity_today - equity_yesterday|`.
    - `named_monkeys` rows are rewritten each tick; `named_monkey_history` rows are appended (so a monkey that drops out of top-3 keeps its history rows).
14. **Tests**:
    - `tests/test_tick_idempotency.py` — run tick twice with same input prices, assert identical row hashes for the new rows.
    - `tests/test_step_monkeys.py` — pure stepper with fixed inputs gives same outputs across runs.
    - `tests/test_runner_tick_skip.py` — call with a date that has no bar; assert `status='skipped_no_bar'` and no monkey_history rows.
    - `tests/test_determinism.py` (council-folded v2.2, per A20) — runs the full tick for date D twice in one process; snapshots state between runs; asserts byte-identical `monkey_history` rows for D, byte-identical `ai_portfolio_history.weight` per `model_id`, and SHA256-identical `diagnostics_json`. **This test gates all AI schema changes**: if it fails on current code, the council-recommended schema migration does not ship until the underlying determinism is real.
    - `tests/test_registry_shape.py` — asserts every `MODELS[id]()` returned object exposes `.fit(X, y, seed)` and `.predict_proba(X)` (per A18).
14a. **`DETERMINISM.md`** at project root (council-folded v2.2, per A21) — <= 200 words documenting the per-`model_id` + per-`runtime_fingerprint` scope; lockfile bumps; "new family = new `model_id`, never reuse"; cross-family equivalence not promised.

### Phase 3 — D1 egress (depends on Phase 2)
15. **`dashboard/migrations/0001_init.sql`** — D1 DDL. Includes `publish_schema_version` row with value `1`.
16. **`dashboard/functions/admin/ingest.ts`** — Pages Function. POST handler validates `Authorization: Bearer ${env.MVM_INGEST_TOKEN}` (constant-time compare), parses JSON, asserts `payload.publish_schema_version === env.PUBLISH_SCHEMA_VERSION` else 409, writes all rows via `env.DB.batch()` with `INSERT OR REPLACE`. Logs to `tick_log`. (Asymmetry note: SQLite side uses `ON CONFLICT DO UPDATE` to avoid FK cascades; D1 side uses `INSERT OR REPLACE` because the publish schema is FK-free and `OR REPLACE` is idiomatic in the Workers+D1 ecosystem. The 0001_init.sql migration carries a comment explaining this.)
17. **`scripts/push_to_d1.py`** — reads pushable rows for given date from SQLite, builds JSON payload, POSTs with 5-retry exponential backoff. Records outcome in `d1_egress_log`.
18. **`scripts/rebuild_d1.py`** — walks `ticks` from `--since`, calls the same JSON-build path as `push_to_d1.py` for each date; idempotent on the receiving end via INSERT OR REPLACE.
19. **`scripts/catchup.py`** — walks every date from `--since` to yesterday US ET that's missing from `ticks`; for each missing date, calls `run_tick.py` then `push_to_d1.py`. Stops on first failure.
20. **Tests**:
    - `tests/test_egress_payload.py` — generate a fake tick's SQLite, build payload, assert shape matches the Pages-Function expected schema (parsed from `0001_init.sql` column list).
    - `tests/test_ingest_function.ts` — Vitest + Workers types; assert 401 on bad token, 409 on schema mismatch, 200 on valid payload.

### Phase 4 — Scheduler (depends on Phases 1-3)
21. **`deploy/openclaw/mvm-tick.service`** — `ExecStart=/opt/mvm/.venv/bin/python /opt/mvm/scripts/run_tick.py && /opt/mvm/.venv/bin/python /opt/mvm/scripts/push_to_d1.py`. `EnvironmentFile=/etc/openclaw/secrets.env`. `User=mvm`, `Group=mvm`. `Type=oneshot`. `TimeoutStartSec=900` (15 min hard cap).
22. **`deploy/openclaw/mvm-tick.timer`** — `OnCalendar=06:00`, `Timezone=Australia/Sydney`, `Persistent=true` (so a missed tick after reboot fires once on resume).
23. **`deploy/openclaw/mvm-tick-alert.service`** — `OnFailure=` target for the tick service; writes `journalctl -t mvm-alert "tick failed at $(date)"`.
24. **`deploy/openclaw/install.sh`** — copies units, creates `/var/log/mvm`, creates `mvm` user, prompts for D1 ingest token, writes `/etc/openclaw/secrets.env` mode 0600, runs `systemctl daemon-reload` + `systemctl enable --now mvm-tick.timer`.
25. **`deploy/openclaw/rotate_d1_token.sh`** — implementing A15.
26. **`deploy/openclaw/PERF.md`** — placeholder; populated after first 10 ticks with measured baseline.
27. **`deploy/openclaw/README.md`** — provisioning checklist (Python 3.11+, systemd, journald, log rotation via `/etc/logrotate.d/mvm`, firewall: outbound HTTPS to `query1.finance.yahoo.com`, `query2.finance.yahoo.com`, and the Pages domain only). **Includes an explicit SPOF disclaimer**: "v1 has no SQLite backup. A drive failure between tick N and the next D1 push permanently loses the SQLite source of truth — D1 publish surface omits the 100k×daily monkey detail, so it can rebuild D1 but not SQLite. Before treating this system as durable, add an `mvm-backup.timer` rsync to a second box or NAS." (Architect-recommended.)

### Phase 5 — SvelteKit dashboard (depends on Phase 3 for live data, but scaffolding can start in parallel)
28. **Scaffold `dashboard/`** — use the current Cloudflare SvelteKit template (`bun create cloudflare@latest dashboard -- --framework=svelte --type=skeleton`). Verify the CLI flags against current release before pinning them in the README. Add `wrangler.toml` with `[[d1_databases]]` binding `DB`, database name `mvm-prod`.
29. **`dashboard/src/lib/server/d1.ts`** — typed queries (council v2.2: model-aware): `getRecentAggregates(days)`, `getAiHistory(days, modelId='hgb_v1')`, `getAiHoldings(modelId='hgb_v1')`, `getAiModelIds()` (returns the distinct list — used by the future league UI), `getNamedMonkeys()`, `getNamedMonkeyHistory(name)`, `getLastTickAt()`. All read-only. The `champion` `model_id` is a hard-coded constant in this file; switching champions in v2 is a one-line change.
30. **`dashboard/src/routes/+page.server.ts`** — race tab. Server-load fetches recent aggregates + AI history + last tick timestamp. Adds `setHeaders({ 'cache-control': 'public, max-age=60' })`.
31. **`dashboard/src/routes/aggregates/+page.server.ts`** — percentile bands.
32. **`dashboard/src/routes/monkeys/+page.server.ts`** — 10 named monkeys with sparklines.
33. **`dashboard/src/routes/monkeys/[name]/+page.server.ts`** — full history for one named monkey (sparkline is computed from `getNamedMonkeyHistory(name)`).
34. **`dashboard/src/routes/ai/+page.server.ts`** — AI's current holdings, feature importances, retrain log.
35. **`dashboard/PERF.md`** — placeholder, populated post-deploy.
36. **Deploy**: `bun run build && wrangler pages deploy .svelte-kit/cloudflare --project-name mvm-dashboard`. Initial deploy includes one `wrangler d1 execute mvm-prod --file=dashboard/migrations/0001_init.sql`.

### Phase 6 — Broker stub (independent)
37. **`src/mvm/broker/base.py`** — abstract base with three methods, return-type hints.
38. **`src/mvm/broker/alpaca.py`** — concrete subclass; every method raises `NotImplementedError("v2")`.
39. **`tests/test_broker_interface.py`** — assert class shape; assert every method raises NotImplementedError.

### Phase 7 — README + ops
40. **Update root `README.md`** — Perpetual mode section covering: bootstrap, manual tick, deploy, D1 token rotation, catchup, multi-day outage, retrain failure runbook. Sunset note for the existing Streamlit dashboard: kept for local diagnostics only.

## File References

| File | Purpose |
|---|---|
| `src/mvm/state/schema.sql` | SQLite DDL |
| `src/mvm/state/db.py` | Connection + flock + tx helper |
| `src/mvm/state/hash_seed.py` | Deterministic SHA256-based seeding |
| `src/mvm/state/snapshots.py` | Per-table ON CONFLICT writers + `get_ai_holdings(model_id, as_of_date)` |
| `src/mvm/state/features_hash.py` | Canonical SHA256 of feature matrix |
| `src/mvm/models/registry.py` | `MODELS` dict mapping `model_id` → builder (council v2.2) |
| `src/mvm/runtime_fingerprint.py` | Python/library/lockfile/BLAS fingerprint (council v2.2) |
| `src/mvm/runner_tick.py` | Orchestrates one tick, iterates `MODELS` |
| `DETERMINISM.md` | Per-`model_id` per-`runtime_fingerprint` contract (council v2.2) |
| `scripts/bootstrap_genesis.py` | Creates initial DB + warmup |
| `scripts/run_tick.py` | CLI tick runner |
| `scripts/catchup.py` | Catch up missing ticks |
| `scripts/push_to_d1.py` | Egress to CF |
| `scripts/rebuild_d1.py` | Replay all egress from SQLite |
| `dashboard/migrations/0001_init.sql` | D1 DDL |
| `dashboard/functions/admin/ingest.ts` | CF Pages Function ingest |
| `dashboard/src/lib/server/d1.ts` | D1 query layer |
| `dashboard/src/routes/+page.server.ts` | Race tab |
| `dashboard/src/routes/aggregates/+page.server.ts` | Aggregates tab |
| `dashboard/src/routes/monkeys/+page.server.ts` | Named monkeys list |
| `dashboard/src/routes/monkeys/[name]/+page.server.ts` | Named monkey detail |
| `dashboard/src/routes/ai/+page.server.ts` | AI internals |
| `deploy/openclaw/mvm-tick.{service,timer}` | systemd units |
| `deploy/openclaw/mvm-tick-alert.service` | Failure alert unit |
| `deploy/openclaw/install.sh` | Provisioning |
| `deploy/openclaw/rotate_d1_token.sh` | Token rotation |
| `deploy/openclaw/PERF.md` | Measured baseline |
| `deploy/openclaw/README.md` | Ops checklist |
| `dashboard/PERF.md` | Measured baseline |
| `src/mvm/broker/{base,alpaca}.py` | v2 stub |

## Risks and Mitigations

| # | Risk | Mitigation |
|---|---|---|
| R1 | SQLite grows ~1 GB/yr (revised from 2 GB after architect math) | Year-1 retro: add rolling VACUUM for `monkey_history` rows > 3 yr. Not v1. |
| R2 | yfinance API change or silent bar revision | Prices persisted on first fetch; idempotency is "given identical input prices" (A3). yfinance pinned in requirements.txt. |
| R3 | D1 ingest token leaked from openclaw | Pages-Function-scoped (not account-wide). `rotate_d1_token.sh` is one command (A15). `/etc/openclaw/secrets.env` mode 0600. |
| R4 | Concurrent tick runs corrupt SQLite | `fcntl.flock` in `db.get_conn` (enforced, not assumed). Second invocation blocks then sees existing row and exits with code 2. |
| R5 | RNG reproducibility breaks across numpy/sklearn versions | All deps pinned in requirements.txt with `## Pinned-for-determinism` comment. Seeds in `hash_seed` are SHA256-based (version-stable). |
| R6 | Survivorship bias drift as S&P 500 changes mid-run | Universe locked at genesis (stored in `genesis_log.universe_tickers`). v2 may add a universe-evolution policy. |
| R7 | Broker stub accidentally wired to real money | Every method raises NotImplementedError. CI runs `tests/test_broker_interface.py`. |
| R8 | Pages Function ingest endpoint abuse | Constant-time bearer compare; logs every call; one ingest/day expected, anything more flagged in `tick_log`. |
| R9 | systemd timer drifts vs DST | `Timezone=Australia/Sydney` handles DST. |
| R10 | First-deploy chicken-and-egg | `wrangler d1 execute mvm-prod --file=dashboard/migrations/0001_init.sql` is a documented step in the deploy README (step 36). |
| R11 | Multi-day openclaw outage causes permanent data gap | `scripts/catchup.py` (A13) backfills missing dates. systemd `Persistent=true` fires one tick on resume; catchup picks up the rest. |
| R12 | SQLite and D1 schemas drift | `publish_schema_version` row in both; ingest endpoint rejects mismatched payloads with 409 (step 16). |
| R13 | AI warmup gap (no training data on day 1) | A16: bootstrap fetches `--warmup-days` (180) of price history. |
| R14 | yfinance returns empty bar on US holidays | `run_tick.py` exits with `status='skipped_no_bar'` (A7); no rows written; catchup is a no-op. |
| R15 | Pages Function deploy changes ingest schema mid-flight | `publish_schema_version` mismatch returns 409; egress retries with backoff but ultimately fails noisily until openclaw is updated. Documented in README. |

## Verification Steps

1. **Genesis** (verifies A1, A16, A17):
   - `python scripts/bootstrap_genesis.py --start-date 2026-05-20`
   - `sqlite3 data/state.db "SELECT COUNT(*) FROM monkeys"` → 100000
   - `sqlite3 data/state.db "SELECT COUNT(*) FROM prices"` → ≥180×100 (warmup days × universe size)
   - `sqlite3 data/state.db "SELECT category, COUNT(*) FROM named_monkeys GROUP BY category"` → personality=3
   - `git status` shows no tracked db files.
2. **First tick** (verifies A2, A4, A12, A13, A18, A19 base case):
   - `python scripts/run_tick.py --date <last US trading day>`
   - `sqlite3 data/state.db "SELECT status, duration_seconds FROM ticks"` → ok, <some number>
   - `sqlite3 data/state.db "SELECT COUNT(*) FROM monkey_history"` → 100000
   - `sqlite3 data/state.db "SELECT model_id, training_seconds FROM ai_model_history WHERE date=<date>"` → 1 row, `hgb_v1`, real number
   - `sqlite3 data/state.db "SELECT model_id, COUNT(*) FROM ai_portfolio_history WHERE date=<date> GROUP BY model_id"` → 1 row, `hgb_v1`, 10
   - `sqlite3 data/state.db "SELECT json_extract(runtime_fingerprint, '$.python') FROM ai_model_history WHERE date=<date>"` → non-empty string
3. **Idempotency** (verifies A3):
   - Re-run the same date.
   - `sqlite3 data/state.db "SELECT COUNT(*) FROM monkey_history WHERE date=...""` → still 100000.
   - Diff a dump of rows before and after: byte-identical.
4. **Skip** (verifies A7's holiday path):
   - Run for a Sunday date. Expect exit code 3 and `ticks.status='skipped_no_bar'`.
5. **Egress** (verifies A5, A6):
   - Deploy Pages + run migration.
   - `python scripts/push_to_d1.py --date <test date>`
   - `wrangler d1 execute mvm-prod --command 'SELECT * FROM tick_log'` → 1 row.
6. **Catchup** (verifies A13):
   - Skip 3 days deliberately. `python scripts/catchup.py --since <skipped start>` → 3 new `ticks` rows + 3 new `d1_egress_log` rows.
7. **Dashboard** (verifies A8):
   - Visit deployed URL; all 4 tabs render with non-empty content from real rows.
   - `for i in 1 2 3 4 5; do curl -w '%{time_total}\n' -o /dev/null -s https://${URL}/; done` → log median in `dashboard/PERF.md`.
8. **Failure path** (verifies A11):
   - Inject a temporary `raise RuntimeError` inside `runner_tick`. Run tick. Confirm: no new `monkey_history` rows for that date; one `ticks` row with `status='failed'`. Revert.
9. **Broker shape** (verifies A9):
   - `pytest tests/test_broker_interface.py -v` → all pass.
9a. **Determinism + registry shape** (verifies A18, A20, A21, council v2.2):
    - `pytest tests/test_determinism.py -v` → passes (two tick runs of date D produce byte-identical snapshots).
    - `pytest tests/test_registry_shape.py -v` → passes (every `MODELS[id]()` exposes the duck-typed interface).
    - `cat DETERMINISM.md | wc -w` → ≤ 200.
10. **Token rotation** (verifies A15):
    - `deploy/openclaw/rotate_d1_token.sh`, accept a new dummy token, observe failed test ingest, restore real token, confirm tick resumes.
11. **D1 rebuild** (verifies A14):
    - `wrangler d1 execute mvm-prod --command 'DELETE FROM daily_aggregates'`
    - `python scripts/rebuild_d1.py --since <genesis date>`
    - `wrangler d1 execute mvm-prod --command 'SELECT COUNT(*) FROM daily_aggregates'` → matches `ticks` row count.

## ADR

### Decision
Build a per-day idempotent tick runner that owns a SQLite single source of truth on openclaw (with enforced single-writer via `fcntl.flock`), publishes a structured aggregates + 10-named-monkey surface to Cloudflare D1 via a bearer-token-authenticated Pages Function with schema-version negotiation, and renders the public dashboard via SvelteKit SSR reading D1 through a Pages binding with 60-second cache. **AI is structured as a model-keyed registry from day one (council-folded v2.2)**: every AI table carries `model_id`, the algorithm lives behind a tiny duck-typed builder interface, and the determinism contract is scoped per `model_id` per `runtime_fingerprint` — adding a second model family is a one-line dict entry, never a migration.

### Drivers
1. Cost ceiling < $5/mo (favours free-tier CF + user-owned compute).
2. One-developer maintainability (favours minimum moving parts + reversible decisions).
3. Auditable forward-only evolution with bit-identical re-runs given identical input bars (idempotency).

### Alternatives considered
- **All-in-D1 (no SQLite)**: rejected — Python's D1 story is HTTP-only with account-wide tokens; 100k×daily rows blows free tier.
- **Postgres on Oracle Free Tier / Hetzner VPS, no D1 sync at all** (architect's steelmanned antithesis): credible alternative that deletes the entire publish-sync layer. Rejected on user preference — openclaw is paid-for hardware, no recurring billing surface, and the principle "compute lives off Cloudflare" came from the user, not the architect. The synthesis tweak (collapse D1 schema to one `publish_rows(date, kind, json)` table) was also considered and rejected: small dashboard surface justifies typed columns over JSON parsing.
- **All-local (no D1, no public dashboard)**: rejected — user explicitly wants a Cloudflare-hosted public dashboard.
- **Parquet-per-tick instead of SQLite rows**: rejected for v1 — DuckDB-over-parquet IS queryable (not strawmanned), but two storage systems on openclaw vs one is the deciding factor for a one-developer project.
- **Cloudflare D1 HTTP API direct write from openclaw**: rejected — account-scoped token blast radius is too large.
- **Council's Expansionist proposal: add `ai_predictions(model_id, date, ticker, score, rank)` + `leaderboard` view + `feature_set_id` + a hashable `ModelSpec` in v1** (council-folded v2.2): rejected for v1 — three of five council reviewers flagged it as a six-month side-project masquerading as v1, and a leaderboard built before the determinism contract is tested is worse than no leaderboard. Deferred to v2 when model #2 actually exists; the chosen `model_id` + `config_json` + `diagnostics_json` foundation makes that addition non-destructive (new table + new view, no migration of existing rows).
- **Council's Contrarian proposal: document determinism as sklearn-HistGBM-specific and stop pretending the contract survives a swap**: rejected as overly defeatist — determinism is per-`model_id` and per-`runtime_fingerprint`, not cross-family. Adopted the runtime fingerprint + per-family scope instead (`DETERMINISM.md`, A19–A21).

### Why chosen
- SQLite + WAL handles 100k row/day INSERTs in single-digit-second per tick on commodity hardware.
- D1 publish surface stays under 50 MB/yr — comfortable in free tier.
- SvelteKit + Pages matches the existing Tally/GoCard stack — zero new tooling.
- Phases ship independently; Phase 1+2 are useful standalone (CLI tick) before any cloud surface exists.

### Consequences
- (+) Re-runnable from genesis at any time given pinned deps.
- (+) D1 wipeable and rebuildable from SQLite (A14).
- (+) Bit-identical reruns given persisted prices (R2).
- (+) **Adding a new AI family (LightGBM/XGBoost/NN/stacking) or a new overfitting control (purged CV, embargo, rolling window) costs one entry in `MODELS` plus a new `config_json` shape — no schema migration, no `runner_tick.py` change, no dashboard rewrite** (council v2.2 dividend).
- (+) Multi-model "league" lights up by `len(MODELS) > 1` without any database change.
- (−) Two databases must stay schema-compatible — addressed by `publish_schema_version` (R12).
- (−) openclaw is a single point of failure for forward evolution; mitigation: rsync nightly to a NAS or second box (not v1, but documented).
- (−) Pages Function cold start ~50 ms per route on first visit each minute; 60s cache amortises across visitors.
- (−) Determinism contract is documented as per-`model_id` per-`runtime_fingerprint`; cross-family equivalence is explicitly NOT promised. Adding a model family means a new `model_id` (never reuse), and lockfile bumps invalidate prior rows for replay (not forward simulation).

### Follow-ups (v2)
- Wire `src/mvm/broker/alpaca.py` — needs Alpaca account, paper-trading sandbox, secrets-rotation pipeline.
- Add the first non-`hgb_v1` entry to `MODELS` (LightGBM is the natural candidate). The schema already supports it; this is purely a code change.
- Add `ai_predictions(model_id, date, ticker, score, rank)` table when stacking / ensemble / disagreement-trading becomes useful (Expansionist's proposal, deferred).
- Add `retired_at` column on `ai_model_history` + a "model graveyard" UI view when the first model variant is sunsetted (council reviewer 4: "the league needs a graveyard").
- Optional `ai_model_runs` audit table if `(model_id, date)` produces multiple artifacts per day (currently 1 per day).
- Add purged walk-forward CV, embargo periods, or rolling-window training as new `config_json` fields against a new `model_id` — never modifying old rows.
- Universe-evolution policy (rolling S&P 500 membership; stored in a new `universe_changes` table).
- Rolling-window VACUUM for `monkey_history` at year 3.
- "Adopt a monkey" share link — visitor URL parameter assigns them a stable random monkey ID to follow.

## Changelog
- 2026-05-20 v1: Initial draft from deep-interview spec.
- 2026-05-20 v2 (iteration 1): Incorporated Architect + Critic feedback.
  - **From Architect**: `ai_holdings_current` is now a VIEW (not a table). AI classifier gets explicit `random_state`. Disk math corrected (1 GB/yr). `fcntl.flock` added to `db.get_conn`. `INSERT ... ON CONFLICT DO UPDATE` replaces `INSERT OR REPLACE` to avoid FK cascade. New scripts: `catchup.py`, `rebuild_d1.py`, `rotate_d1_token.sh`. Genesis seed now persisted to `genesis_log.seed_string` (not literal in code). Dashboard `/` route exposes `last_tick_at`. D1 write budget noted (A6).
  - **From Critic**: A2 / A3 / A8 / A11 acceptance criteria tightened with measurement methodology. Step 5 monkey refactor decomposed into 5a/5b/5c. A3 idempotency boundary made explicit (given identical input prices via `prices` upsert). Phase 3 step 15 adds D1 migrations file. Named-monkey refresh logic added (step 13). AI warmup (A16) addresses cold-start problem. `.gitignore` (A17). Holiday handling via `status='skipped_no_bar'` (A7, A14 verification). `publish_schema_version` resolves SQLite/D1 drift (R12, R15). Dashboard 60-second cache addresses cold-start cost. Streamlit sunset clarified in A10/step 40.
- 2026-05-20 v2.1 (iteration 2 polish — both reviewers APPROVED): Step 11 split into Tx 1 (prices) + Tx 2 (simulation) so skipped-bar path never opens a simulation tx. `AI_TOP_K = 10` explicitly pinned at module top of `runner_tick.py`. Step 16 carries explicit asymmetry note explaining D1's `INSERT OR REPLACE` vs SQLite's `ON CONFLICT DO UPDATE`. Step 27 (`deploy/openclaw/README.md`) adds explicit SPOF disclaimer recommending `mvm-backup.timer` rsync before treating system as durable.
- 2026-05-20 v2.2 (LLM Council fold — 5 advisors + chairman, see `.omc/council/council-report-2026-05-20-1715.html`): AI persistence layer is now model-keyed from day one. New principle #6 (per-family determinism). A4 schema rewritten: `model_id` + `model_family` + `config_json` + `diagnostics_json` + `runtime_fingerprint` + `features_hash` + `train_window_end` + `training_seconds` columns; typed sklearn columns dropped; `ai_holdings_current` VIEW removed in favour of parameterised query. A12 determinism scope reframed to per-`model_id` per-`runtime_fingerprint`. New ACs A18–A21: registry pattern, runtime fingerprint, determinism test, `DETERMINISM.md`. Step 9 expanded to 9a–9d (registry, ai_trader rewrite, runtime_fingerprint, features_hash). Step 11 (`runner_tick`) now iterates `MODELS.items()` so adding model #2 is a one-line dict entry. New tests: `test_determinism.py` (gates all AI schema changes), `test_registry_shape.py`. ADR adds explicit rejection of Expansionist's `ai_predictions` table for v1 + Contrarian's defeatist determinism framing. Consequences gain explicit "swap costs one dict entry, never a migration" dividend. Follow-ups list LightGBM-as-first-non-hgb model + `ai_predictions` deferred + `retired_at` graveyard column. Total: ~3 hours of v1 work for a system that genuinely keeps training method, overfitting controls, and league structure swappable later without rewriting any of v1.
- 2026-05-20 v2.3 (shipped + post-build validation fixes — autopilot Phase 4): All 12 unit tests pass including the network-bound determinism gate (real tick run twice, byte-identical state asserted).
  - **From Architect**: systemd `ExecStartPost=$(date ...)` doesn't shell-substitute — `push_to_d1.py` now defaults `--date` to today US/Eastern (matching `run_tick.py`) and the unit no longer uses `$(...)`. `db.py` `ROLLBACK` swallow narrowed to "no transaction is active" only. `ingest.ts` fails closed (HTTP 500) if `PUBLISH_SCHEMA_VERSION` env binding is missing. `rebuild_d1.py` end-date now US/Eastern instead of UTC.
  - **From code-reviewer**: `bootstrap_genesis.py` now writes the whole DB inside a single `transaction()` to a `.genesis.tmp` path, then `os.replace`s it atomically — partial state on Ctrl-C is no longer possible. `_update_ai_equity` raises loudly if today's or yesterday's close panel row is missing (was silently zeroing `daily_return`). Sell branch in `step_monkeys_one_day` adds the same NaN/zero-price guard as the buy branch. `_load_close_volume_panels` and `runner_tick`'s close-fill drop the `bfill()` to prevent future-data leakage backwards into warmup rows. `with conn:` blocks in egress scripts removed (no-op under autocommit). Explicit `astype("float64")` lock on the close + volume pivots.
  - **Known divergences from earlier plan versions** (acknowledged): SQLite schema added `ai_portfolio_equity(date, model_id, equity, daily_return)` (needed by the race chart — equity is derived from weights, not in `ai_portfolio_history`). D1 schema added matching `ai_equity` table + `ingest.ts` path. `daily_aggregates.spy_equity` is currently always `NULL` — SPY isn't in the universe yet; A8's "count beating SPY" sub-requirement is deferred to v2 with a follow-up. Monkey RNG is per-tick (`hash_seed("monkey_tick", date)`) rather than per-monkey-per-date — passes the determinism gate, plan letter requires per-monkey seeding, low-priority follow-up.
