"""Four-case NULL dispatch for external_events_fingerprint, exercised directly
against the guard helper (no bootstrap needed — uses an in-memory DB).
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mvm.runner_tick import DeterminismError, _check_external_events_fingerprint  # noqa: E402


def _seed_db(*, stored_fp: str | None, events: list[tuple[str, str, int]]) -> sqlite3.Connection:
    """Stand up a minimal DB shape with just the columns the guard reads."""
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute(
        "CREATE TABLE genesis_log (id INTEGER PRIMARY KEY, external_events_fingerprint TEXT)"
    )
    c.execute(
        "CREATE TABLE external_events (date TEXT, event_kind TEXT, outcome INTEGER, "
        "PRIMARY KEY (date, event_kind))"
    )
    c.execute("INSERT INTO genesis_log (id, external_events_fingerprint) VALUES (1, ?)", (stored_fp,))
    for d, k, o in events:
        c.execute("INSERT INTO external_events (date, event_kind, outcome) VALUES (?, ?, ?)", (d, k, o))
    return c


def _compute(conn) -> str:
    from mvm.runner_tick import _compute_external_events_fingerprint
    return _compute_external_events_fingerprint(conn)


def test_null_fingerprint_with_empty_events_is_permissive():
    """Pre-Phase-1 prod DB shape: NULL fingerprint, empty external_events. Tick must proceed."""
    conn = _seed_db(stored_fp=None, events=[])
    _check_external_events_fingerprint(conn)  # must not raise


def test_null_fingerprint_with_rows_is_fatal():
    """Half-migrated DB: NULL fingerprint but rows present. Must raise."""
    conn = _seed_db(stored_fp=None, events=[("2024-01-01", "lakers_game", 1)])
    with pytest.raises(DeterminismError) as exc_info:
        _check_external_events_fingerprint(conn)
    assert "NULL" in str(exc_info.value)


def test_matching_fingerprint_proceeds():
    events = [("2024-01-01", "lakers_game", 1), ("2024-01-03", "lakers_game", 0)]
    # Seed with placeholder, then compute and patch.
    conn = _seed_db(stored_fp="placeholder", events=events)
    real_fp = _compute(conn)
    conn.execute("UPDATE genesis_log SET external_events_fingerprint=? WHERE id=1", (real_fp,))
    _check_external_events_fingerprint(conn)  # must not raise


def test_mismatched_fingerprint_raises():
    conn = _seed_db(stored_fp="deadbeef" * 8, events=[("2024-01-01", "lakers_game", 1)])
    with pytest.raises(DeterminismError) as exc_info:
        _check_external_events_fingerprint(conn)
    assert "mismatch" in str(exc_info.value)
