"""Migrate a pre-v3 deployed state.db onto the 8-monkey personality cast.

Idempotent. Refuses to re-run once cast_version >= 2 (use --force to override).
Bootstrap and this script share `pick_personality_cast` from bootstrap_genesis,
so a Machine-A migration and a Machine-B fresh bootstrap converge to the same
(monkey_id, name, personality_config) mapping for a given seed_string.

Usage:
    python scripts/migrate_personality_cast.py            # one-shot
    python scripts/migrate_personality_cast.py --force    # re-run even if v2
    python scripts/migrate_personality_cast.py --dry-run  # print plan, no writes

Notes on `cast_version`:
- Local-state-only. NEVER pushed to D1, NEVER participates in any hash.
- Bumped to 2 by this script on first successful migration.
- Bumped again by scripts/rebase_external_events.py for the rebase boundary.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mvm.state.db import DEFAULT_DB_PATH, get_conn, transaction  # noqa: E402
from mvm.state.hash_seed import hash_seed  # noqa: E402

# Reuse the cast definition + helpers from bootstrap so both paths converge.
sys.path.insert(0, str(ROOT / "scripts"))
from bootstrap_genesis import (  # noqa: E402
    DEFAULT_PERSONALITY_CAST,
    LEGACY_PERSONALITY_NAMES,
    compute_external_events_fingerprint,
    load_lakers_fixture,
    pick_personality_cast,
)

log = logging.getLogger(__name__)


def _has_column(conn, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any((r[1] if not hasattr(r, "keys") else r["name"]) == column for r in rows)


def _has_table(conn, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row is not None


def apply_v3_schema_additions(conn) -> list[str]:
    """Apply additive schema additions a pre-Phase-1 DB is missing.

    All operations are idempotent: only runs ALTER/CREATE if the column/table
    isn't already present. Returns a list of human-readable change descriptions.
    """
    changes = []
    if not _has_column(conn, "named_monkeys", "personality_config"):
        conn.execute("ALTER TABLE named_monkeys ADD COLUMN personality_config TEXT")
        changes.append("named_monkeys.personality_config TEXT")
    if not _has_column(conn, "genesis_log", "external_events_fingerprint"):
        conn.execute("ALTER TABLE genesis_log ADD COLUMN external_events_fingerprint TEXT")
        changes.append("genesis_log.external_events_fingerprint TEXT")
    if not _has_column(conn, "genesis_log", "cast_version"):
        conn.execute("ALTER TABLE genesis_log ADD COLUMN cast_version INTEGER NOT NULL DEFAULT 1")
        changes.append("genesis_log.cast_version INTEGER DEFAULT 1")
    if not _has_column(conn, "genesis_log", "personality_config_json"):
        conn.execute("ALTER TABLE genesis_log ADD COLUMN personality_config_json TEXT")
        changes.append("genesis_log.personality_config_json TEXT")
    if not _has_table(conn, "external_events"):
        conn.execute(
            "CREATE TABLE external_events ("
            "date TEXT NOT NULL, event_kind TEXT NOT NULL, outcome INTEGER NOT NULL, "
            "payload_json TEXT, PRIMARY KEY (date, event_kind))"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_external_events_kind_date "
            "ON external_events(event_kind, date)"
        )
        changes.append("external_events table + idx_external_events_kind_date")
    if not _has_table(conn, "external_events_rebase_log"):
        conn.execute(
            "CREATE TABLE external_events_rebase_log ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "rebased_at TEXT NOT NULL DEFAULT (datetime('now')), "
            "old_fingerprint TEXT, new_fingerprint TEXT NOT NULL, "
            "rows_added INTEGER NOT NULL DEFAULT 0, "
            "rows_removed INTEGER NOT NULL DEFAULT 0, "
            "reason TEXT NOT NULL)"
        )
        changes.append("external_events_rebase_log table")
    return changes


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    p.add_argument("--force", action="store_true", help="Re-run even if cast_version >= 2")
    p.add_argument("--dry-run", action="store_true", help="Print the plan but don't modify the DB")
    args = p.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    if not args.db.exists():
        log.error("No DB at %s — run scripts/bootstrap_genesis.py first.", args.db)
        return 2

    with get_conn(args.db) as conn:
        # On pre-Phase-1 DBs (no cast_version column, no external_events table),
        # apply the additive schema first so the rest of the migration can run.
        schema_changes = apply_v3_schema_additions(conn)
        if schema_changes:
            log.info("Applied v3 schema additions: %s", ", ".join(schema_changes))

        row = conn.execute(
            "SELECT cast_version, seed_string, n_monkeys FROM genesis_log WHERE id=1"
        ).fetchone()
        if row is None:
            log.error("genesis_log row id=1 missing — refusing to migrate without genesis context.")
            return 2

        # Tolerate pre-v3 schemas that lack cast_version (None means v1).
        cast_version = row["cast_version"] if row["cast_version"] is not None else 1
        seed_string = row["seed_string"]
        n_monkeys = row["n_monkeys"]

        if cast_version >= 2 and not args.force:
            log.info("cast_version=%d already; no migration needed. Pass --force to re-run.", cast_version)
            return 0

        log.info("Migrating cast_version=%d -> 2 (seed=%s, n_monkeys=%d)", cast_version, seed_string, n_monkeys)

        # Reproduce the genesis seed so we land on the SAME monkey IDs as a fresh bootstrap.
        rng = np.random.default_rng(seed=hash_seed("personality_pick", seed_string=seed_string))
        new_cast = pick_personality_cast(rng, n_monkeys)
        new_names = [name for _, name, _ in new_cast]
        log.info("New cast (%d): %s", len(new_cast), new_names)

        existing_legacy = conn.execute(
            f"SELECT name FROM named_monkeys WHERE name IN ({','.join('?' * len(LEGACY_PERSONALITY_NAMES))})",
            LEGACY_PERSONALITY_NAMES,
        ).fetchall()
        log.info("Found %d legacy personality rows to remove", len(existing_legacy))

        # Load fixture so external_events can be backfilled if currently empty.
        lakers_rows = load_lakers_fixture()
        events_existing = conn.execute(
            "SELECT COUNT(*) FROM external_events WHERE event_kind='lakers_game'"
        ).fetchone()[0]

        plan = {
            "delete_named_monkeys": len(existing_legacy),
            "delete_named_history": "all rows for legacy names",
            "insert_named_monkeys": len(new_cast),
            "external_events_lakers_existing": events_existing,
            "external_events_lakers_after": len(lakers_rows),
            "set_cast_version": 2,
        }
        log.info("Migration plan: %s", json.dumps(plan, indent=2))

        if args.dry_run:
            log.info("--dry-run: no changes made.")
            return 0

        with transaction(conn):
            placeholders = ",".join("?" * len(LEGACY_PERSONALITY_NAMES))
            conn.execute(
                f"DELETE FROM named_monkey_history WHERE name IN ({placeholders})",
                LEGACY_PERSONALITY_NAMES,
            )
            conn.execute(
                f"DELETE FROM named_monkeys WHERE name IN ({placeholders})",
                LEGACY_PERSONALITY_NAMES,
            )

            # Re-seed with the v3 cast. INSERT OR REPLACE to make --force idempotent.
            for mid, name, config in new_cast:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO named_monkeys (name, monkey_id, category, personality_config)
                    VALUES (?, ?, 'personality', ?)
                    """,
                    (name, int(mid), json.dumps(config, sort_keys=True)),
                )

            # Backfill external_events only if currently empty (the rebase script
            # is the sanctioned way to mutate already-populated rows).
            if events_existing == 0:
                conn.executemany(
                    """
                    INSERT INTO external_events (date, event_kind, outcome, payload_json)
                    VALUES (?, 'lakers_game', ?, ?)
                    """,
                    [
                        (r["date"], int(r["outcome"]), json.dumps(r["payload"], sort_keys=True))
                        for r in lakers_rows
                    ],
                )
                log.info("Seeded %d lakers_game rows into external_events", len(lakers_rows))

            fingerprint = compute_external_events_fingerprint(conn)
            cast_json = json.dumps(
                [{"name": n, "monkey_id": m, "config": c} for m, n, c in new_cast],
                sort_keys=True,
            )

            conn.execute(
                """
                UPDATE genesis_log
                SET cast_version=2,
                    external_events_fingerprint=?,
                    personality_config_json=?
                WHERE id=1
                """,
                (fingerprint, cast_json),
            )

        log.info("Migration complete. cast_version=2, fingerprint=%s...", fingerprint[:12])
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
