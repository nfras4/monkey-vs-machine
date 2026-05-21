-- SQLite schema for the perpetual monkey-vs-machine simulator.
-- v2.2 (council-folded): AI tables are model-keyed; typed sklearn columns gone.
-- Pragmas live in db.py so we can apply them on every connection.

CREATE TABLE IF NOT EXISTS genesis_log (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    start_date TEXT NOT NULL,
    seed_string TEXT NOT NULL,
    warmup_days INTEGER NOT NULL,
    n_monkeys INTEGER NOT NULL,
    universe_tickers_json TEXT NOT NULL,
    personality_monkey_ids_json TEXT NOT NULL,
    spy_anchor_date TEXT,        -- latest SPY-trading date <= start_date
    spy_anchor_close REAL,       -- SPY close on that anchor; used to compute spy_equity each tick
    -- v3 personality cast: fingerprint of frozen external_events; null on legacy/empty
    external_events_fingerprint TEXT,
    -- v3 personality cast: bumped by deterministic-boundary migrations + rebases
    cast_version INTEGER NOT NULL DEFAULT 1,
    -- v3 personality cast: snapshot the whole cast config at genesis for bit-identical reruns
    personality_config_json TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS tickers (
    ticker TEXT PRIMARY KEY,
    added_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS prices (
    date TEXT NOT NULL,
    ticker TEXT NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL NOT NULL,
    volume REAL,
    PRIMARY KEY (date, ticker)
);
CREATE INDEX IF NOT EXISTS idx_prices_date ON prices(date);

CREATE TABLE IF NOT EXISTS monkeys (
    monkey_id INTEGER PRIMARY KEY,
    cash REAL NOT NULL,
    shares REAL NOT NULL,
    position_ticker TEXT,
    equity REAL NOT NULL,
    last_date TEXT
);

CREATE TABLE IF NOT EXISTS monkey_history (
    date TEXT NOT NULL,
    monkey_id INTEGER NOT NULL,
    cash REAL NOT NULL,
    shares REAL NOT NULL,
    position_ticker TEXT,
    equity REAL NOT NULL,
    action TEXT,
    PRIMARY KEY (date, monkey_id)
);
CREATE INDEX IF NOT EXISTS idx_monkey_history_date ON monkey_history(date);

-- Model-keyed AI history (council v2.2)
CREATE TABLE IF NOT EXISTS ai_model_history (
    date TEXT NOT NULL,
    model_id TEXT NOT NULL DEFAULT 'hgb_v1',
    model_family TEXT NOT NULL DEFAULT 'sklearn_hgb',
    config_json TEXT NOT NULL DEFAULT '{}',
    diagnostics_json TEXT NOT NULL DEFAULT '{}',
    runtime_fingerprint TEXT NOT NULL DEFAULT '{}',
    features_hash TEXT NOT NULL DEFAULT '',
    train_window_end TEXT NOT NULL DEFAULT '',
    training_seconds REAL,
    PRIMARY KEY (date, model_id)
);

CREATE TABLE IF NOT EXISTS ai_portfolio_history (
    date TEXT NOT NULL,
    ticker TEXT NOT NULL,
    model_id TEXT NOT NULL DEFAULT 'hgb_v1',
    weight REAL NOT NULL,
    PRIMARY KEY (date, ticker, model_id)
);
CREATE INDEX IF NOT EXISTS idx_ai_portfolio_history_model_date ON ai_portfolio_history(model_id, date);

CREATE TABLE IF NOT EXISTS ai_portfolio_equity (
    date TEXT NOT NULL,
    model_id TEXT NOT NULL DEFAULT 'hgb_v1',
    equity REAL NOT NULL,
    daily_return REAL,
    PRIMARY KEY (date, model_id)
);

CREATE TABLE IF NOT EXISTS daily_aggregates (
    date TEXT PRIMARY KEY,
    monkey_mean REAL NOT NULL,
    monkey_median REAL NOT NULL,
    monkey_p5 REAL NOT NULL,
    monkey_p25 REAL NOT NULL,
    monkey_p75 REAL NOT NULL,
    monkey_p95 REAL NOT NULL,
    monkey_best REAL NOT NULL,
    monkey_worst REAL NOT NULL,
    n_monkeys INTEGER NOT NULL,
    n_monkeys_above_starting INTEGER NOT NULL,
    spy_equity REAL
);

-- Named monkeys: 8 personality (fixed at genesis, each with a deterministic
-- quirk in personality_config) + top3 + bottom3 + today_mover (daily-refreshed).
-- personality_config is JSON parsed into typed Personality dataclasses at tick start.
CREATE TABLE IF NOT EXISTS named_monkeys (
    name TEXT PRIMARY KEY,
    monkey_id INTEGER NOT NULL,
    category TEXT NOT NULL,
    personality_config TEXT,
    pinned_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS named_monkey_history (
    date TEXT NOT NULL,
    name TEXT NOT NULL,
    monkey_id INTEGER NOT NULL,
    category TEXT NOT NULL,
    equity REAL NOT NULL,
    PRIMARY KEY (date, name)
);
CREATE INDEX IF NOT EXISTS idx_named_monkey_history_name ON named_monkey_history(name, date);

CREATE TABLE IF NOT EXISTS ticks (
    date TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    duration_seconds REAL,
    note TEXT
);

-- Frozen external events seeded at genesis (NBA results, calendar credits,
-- anything date-keyed that informs personality monkey post-tick equity).
-- Mutating this table after genesis without re-running rebase_external_events.py
-- violates the determinism contract; runner_tick.py refuses to proceed on mismatch.
CREATE TABLE IF NOT EXISTS external_events (
    date TEXT NOT NULL,
    event_kind TEXT NOT NULL,
    outcome INTEGER NOT NULL,
    payload_json TEXT,
    PRIMARY KEY (date, event_kind)
);
CREATE INDEX IF NOT EXISTS idx_external_events_kind_date ON external_events(event_kind, date);

-- Audit trail for sanctioned external_events rebases. Every row corresponds to
-- one invocation of scripts/rebase_external_events.py and captures the old/new
-- fingerprint plus the human-supplied --reason.
CREATE TABLE IF NOT EXISTS external_events_rebase_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rebased_at TEXT NOT NULL DEFAULT (datetime('now')),
    old_fingerprint TEXT,
    new_fingerprint TEXT NOT NULL,
    rows_added INTEGER NOT NULL DEFAULT 0,
    rows_removed INTEGER NOT NULL DEFAULT 0,
    reason TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS d1_egress_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    status TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 1,
    response_code INTEGER,
    error TEXT,
    pushed_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_d1_egress_log_date ON d1_egress_log(date);
