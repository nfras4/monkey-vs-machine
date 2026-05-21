"""Schema test for the committed Lakers fixture.

Catches drift where data/fixtures/lakers_2023_2025.json gains/loses fields,
gets outcome values outside {0,1}, or has malformed dates. Runs in CI before
bootstrap_genesis.py is ever invoked, so a bad fixture fails the build, not
a downstream tick.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = REPO_ROOT / "data" / "fixtures" / "lakers_2023_2025.json"
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@pytest.fixture(scope="module")
def fixture_rows() -> list[dict]:
    assert FIXTURE_PATH.exists(), f"Fixture missing at {FIXTURE_PATH}"
    with FIXTURE_PATH.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def test_fixture_nonempty(fixture_rows):
    assert len(fixture_rows) > 0


def test_fixture_each_row_has_required_keys(fixture_rows):
    required = {"date", "outcome", "payload"}
    for i, row in enumerate(fixture_rows):
        missing = required - row.keys()
        assert not missing, f"Row {i} missing keys: {missing}"


def test_fixture_outcome_is_binary(fixture_rows):
    for i, row in enumerate(fixture_rows):
        assert row["outcome"] in (0, 1), f"Row {i}: outcome={row['outcome']}"


def test_fixture_dates_iso(fixture_rows):
    for i, row in enumerate(fixture_rows):
        assert ISO_DATE.match(row["date"]), f"Row {i}: date={row['date']!r}"


def test_fixture_payload_is_dict(fixture_rows):
    for i, row in enumerate(fixture_rows):
        assert isinstance(row["payload"], dict), f"Row {i}: payload type={type(row['payload']).__name__}"


def test_fixture_dates_sorted_ascending(fixture_rows):
    """The fixture must be in date-ascending order so the fingerprint is stable."""
    dates = [r["date"] for r in fixture_rows]
    assert dates == sorted(dates), "Fixture rows must be sorted by date ascending"


def test_fixture_no_duplicate_games(fixture_rows):
    """One game per (date, opp) — protects against ESPN returning the same game twice."""
    keys = [(r["date"], r["payload"].get("opp")) for r in fixture_rows]
    assert len(keys) == len(set(keys)), "Duplicate (date, opp) in fixture"


def test_fixture_win_rate_plausible(fixture_rows):
    """Sanity check: Lakers regular-season win rate should be between 30% and 75%."""
    n = len(fixture_rows)
    wins = sum(r["outcome"] for r in fixture_rows)
    rate = wins / n
    assert 0.30 <= rate <= 0.75, f"Win rate {rate:.2f} ({wins}/{n}) looks wrong"
