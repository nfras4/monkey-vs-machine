import { getAiEquity, getLastTick, getRecentAggregates } from "$lib/server/d1";
import type { PageServerLoad } from "./$types";

// Returns the most recent US trading day we'd expect a tick for, given the
// server clock. Heuristic: today's date in US/Eastern if a US weekday has
// finished (>= 16:30 ET), otherwise the most recent prior weekday.
// Cheap approximation — exact NYSE-holiday calendar isn't worth the dep.
function expectedLatestTradingDate(now = new Date()): string {
  // Convert to US/Eastern via Intl rather than pulling in a tz lib.
  const fmt = new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/New_York",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    hour12: false,
  });
  const parts = Object.fromEntries(fmt.formatToParts(now).map((p) => [p.type, p.value]));
  const y = Number(parts.year), m = Number(parts.month), d = Number(parts.day), h = Number(parts.hour);

  let trading = new Date(Date.UTC(y, m - 1, d));
  // If market hasn't closed yet (heuristic: before 17:00 ET to give the tick time to run), step back a day.
  if (h < 17) trading.setUTCDate(trading.getUTCDate() - 1);
  // Walk back to the most recent weekday.
  while (trading.getUTCDay() === 0 || trading.getUTCDay() === 6) {
    trading.setUTCDate(trading.getUTCDate() - 1);
  }
  return trading.toISOString().slice(0, 10);
}

function weekdaysBetween(a: string, b: string): number {
  // Inclusive of neither endpoint — strictly the weekdays strictly between a and b.
  if (a >= b) return 0;
  let count = 0;
  const cur = new Date(`${a}T00:00:00Z`);
  const end = new Date(`${b}T00:00:00Z`);
  cur.setUTCDate(cur.getUTCDate() + 1);
  while (cur < end) {
    const dow = cur.getUTCDay();
    if (dow !== 0 && dow !== 6) count++;
    cur.setUTCDate(cur.getUTCDate() + 1);
  }
  return count;
}

export const load: PageServerLoad = async ({ platform, setHeaders }) => {
  setHeaders({ "cache-control": "public, max-age=60" });
  const db = platform!.env.DB;
  const [aggregates, aiEquity, lastTick] = await Promise.all([
    getRecentAggregates(db, 365),
    getAiEquity(db, 365),
    getLastTick(db),
  ]);

  const expected = expectedLatestTradingDate();
  let freshness: { state: "fresh" | "stale" | "missing"; daysBehind: number; expected: string };
  if (!lastTick) {
    freshness = { state: "missing", daysBehind: 0, expected };
  } else if (lastTick.date >= expected) {
    freshness = { state: "fresh", daysBehind: 0, expected };
  } else {
    const behind = 1 + weekdaysBetween(lastTick.date, expected);
    freshness = { state: "stale", daysBehind: behind, expected };
  }

  return { aggregates, aiEquity, lastTick, freshness };
};
