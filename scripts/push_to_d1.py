"""CLI: push a single tick's published rows to Cloudflare D1 via the Pages Function ingest endpoint.

Reads the local SQLite source-of-truth for `--date` and POSTs the publish
payload to ${PAGES_URL}/admin/ingest with Authorization: Bearer ${MVM_INGEST_TOKEN}.

Idempotent on the receiving side (INSERT OR REPLACE in the Pages Function).
Retries with exponential backoff up to 5 attempts.

Environment variables:
    PAGES_URL          e.g. https://mvm-dashboard.pages.dev
    MVM_INGEST_TOKEN   bearer token (matches Pages Function env binding)
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests


def _us_today_date() -> str:
    """Same convention as run_tick.py — US/Eastern."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    except Exception:  # noqa: BLE001
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mvm.state.db import DEFAULT_DB_PATH, get_conn  # noqa: E402

PUBLISH_SCHEMA_VERSION = 2


def build_payload(conn, date: str) -> dict:
    agg = conn.execute("SELECT * FROM daily_aggregates WHERE date=?", (date,)).fetchone()
    if agg is None:
        raise RuntimeError(f"No daily_aggregates row for {date} — has the tick run yet?")
    ai_history = conn.execute(
        "SELECT * FROM ai_model_history WHERE date=?", (date,)
    ).fetchall()
    ai_portfolios = conn.execute(
        "SELECT * FROM ai_portfolio_history WHERE date=?", (date,)
    ).fetchall()
    ai_equity = conn.execute(
        "SELECT * FROM ai_portfolio_equity WHERE date=?", (date,)
    ).fetchall()
    # v2: JOIN named_monkeys to attach each row's personality_config so the
    # dashboard can render character cards without a second table on D1.
    named = conn.execute(
        """
        SELECT h.date, h.name, h.monkey_id, h.category, h.equity,
               m.personality_config
        FROM named_monkey_history h
        LEFT JOIN named_monkeys m ON m.name = h.name
        WHERE h.date = ?
        """,
        (date,),
    ).fetchall()
    tick = conn.execute("SELECT * FROM ticks WHERE date=?", (date,)).fetchone()

    # v2: ship the full frozen external_events table on every push. INSERT OR
    # IGNORE on the receive side means duplicates are no-ops; the 247-row
    # Lakers fixture is well within D1 batch limits and the wire cost is small
    # (~30KB compressed). Genesis fingerprint guarantees content immutability.
    external_events = conn.execute(
        "SELECT date, event_kind, outcome, payload_json FROM external_events "
        "ORDER BY date, event_kind"
    ).fetchall()

    return {
        "publish_schema_version": PUBLISH_SCHEMA_VERSION,
        "date": date,
        "daily_aggregates": dict(agg) if agg else None,
        "ai_history": [dict(r) for r in ai_history],
        "ai_portfolios": [dict(r) for r in ai_portfolios],
        "ai_equity": [dict(r) for r in ai_equity],
        "named_monkey_history": [dict(r) for r in named],
        "tick": dict(tick) if tick else None,
        "external_events": [dict(r) for r in external_events],
    }


def post_with_retry(url: str, token: str, payload: dict, max_attempts: int = 5):
    delay = 1.5
    last_err = None
    for attempt in range(1, max_attempts + 1):
        try:
            resp = requests.post(
                url,
                data=json.dumps(payload),
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                timeout=30,
            )
            if 200 <= resp.status_code < 300:
                return resp.status_code, resp.text, attempt
            last_err = f"HTTP {resp.status_code}: {resp.text[:200]}"
        except requests.RequestException as e:
            last_err = str(e)
        logging.warning("ingest attempt %d/%d failed: %s", attempt, max_attempts, last_err)
        if attempt < max_attempts:
            time.sleep(delay)
            delay *= 2
    return None, last_err, max_attempts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None, help="YYYY-MM-DD (defaults to today US/Eastern)")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    args = parser.parse_args()
    if args.date is None:
        args.date = _us_today_date()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    pages_url = os.environ.get("PAGES_URL", "").rstrip("/")
    token = os.environ.get("MVM_INGEST_TOKEN", "")
    if not pages_url or not token:
        logging.error("PAGES_URL and MVM_INGEST_TOKEN environment variables are required")
        return 2

    url = f"{pages_url}/admin/ingest"

    with get_conn(args.db, enforce_single_writer=False) as conn:
        payload = build_payload(conn, args.date)

        code, body, attempts = post_with_retry(url, token, payload)
        # conn is in autocommit (isolation_level=None) so the execute commits
        # immediately. No `with conn:` wrapper needed.
        conn.execute(
            """
            INSERT INTO d1_egress_log (date, status, attempts, response_code, error)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                args.date,
                "ok" if code and 200 <= code < 300 else "failed",
                attempts,
                code,
                None if code and 200 <= code < 300 else str(body)[:400],
            ),
        )

    if code and 200 <= code < 300:
        logging.info("Pushed %s in %d attempts (HTTP %s)", args.date, attempts, code)
        return 0
    logging.error("Push failed: %s", body)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
