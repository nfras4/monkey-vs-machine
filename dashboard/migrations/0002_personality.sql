-- D1 publish schema v2: add 8-monkey personality cast + frozen external events.
--
-- Pairs with engine schema additions in src/mvm/state/schema.sql (Phase 1) and
-- ingest.ts payload v2 (Phase 3). Apply via:
--
--   wrangler d1 execute mvm-prod --remote --file=migrations/0002_personality.sql
--
-- Then bump the PUBLISH_SCHEMA_VERSION secret to 2 and deploy the receiver.
-- The next `./update.ps1` push will populate named_monkey_history with the
-- new cast + external_events with the Lakers fixture. There is a brief
-- window between this migration and the next push where /monkeys is empty.

-- Denormalised: each named_monkey_history row carries its monkey's current
-- personality_config so the /monkeys page can render cast cards without a
-- second table. NULL on legacy (alice/bob/carol) rows, non-null on v3 cast.
ALTER TABLE named_monkey_history ADD COLUMN personality_config TEXT;

-- Frozen NBA results etc., mirrors src/mvm/state/schema.sql external_events.
CREATE TABLE IF NOT EXISTS external_events (
    date TEXT NOT NULL,
    event_kind TEXT NOT NULL,
    outcome INTEGER NOT NULL,
    payload_json TEXT,
    PRIMARY KEY (date, event_kind)
);
CREATE INDEX IF NOT EXISTS idx_external_events_kind_date ON external_events(event_kind, date);

-- Purge legacy cast — the next push will write the v3 cast rows.
-- This matches the engine-side migrate_personality_cast.py behaviour so
-- /monkeys never surfaces a stale alice/bob/carol card after the migration.
DELETE FROM named_monkey_history WHERE name IN ('alice', 'bob', 'carol');

-- Record the publish schema bump.
INSERT OR IGNORE INTO publish_schema_version (version) VALUES (2);
