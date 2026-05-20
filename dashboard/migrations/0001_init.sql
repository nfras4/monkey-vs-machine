-- D1 publish schema for monkey-vs-machine dashboard.
-- Asymmetry note: SQLite (source-of-truth, openclaw) uses INSERT ... ON CONFLICT DO UPDATE
-- to avoid FK cascade surprises. D1 (this side) is the flat publish surface and uses
-- INSERT OR REPLACE in the Pages Function ingest endpoint.

CREATE TABLE IF NOT EXISTS publish_schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);
INSERT OR IGNORE INTO publish_schema_version (version) VALUES (1);

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

CREATE TABLE IF NOT EXISTS ai_history (
    date TEXT NOT NULL,
    model_id TEXT NOT NULL,
    model_family TEXT NOT NULL,
    config_json TEXT NOT NULL,
    diagnostics_json TEXT NOT NULL,
    runtime_fingerprint TEXT NOT NULL,
    features_hash TEXT NOT NULL,
    train_window_end TEXT NOT NULL,
    training_seconds REAL,
    PRIMARY KEY (date, model_id)
);

CREATE TABLE IF NOT EXISTS ai_portfolios (
    date TEXT NOT NULL,
    ticker TEXT NOT NULL,
    model_id TEXT NOT NULL,
    weight REAL NOT NULL,
    PRIMARY KEY (date, ticker, model_id)
);

CREATE TABLE IF NOT EXISTS ai_equity (
    date TEXT NOT NULL,
    model_id TEXT NOT NULL,
    equity REAL NOT NULL,
    daily_return REAL,
    PRIMARY KEY (date, model_id)
);

CREATE TABLE IF NOT EXISTS named_monkey_history (
    date TEXT NOT NULL,
    name TEXT NOT NULL,
    monkey_id INTEGER NOT NULL,
    category TEXT NOT NULL,
    equity REAL NOT NULL,
    PRIMARY KEY (date, name)
);

CREATE TABLE IF NOT EXISTS tick_log (
    date TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    duration_seconds REAL,
    note TEXT,
    pushed_at TEXT NOT NULL DEFAULT (datetime('now'))
);
