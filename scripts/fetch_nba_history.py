"""Fetch + cache historical Lakers regular-season results for Lakers Joe.

Two modes:

1. **Default (read-only verify)**: load data/fixtures/lakers_2023_2025.json,
   validate every row matches the normalised shape, exit 0. Used by CI and
   bootstrap to confirm the fixture is loadable.

2. **--refresh**: hit balldontlie.io (free tier, no auth) for Lakers (team_id=14)
   seasons 2023/2024/2025, transform to normalised
   {date, outcome, payload_json} rows, write to the fixture, then re-verify.
   Refuses to run if state.db already has external_events_fingerprint set
   unless --rebase is passed (forward to rebase_external_events.py).

The fixture lives at data/fixtures/lakers_2023_2025.json in normalised form so
the bootstrap consumer schema is stable even if balldontlie's response shape
changes. Determinism boundary: this script is provisioning-time, never tick-time.
"""
from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mvm.state.db import DEFAULT_DB_PATH  # noqa: E402

log = logging.getLogger(__name__)

FIXTURE_PATH = ROOT / "data" / "fixtures" / "lakers_2023_2025.json"
# ESPN team_id for Los Angeles Lakers. (balldontlie went freemium and now needs
# an API key, so we use ESPN's no-auth schedule API instead.)
ESPN_LAKERS_TEAM_ID = 13
# ESPN season parameter is END year of the NBA season: 2024 = 2023-24 etc.
ESPN_SEASONS = [2024, 2025, 2026]
ESPN_SCHEDULE_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{team_id}/schedule"
# seasontype 2 = regular season (1 = preseason, 3 = postseason)
ESPN_SEASONTYPE_REGULAR = 2


def verify_fixture(rows: list[dict[str, Any]]) -> None:
    """Raise if any row doesn't match the normalised shape."""
    required = {"date", "outcome", "payload"}
    for i, row in enumerate(rows):
        missing = required - row.keys()
        if missing:
            raise ValueError(f"row {i}: missing keys {missing}; got {list(row.keys())}")
        if row["outcome"] not in (0, 1):
            raise ValueError(f"row {i} on {row['date']}: outcome must be 0 or 1, got {row['outcome']}")
        if not isinstance(row["date"], str) or len(row["date"]) != 10:
            raise ValueError(f"row {i}: date must be YYYY-MM-DD, got {row['date']!r}")
        if not isinstance(row["payload"], dict):
            raise ValueError(f"row {i}: payload must be a dict, got {type(row['payload']).__name__}")


def load_fixture() -> list[dict[str, Any]]:
    if not FIXTURE_PATH.exists():
        raise FileNotFoundError(
            f"Fixture not found at {FIXTURE_PATH}. Run with --refresh to fetch it."
        )
    with FIXTURE_PATH.open("r", encoding="utf-8") as fh:
        rows = json.load(fh)
    verify_fixture(rows)
    return rows


def fetch_live() -> list[dict[str, Any]]:
    """Hit ESPN's no-auth schedule API and normalise the response.

    ESPN returns games keyed by event_id. Each event has a competitions[0] with
    a competitors[] of length 2 (home + away). Outcome = 1 iff the Lakers'
    competitor has winner=True. We filter to regular-season + completed games.
    """
    try:
        import requests  # local import so the read-only path doesn't need requests
    except ImportError as e:
        raise RuntimeError("requests is required for --refresh; pip install requests") from e

    rows: list[dict[str, Any]] = []
    url = ESPN_SCHEDULE_URL.format(team_id=ESPN_LAKERS_TEAM_ID)
    for season in ESPN_SEASONS:
        params = {"season": season, "seasontype": ESPN_SEASONTYPE_REGULAR}
        resp = requests.get(url, params=params, timeout=20)
        resp.raise_for_status()
        payload = resp.json()
        season_count = 0
        for event in payload.get("events", []):
            comp = (event.get("competitions") or [{}])[0]
            status = comp.get("status", {}).get("type", {}).get("completed")
            if not status:
                continue  # game not yet played
            # ESPN's date is UTC. Convert to US/Eastern so late-night tipoffs
            # don't collide with the next day's game (e.g. 02:30 UTC = 22:30 ET prev day).
            iso = event["date"].replace("Z", "+00:00")
            dt_utc = datetime.fromisoformat(iso).astimezone(timezone.utc)
            dt_et = dt_utc.astimezone(ZoneInfo("America/New_York"))
            date_str = dt_et.strftime("%Y-%m-%d")
            competitors = comp.get("competitors") or []
            lakers = next((c for c in competitors if c.get("team", {}).get("abbreviation") == "LAL"), None)
            opp = next((c for c in competitors if c.get("team", {}).get("abbreviation") != "LAL"), None)
            if not lakers or not opp:
                continue
            lakers_score = int(float(lakers.get("score", {}).get("value", 0)))
            opp_score = int(float(opp.get("score", {}).get("value", 0)))
            outcome = 1 if lakers.get("winner") is True else 0
            rows.append({
                "date": date_str,
                "outcome": outcome,
                "payload": {
                    "opp": opp.get("team", {}).get("abbreviation"),
                    "score": f"{lakers_score}-{opp_score}",
                    "home": lakers.get("homeAway") == "home",
                    "season": season,
                },
            })
            season_count += 1
        log.info("Season %d (ESPN end-year): %d completed regular-season games", season, season_count)

    rows.sort(key=lambda r: r["date"])
    # De-dup by (date, opp) just in case ESPN returns the same game twice from different seasons.
    seen = set()
    unique: list[dict[str, Any]] = []
    for r in rows:
        key = (r["date"], r["payload"]["opp"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(r)
    return unique


def write_fixture(rows: list[dict[str, Any]]) -> None:
    FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with FIXTURE_PATH.open("w", encoding="utf-8") as fh:
        json.dump(rows, fh, indent=2)
        fh.write("\n")
    log.info("Wrote %d rows to %s", len(rows), FIXTURE_PATH)


def state_db_has_fingerprint(db: Path) -> bool:
    if not db.exists():
        return False
    try:
        conn = sqlite3.connect(db)
        row = conn.execute("SELECT external_events_fingerprint FROM genesis_log WHERE id=1").fetchone()
        return bool(row and row[0])
    except sqlite3.OperationalError:
        # column doesn't exist yet (pre-v3 schema) -> treat as unfingerprinted
        return False


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--refresh", action="store_true", help="Hit balldontlie.io and overwrite the fixture")
    p.add_argument("--rebase", action="store_true", help="Allow --refresh even when state.db already has a fingerprint (forwards to rebase_external_events.py)")
    p.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    args = p.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    if args.refresh:
        if state_db_has_fingerprint(args.db) and not args.rebase:
            log.error(
                "state.db already has external_events_fingerprint set. "
                "Refusing to silently re-fetch. Pass --rebase to invoke rebase_external_events.py."
            )
            return 2
        rows = fetch_live()
        verify_fixture(rows)
        write_fixture(rows)
        log.info("Fixture refresh complete: %d rows (%d wins)", len(rows), sum(r["outcome"] for r in rows))
        if args.rebase:
            log.warning("--rebase requested: would invoke scripts/rebase_external_events.py (not yet implemented in Phase 1)")
        return 0

    # Default: read-only verify
    rows = load_fixture()
    log.info("Fixture OK: %d rows, %d wins", len(rows), sum(r["outcome"] for r in rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
