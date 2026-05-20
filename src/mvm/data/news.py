"""Live news headlines via yfinance.

yfinance only exposes the most recent ~N headlines per ticker (no historical archive),
so this module is used by the dashboard's "today" tab only, never the backtest.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, List

import yfinance as yf

log = logging.getLogger(__name__)


def fetch_recent_headlines(ticker: str, limit: int = 10) -> List[Dict]:
    """Return a list of {title, publisher, link, published_at} for one ticker."""
    try:
        items = yf.Ticker(ticker).news or []
    except Exception as e:
        log.warning("news fetch failed for %s: %s", ticker, e)
        return []
    out = []
    for item in items[:limit]:
        # yfinance schema changed over versions; coalesce known shapes.
        content = item.get("content", item)
        title = content.get("title") or item.get("title")
        if not title:
            continue
        publisher = (
            content.get("provider", {}).get("displayName")
            if isinstance(content.get("provider"), dict)
            else item.get("publisher")
        )
        link = (
            content.get("canonicalUrl", {}).get("url")
            if isinstance(content.get("canonicalUrl"), dict)
            else item.get("link")
        )
        published = content.get("pubDate") or item.get("providerPublishTime")
        if isinstance(published, (int, float)):
            published = datetime.fromtimestamp(published, tz=timezone.utc).isoformat()
        out.append(
            {
                "title": title,
                "publisher": publisher or "",
                "link": link or "",
                "published_at": str(published) if published else "",
            }
        )
    return out


def fetch_headlines_for(tickers: List[str], limit_per_ticker: int = 5) -> Dict[str, List[Dict]]:
    return {t: fetch_recent_headlines(t, limit=limit_per_ticker) for t in tickers}
