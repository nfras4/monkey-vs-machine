"""Tick-time date helpers shared across runner + scripts.

Single source of truth for "what date is today in the tick's reference frame"
so run_tick.py, catchup.py, and push_to_d1.py don't drift on the timezone or
fallback semantics.
"""
from __future__ import annotations

from datetime import datetime, timezone


def us_today_date() -> str:
    """Today's date in US/Eastern, formatted YYYY-MM-DD.

    Daily bars are stamped to the US/Eastern close, so the "current trading
    date" is always evaluated in ET regardless of where the script runs.
    Falls back to UTC if zoneinfo can't load the IANA database (rare on
    bare/embedded Python builds).
    """
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    except Exception:  # noqa: BLE001
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")
