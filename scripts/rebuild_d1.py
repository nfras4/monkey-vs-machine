"""CLI: replay the egress payload for every successful tick in SQLite from --since.

Used when D1 has been wiped or migrated. Calls push_to_d1's payload builder
+ HTTP path per date. Idempotent on the receiving side.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from push_to_d1 import _us_today_date, build_payload, post_with_retry  # noqa: E402

from mvm.state.db import DEFAULT_DB_PATH, get_conn  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--since", required=True, help="YYYY-MM-DD inclusive")
    parser.add_argument("--until", default=None)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    pages_url = os.environ.get("PAGES_URL", "").rstrip("/")
    token = os.environ.get("MVM_INGEST_TOKEN", "")
    if not pages_url or not token:
        logging.error("PAGES_URL and MVM_INGEST_TOKEN env vars are required")
        return 2

    url = f"{pages_url}/admin/ingest"

    # End-date defaults to today US/Eastern to match the rest of the toolchain;
    # using UTC here would skip ticks for "today" between 00:00–13:00 ET on the
    # current day (after midnight UTC but before US close).
    end = args.until or _us_today_date()
    with get_conn(args.db, enforce_single_writer=False) as conn:
        rows = conn.execute(
            "SELECT date FROM ticks WHERE status='ok' AND date BETWEEN ? AND ? ORDER BY date",
            (args.since, end),
        ).fetchall()

        if not rows:
            logging.info("No ok ticks in range [%s, %s] — nothing to rebuild", args.since, end)
            return 0

        ok = 0
        for r in rows:
            d = r["date"]
            payload = build_payload(conn, d)
            code, body, attempts = post_with_retry(url, token, payload)
            conn.execute(
                """
                INSERT INTO d1_egress_log (date, status, attempts, response_code, error)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    d,
                    "ok" if code and 200 <= code < 300 else "failed",
                    attempts,
                    code,
                    None if code and 200 <= code < 300 else str(body)[:400],
                ),
            )
            if code and 200 <= code < 300:
                ok += 1
            else:
                logging.error("Push failed for %s — stopping. err=%s", d, body)
                return 1
        logging.info("Replayed %d/%d ticks", ok, len(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
