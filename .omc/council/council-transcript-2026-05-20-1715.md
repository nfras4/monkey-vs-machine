# Council Transcript — 2026-05-20 17:15 AEST

## Original user question

> Council this, i want to ensure i can change the way is is trained later with different methods or make adjustments to i can limit overfitting

## Framed question

Does the perpetual-loop trading-sim plan keep:
1. AI training method swappable (LightGBM / XGBoost / RandomForest / NN / stacking) without rewriting `runner_tick.py`, `ai_trader.py`, `ai_model_history`, the dashboard, or the determinism contract?
2. Overfitting controls addable later (purged walk-forward CV, rolling vs expanding window, regularization, early stopping, embargo, validation Sharpe gates, feature ablation, ensemble averaging) without breaking idempotency or persisted history?
3. Multiple model variants in parallel (a "league" of competing AIs)?

What concrete v1 plan changes preserve extensibility without bloating v1?

**Current schema:** `ai_model_history(date, feature_importances, hyperparams, random_state, train_score)` — single model assumed. `ai_portfolio_history(date, ticker, weight)`. `ai_holdings_current` VIEW. D1 mirrors.

**Constraints:** one developer, "for fun", bit-identical reruns given same prices, daily tick + daily retrain, local SQLite + D1 publish mirror.

---

## Anonymisation map (for peer review pass)

| Letter | Advisor |
|---|---|
| A | The First Principles Thinker |
| B | The Contrarian |
| C | The Executor |
| D | The Outsider |
| E | The Expansionist |

---

## Advisor responses

### The Contrarian (Response B)

You're asking the wrong question. You've already decided the answer is "yes, with a few interfaces" — what you need is for someone to point out the trap you're walking into.

**The fatal flaw: "bit-identical reruns" and "swappable models" are in direct tension, and you haven't acknowledged it.**

The moment you swap sklearn for LightGBM/XGBoost/Torch, your determinism contract breaks. Different libraries have different RNG semantics, different float reduction orders, different thread-nondeterminism (LightGBM `num_threads`, XGBoost `nthread`, CUDA atomics in NN). SHA256-seeding a `random_state` int does nothing for OpenMP reduction order. Your "bit-identical" rerun guarantee is sklearn-HistGBM-specific and you don't know it yet.

**Second flaw**: `ai_model_history` schema bakes in sklearn vocabulary. `feature_importances`, `hyperparams` as what — JSON blob? `train_score` as what metric? A stacking ensemble has no single `feature_importances`. A NN has no `train_score` in the same sense. You'll either lie in the columns or migrate the table — and migrating breaks reruns of old dates.

**Third flaw**: "League of competing AIs" with `ai_portfolio_history(date, ticker, weight)` having no `model_id` column. You'll bolt it on later, default to `'default'`, and now your D1 mirror, dashboard, and VIEW all need conditional logic forever.

**What to add in v1, non-negotiable:**
1. `model_id TEXT NOT NULL` on every AI table now. Default `'v1_histgbm'`. Composite PK `(date, model_id)` and `(date, ticker, model_id)`.
2. `artifact_json TEXT` blob replacing typed columns. Schema-per-model, not schema-per-database.
3. Pin determinism to one library family. Document it as **sklearn-HistGBM-determinism**, not "AI-determinism". Stop pretending the contract survives a swap.
4. Kill `ai_holdings_current` VIEW. Make it a parameterized query taking `model_id`.

Everything else is yak-shaving.

### The First Principles Thinker (Response A)

You're asking three "is my plan extensible enough" questions. That's the wrong question. The real question is: **what is the smallest persistence contract that makes every future variant a pure function of (date, prices, config)?**

Strip it down. You have three things, not three concerns:

1. A **model_id** (string). Not a table assumption. Every row in `ai_model_history` and `ai_portfolio_history` needs a `model_id` column NOW. That single change kills assumptions 1 and 3 simultaneously. "Single model assumed" is the actual bug in your v1.

2. A **config blob** (JSON). Hyperparams, algo choice, CV scheme, embargo, window type, regularization, ensemble recipe — all of it. One column: `config_json`. One column: `config_hash`. Determinism contract becomes: `(date, prices, config_hash) -> identical output`. Not "same hyperparams" — same *everything*. Overfitting controls (#2) are just config fields you haven't invented yet.

3. A **fit interface**. One function: `fit_predict(train_df, predict_df, config, rng) -> (scores, diagnostics_dict)`. sklearn, LightGBM, NN, stacking — all conform. `runner_tick.py` never names an algorithm. `ai_trader.py` becomes a 20-line dispatcher reading `config["algo"]`.

What you do NOT add to v1: actual LightGBM, actual CV, actual league UI. Those are YAGNI.

What you DO add to v1, today:
- `model_id` column everywhere (default `"v1_hgb"`)
- `config_json` + `config_hash` columns (replaces `hyperparams`)
- `diagnostics_json` column (replaces `train_score`, `feature_importances`)
- Primary key becomes `(date, model_id)` not `(date)`
- The view `ai_holdings_current` filters by a `default_model_id` setting

That's it. Four schema changes. Everything else is future config.

### The Expansionist (Response E)

The hidden gold here isn't "swap LightGBM in later." It's the **league**. Build for that NOW and you've quietly created a personal Numerai/Kaggle inside your own simulator, with bit-identical replay. That's a content engine, a research lab, and a portfolio piece all at once.

Concrete v1 changes that unlock 10x upside:

1. **`model_id` is a first-class column everywhere.** `ai_model_history(model_id, date, ...)`, `ai_portfolio_history(model_id, date, ticker, weight)`, drop the "single model assumed" baggage today. Cost: one column. Payoff: every future variant lights up automatically. Your "current" view becomes `WHERE model_id = 'champion'`.

2. **Persist predictions, not just weights.** Add `ai_predictions(model_id, date, ticker, score, rank)`. This is the unlock for stacking, ensemble averaging, calibration analysis, and disagreement-based features ("trade where models disagree most"). Costs ~nothing. Enables everything.

3. **`ModelSpec` as a hashable dict** (`{family, hyperparams, feature_set, cv_scheme, window_type, seed_salt}`) → `model_id = sha256(spec)`. Now determinism, registry, and the league all share one primitive. Adding purged CV later? New field, new hash, new model_id, old history untouched.

4. **A `leaderboard` view from day one**, even with one model. Forces you to define the scoring contract (Sharpe? hit rate? turnover-adjusted?) before you have political attachment to "the" model.

5. **Feature pipeline as a versioned artifact** (`feature_set_id`). Lets you ablate features as separate "models" in the league without code forks.

The dashboard angle nobody's mentioning: a live league standings page is dramatically more compelling than "here's my one model's equity curve." That's the upside.

### The Outsider (Response D)

Three things jump out as an outsider reading this cold.

**1. You have a single-model schema for a question that already names six successors.** `ai_model_history` keys on `(date)` with `single model assumed`. The moment you add LightGBM alongside HGB, that PK breaks and you're writing a migration. Just add `model_id TEXT` to the PK on `ai_model_history` and `ai_portfolio_history` NOW. Make `ai_holdings_current` a VIEW filtered by a configured `active_model_id`. That single change unlocks the "league" with zero v1 cost — you just run one model and write `model_id='hgb_v1'`.

**2. "Hyperparams" as a column is a trap.** Different model families have wildly different param shapes, and `feature_importances` doesn't exist for NNs or stacks. Store both as JSON blobs (`config_json`, `diagnostics_json`). Stop pretending the schema knows what's in them. Add a `model_family` column so the dashboard can branch on rendering.

**3. The determinism contract is undefined in writing.** You say "bit-identical given same prices" and "RNG via SHA256(purpose, date)" — but is that a tested invariant or a vibe? Write one test NOW: run tick for date D twice, assert identical `feature_importances` hash and identical weights. Without that test, every new model you bolt on will silently break determinism and you won't know which one did it.

**What I'd skip in v1:** Don't build the abstract `Trader` base class yet. Don't add CV plumbing. Don't add embargo logic. Those are YAGNI until model #2 exists. The schema changes and the determinism test are the only things that are expensive to retrofit. Everything else is a refactor you can do when it actually hurts.

### The Executor (Response C)

Three changes Monday morning. Skip everything else.

**1. Add a `model_id` column NOW. Everywhere.**

`ai_model_history`, `ai_portfolio_history`, `ai_holdings_current` view, D1 mirrors. Default value `'hgb_v1'`. That's it. Without this you cannot run a league, cannot A/B, cannot even rename your hyperparams without a migration. It's one ALTER TABLE today vs. a painful backfill in three months. Make the PK `(date, model_id)` for history and `(date, ticker, model_id)` for portfolio. Done.

**2. One file: `models/registry.py` with a dict.**

```python
MODELS = {"hgb_v1": build_hgb_v1}
```

`runner_tick.py` does `for model_id, builder in MODELS.items(): train_and_store(model_id, builder, ...)`. Each `builder` returns an object with `.fit(X, y, seed)` and `.predict_proba(X)`. That's the entire interface. No ABC, no plugin system, no config YAML. When you want LightGBM, add one entry. When you want stacking, add one entry whose builder wraps two others. The "league" is literally `len(MODELS) > 1`.

**3. Persist the feature matrix hash + label cutoff date per row.**

Add `features_hash TEXT, label_cutoff_date DATE` to `ai_model_history`. Costs nothing now. Lets you later prove determinism after you swap libraries, detect silent feature drift, and verify your 5-day embargo held. Without this, six months from now you cannot tell if a backtest divergence is a bug or a feature change.

**Skip for v1**: CV framework, validation gates, ensemble code, abstract base classes, model serialization. YAGNI. The three changes above unlock all of them later without touching `runner_tick.py` again.

Total work: ~2 hours. Ship today.

---

## Peer reviews (anonymised by letter)

### Review 1

**Strongest: B (Contrarian).** Only one to name the actual trap: "bit-identical reruns" and "swap LightGBM/XGBoost/Torch" are in direct tension. OpenMP reduction order, thread nondeterminism, CUDA atomics — none touched by an SHA256 seed. Every other response treats determinism as a solved property carried forward via a config_hash (A) or a test (D). B is right that the contract is library-family-specific and must be documented as such. B also correctly kills the `ai_holdings_current` VIEW, which A and D naively keep parameterized.

**Biggest blind spot: E (Expansionist).** Seduced by the "league as content engine" framing and skips the determinism problem entirely. Persisting predictions and feature_set_id is fine, but a leaderboard built on non-reproducible scores is worse than no leaderboard. E is building the dashboard before the invariant.

**All five missed**: Schema versioning of the *feature pipeline code itself*. A `features_hash` (C) or `feature_set_id` (E) captures the spec, not the implementation. A pandas/numpy upgrade silently changes rolling-window NaN handling, and every old row becomes a lie. Pin the compute environment (lockfile hash) into `ai_model_history`, or the determinism contract dies on `pip install -U` — not on a model swap.

### Review 2

**Strongest: C (Executor).** Only response that names files, defines an interface (`.fit/.predict_proba`), gives a concrete registry shape (`MODELS` dict keyed by id), and adds `features_hash` + `label_cutoff_date` — which simultaneously solves determinism proof, embargo verification, and drift detection. It's the minimum schema that makes B's concerns testable and E's league trivial to bolt on. Two-hour estimate is honest.

**Biggest blind spot: A (First Principles).** A's "smallest contract" explicitly punts the determinism question that B correctly identifies as fatal. A keeps `diagnostics_json` but offers no `features_hash`, no determinism test, and no way to detect when a library swap silently breaks reproducibility. A is internally coherent but ships a contract that can't defend itself the moment model #2 lands.

**All five missed**: Seed provenance and library version pinning in the row itself. None of A-E persist `python_version`, `library_versions_json`, `numpy_blas`, or `thread_count` alongside `model_id`. Bit-identical reruns aren't a property of code — they're a property of the environment. Without a `runtime_fingerprint` column, "rerun date D" silently means "rerun on whatever sklearn is installed today," and the contract dies on the first `pip install -U`.

### Review 3

**Strongest: B (Contrarian).** Only response that engages with the *actual* contract conflict the user named. "Bit-identical + swappable" is genuinely broken once LightGBM/NN enter, and pretending otherwise (A, C, D, E all do) ships a v1 that lies to itself. B's prescription (artifact_json blob, document determinism as library-scoped, kill the typed sklearn-vocabulary columns) is the only one that survives contact with XGBoost.

**Biggest blind spot: E (Expansionist).** The league framing is seductive but E never addresses determinism at all. A leaderboard that re-ranks every rerun because LightGBM's thread reduction order shifted is worse than no leaderboard. E also bloats v1 with a second table and a view before model #2 exists.

**All five missed**: The retrain cadence itself. Daily retrain on expanding window means model_id alone is insufficient — the *same* ModelSpec produces N artifacts over N days, and the dashboard/history need (model_id, train_window_end) to be meaningful. None of A-E specified what gets stored: the spec, the trained artifact, or both.

### Review 4

**Strongest: D (Outsider).** Only response that names determinism as a *testable* property rather than a vibe or schema assertion. "Write the determinism test now" is the load-bearing insight — without it, every other claim about bit-identical reruns is unfalsifiable. D also correctly traps `hyperparams` and `feature_importances` as typed columns (family-specific) while keeping the v1 surface tiny.

**Biggest blind spot: B (Contrarian).** B declares "bit-identical and swappable are incompatible" and stops there. That's defeatist — determinism is per-family, and the contract is `(date, prices, config, model_id) -> identical output`, not cross-family equivalence. B's diagnosis is real but the prescription (document as sklearn-only) forecloses the league prematurely.

**All five missed**: The retraining cost / wall-clock budget for a daily tick. A league of 5+ variants retraining daily on growing history is fine at year 1, painful at year 5. Nobody specified a `training_seconds` diagnostic or a wall-clock budget per `model_id`. Also missed: prediction storage cost (E's `ai_predictions` table grows as variants × days × symbols) and a retirement protocol for dead variants. The league needs a graveyard, not just a leaderboard.

### Review 5

**Strongest: D (Outsider).** Only response that names determinism as the load-bearing risk and demands a test, not a promise. B identifies the same tension but capitulates ("document it as sklearn-specific") instead of forcing a contract. D's `config_json` + `diagnostics_json` + `model_family` split is the minimum viable schema; everything else (CV, embargo, ABCs) is correctly deferred to "when model #2 exists." C is close but skips the determinism test, which is the one thing that genuinely cannot be added later without invalidating prior runs.

**Biggest blind spot: E (Expansionist).** The league/leaderboard pitch ignores the one-developer "for fun" constraint. `ai_predictions` table, feature_set_id versioning, hashable ModelSpec, and live standings UI is a six-month side-project masquerading as v1.

**All five missed**: Retrain cost under daily ticks with multiple model families, and how to handle determinism drift when upstream libraries patch-bump (numpy/sklearn ABI changes silently break bit-identical reruns). The determinism contract needs a pinned-lockfile clause, not just a test.

---

## Chairman synthesis

### Where the council agrees

Four of five advisors converged independently on the same v1 schema change, and the fifth doesn't contradict it:

1. **`model_id` becomes a first-class column on every AI table, today.** Non-negotiable. PK becomes `(date, model_id)` on `ai_model_history` and `(date, ticker, model_id)` on `ai_portfolio_history`.

2. **Kill the typed sklearn-vocabulary columns.** `feature_importances` and `train_score` are HistGBM-flavoured. Replace with `config_json` (the spec) and `diagnostics_json` (whatever the family produces).

3. **No ABC, no plugin system, no YAML, no CV framework, no embargo logic, no validation gates in v1.** YAGNI until model #2 actually lands.

4. **The fit interface is a tiny duck-typed contract**, not an inheritance hierarchy. Executor's `.fit(X, y, seed) / .predict_proba(X)` and FirstPrinciples' `fit_predict(...)` are the same shape. `runner_tick.py` never names an algorithm; it iterates a registry dict.

5. **The `ai_holdings_current` VIEW is wrong once `model_id` exists.** Replace with a parameterised query that takes `model_id`.

### Where the council clashes

**Is bit-identical determinism survivable across model families?**

- **Contrarian:** No. OpenMP reduction order, CUDA atomics, library RNG semantics make "bit-identical" a sklearn-HistGBM-specific property.
- **Outsider / Executor / First Principles:** Yes, *per family*. The contract is `(date, prices, config, model_id) -> identical output` within a family/runtime — never cross-family. Write the test, pin the env, move on.

Outsider/Executor framing wins. Contrarian's threat model wins on environment dependence (see blind spots).

**Add an `ai_predictions` table now?**

- **Expansionist:** Yes — unlocks stacking, ensemble, disagreement-trading, leaderboard.
- **Everyone else, implicitly:** Premature. 3 of 5 reviewers flagged Expansionist as the biggest blind spot.

Expansionist loses on constraints. The league is `len(MODELS) > 1` in a registry dict, not a new table.

### Blind spots the council caught

1. **Environment fingerprint, not just config hash.** Reviewers 2 and 5 named it. `random_state` + `config_json` is insufficient; bit-identical reruns depend on `python_version`, `numpy_version`, `sklearn_version`, lockfile hash, BLAS variant, thread count. Without a `runtime_fingerprint` column, the first `pip install -U` silently invalidates every historical row.

2. **Feature pipeline code versioning.** Reviewer 1. Same fix: lockfile hash.

3. **Train-window provenance.** Reviewer 3: daily retrain on expanding window means one `model_id` produces N artifacts over N days. Need `train_window_end` on the row.

4. **Wall-clock + storage cost of the league.** Reviewer 4: need `training_seconds` diagnostic and a retirement protocol. "The league needs a graveyard."

### Recommendation

Slightly larger than Executor's "Monday morning" patch, smaller than Expansionist's vision.

**SQLite + D1 schema changes:**

```sql
ALTER TABLE ai_model_history ADD COLUMN model_id TEXT NOT NULL DEFAULT 'hgb_v1';
ALTER TABLE ai_model_history ADD COLUMN model_family TEXT NOT NULL DEFAULT 'sklearn_hgb';
ALTER TABLE ai_model_history ADD COLUMN config_json TEXT NOT NULL DEFAULT '{}';
ALTER TABLE ai_model_history ADD COLUMN diagnostics_json TEXT NOT NULL DEFAULT '{}';
ALTER TABLE ai_model_history ADD COLUMN runtime_fingerprint TEXT NOT NULL DEFAULT '{}';
ALTER TABLE ai_model_history ADD COLUMN features_hash TEXT NOT NULL DEFAULT '';
ALTER TABLE ai_model_history ADD COLUMN train_window_end TEXT NOT NULL DEFAULT '';
ALTER TABLE ai_model_history ADD COLUMN training_seconds REAL;
-- Drop typed columns feature_importances, hyperparams, train_score
-- New PK: (date, model_id)

ALTER TABLE ai_portfolio_history ADD COLUMN model_id TEXT NOT NULL DEFAULT 'hgb_v1';
-- New PK: (date, ticker, model_id)

-- Drop ai_holdings_current VIEW; replace with parameterised query.
```

**Code:**
- `src/mvm/models/registry.py` — `MODELS = {"hgb_v1": build_hgb_v1}`. Builders expose `.fit(X, y, seed)` + `.predict_proba(X)`. No ABC.
- `src/mvm/runner_tick.py` — iterate `MODELS.items()`. Write one row per `(date, model_id)`.
- `src/mvm/runtime_fingerprint.py` — returns `{python, numpy, sklearn, pandas, lockfile_sha256, blas, threads}` as JSON. Called once per tick.
- `tests/test_determinism.py` — run tick for date D twice, assert byte-identical weights + `feature_importances_sha256`. CI must run it.
- `DETERMINISM.md` — 10 lines stating the contract is per-`model_id` per-`runtime_fingerprint`; lockfile bumps invalidate prior rows for replay, not forward simulation.

**Deferred to when model #2 actually exists:**
- `ai_predictions` table (Expansionist's stacking dream)
- Leaderboard view
- Purged CV, embargo, rolling-vs-expanding switches, validation Sharpe gates, ensemble averaging
- Plugin system, YAML config
- `retired_at` flag

Total work ≈ 3 hours.

### The one thing to do first

**Write the determinism test before touching the schema.** Run `runner_tick(date=D)` twice in one process, hash `weights` and `feature_importances`, assert equality. Check it into CI. Everything else is theatre if that test doesn't pass on current code today. If it passes, you have a real contract to extend. If it doesn't, the v1 plan is wrong and you need to know now — not after adding `model_id`.
