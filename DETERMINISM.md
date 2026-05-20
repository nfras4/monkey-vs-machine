# Determinism Contract

This project guarantees **bit-identical reruns of a tick** under a single,
tightly-scoped condition: same `model_id`, same `runtime_fingerprint`, same
input prices (which are persisted to the `prices` table on first fetch and
never overwritten by re-fetches).

## What's promised
- For a fixed `model_id` and a fixed `runtime_fingerprint`, running
  `run_tick(date=D)` twice produces byte-identical rows in `monkey_history`,
  `ai_model_history.diagnostics_json` (after JSON-hashing), and
  `ai_portfolio_history.weight` per ticker.
- RNG seeds are SHA256-derived from `(seed_string, purpose, model_id, date)`,
  using the genesis `seed_string` stored in `genesis_log`.

## What's NOT promised
- **Cross-family equivalence**. Swapping `hgb_v1` for `lightgbm_v1` produces a
  new `model_id`. The new family's output is its own contract, not the old one's.
- **Cross-runtime equivalence**. A `pip install -U` that bumps `numpy`,
  `scikit-learn`, `pandas`, `pyarrow`, the BLAS, or Python itself produces a
  new `runtime_fingerprint`. Prior rows remain valid for forward simulation
  but bit-identical replay across the boundary is not guaranteed.

## Operational consequences
- Adding a new training method = new `model_id` entry in `models/registry.py`.
  Old rows for the old `model_id` keep working.
- Bumping a pinned library version = breaking change for the *replay* property
  only. Forward ticks continue to be deterministic going forward under the new
  fingerprint.
- `tests/test_determinism.py` runs in CI and gates AI schema changes.
