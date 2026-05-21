-- Rollback for 0002_personality.sql.
--
-- D1 (SQLite) can't drop a column without an expensive table-rebuild, so the
-- personality_config column stays as a no-op tombstone (NULL values are safe;
-- the legacy ingest schema never reads it). What we DO undo:
--
-- 1. Drop the external_events table — the engine side already refuses to tick
--    if external_events is present without a fingerprint match, so leaving
--    these rows would be a future footgun.
-- 2. Roll publish_schema_version table marker back. The actual gating env var
--    PUBLISH_SCHEMA_VERSION must be flipped back to "1" via:
--      wrangler pages secret put PUBLISH_SCHEMA_VERSION   (then enter 1)
--
-- Re-seeding the legacy alice/bob/carol named_monkey_history rows is NOT done
-- here — they were deliberately deleted as a deterministic boundary. If you
-- truly need them back, restore from a D1 export taken before 0002.

DROP TABLE IF EXISTS external_events;
DELETE FROM publish_schema_version WHERE version = 2;
