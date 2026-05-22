// Typed read-only D1 query layer for the dashboard.
// Model-aware (council v2.2): every AI query takes a model_id, defaulting to 'hgb_v1'.
// Switching champions in v2 is a one-line change here.

import type { D1Database } from "@cloudflare/workers-types";

export const CHAMPION_MODEL_ID = "hgb_v1";

export type AggregateRow = {
  date: string;
  monkey_mean: number;
  monkey_median: number;
  monkey_p5: number;
  monkey_p25: number;
  monkey_p75: number;
  monkey_p95: number;
  monkey_best: number;
  monkey_worst: number;
  n_monkeys: number;
  n_monkeys_above_starting: number;
  spy_equity: number | null;
};

export type AiHistoryRow = {
  date: string;
  model_id: string;
  model_family: string;
  config_json: string;
  diagnostics_json: string;
  runtime_fingerprint: string;
  features_hash: string;
  train_window_end: string;
  training_seconds: number | null;
};

export type AiPortfolioRow = { date: string; ticker: string; model_id: string; weight: number };
export type AiEquityRow = { date: string; model_id: string; equity: number; daily_return: number | null };
export type NamedMonkeyRow = {
  date: string;
  name: string;
  monkey_id: number;
  category: string;
  equity: number;
  personality_config: string | null;
};
export type TickRow = { date: string; status: string; duration_seconds: number | null; note: string | null; pushed_at: string };

export async function getRecentAggregates(db: D1Database, days = 365): Promise<AggregateRow[]> {
  const { results } = await db
    .prepare("SELECT * FROM daily_aggregates ORDER BY date DESC LIMIT ?")
    .bind(days)
    .all<AggregateRow>();
  return (results ?? []).reverse();
}

export async function getAiEquity(db: D1Database, days = 365, modelId = CHAMPION_MODEL_ID): Promise<AiEquityRow[]> {
  const { results } = await db
    .prepare("SELECT * FROM ai_equity WHERE model_id=? ORDER BY date DESC LIMIT ?")
    .bind(modelId, days)
    .all<AiEquityRow>();
  return (results ?? []).reverse();
}

export async function getAiHoldings(db: D1Database, modelId = CHAMPION_MODEL_ID): Promise<AiPortfolioRow[]> {
  const latest = await db
    .prepare("SELECT MAX(date) AS d FROM ai_portfolios WHERE model_id=?")
    .bind(modelId)
    .first<{ d: string | null }>();
  if (!latest?.d) return [];
  const { results } = await db
    .prepare("SELECT * FROM ai_portfolios WHERE model_id=? AND date=? ORDER BY weight DESC")
    .bind(modelId, latest.d)
    .all<AiPortfolioRow>();
  return results ?? [];
}

export async function getAiHistory(db: D1Database, days = 90, modelId = CHAMPION_MODEL_ID): Promise<AiHistoryRow[]> {
  const { results } = await db
    .prepare("SELECT * FROM ai_history WHERE model_id=? ORDER BY date DESC LIMIT ?")
    .bind(modelId, days)
    .all<AiHistoryRow>();
  return (results ?? []).reverse();
}

export async function getAiModelIds(db: D1Database): Promise<string[]> {
  const { results } = await db
    .prepare("SELECT DISTINCT model_id FROM ai_history ORDER BY model_id")
    .all<{ model_id: string }>();
  return (results ?? []).map((r) => r.model_id);
}

export async function getNamedMonkeys(db: D1Database): Promise<NamedMonkeyRow[]> {
  const latest = await db
    .prepare("SELECT MAX(date) AS d FROM named_monkey_history")
    .first<{ d: string | null }>();
  if (!latest?.d) return [];
  const { results } = await db
    .prepare("SELECT * FROM named_monkey_history WHERE date=? ORDER BY name")
    .bind(latest.d)
    .all<NamedMonkeyRow>();
  return results ?? [];
}

/** Last N trading dates of named-monkey history, grouped by name. One DB
 *  subrequest. Used by /monkeys to render sparklines per character card. */
export async function getRecentNamedMonkeyHistory(
  db: D1Database,
  days = 21,
): Promise<Record<string, NamedMonkeyRow[]>> {
  // Pull rows from the last `days` distinct dates. Subquery avoids needing
  // to compute the cutoff date in TS (handles weekends/holidays correctly).
  const { results } = await db
    .prepare(
      `SELECT * FROM named_monkey_history
       WHERE date IN (
         SELECT date FROM named_monkey_history
         GROUP BY date ORDER BY date DESC LIMIT ?
       )
       ORDER BY name, date`,
    )
    .bind(days)
    .all<NamedMonkeyRow>();
  const grouped: Record<string, NamedMonkeyRow[]> = {};
  for (const r of results ?? []) {
    (grouped[r.name] ??= []).push(r);
  }
  return grouped;
}

export async function getNamedMonkeyHistory(db: D1Database, name: string): Promise<NamedMonkeyRow[]> {
  const { results } = await db
    .prepare("SELECT * FROM named_monkey_history WHERE name=? ORDER BY date")
    .bind(name)
    .all<NamedMonkeyRow>();
  return results ?? [];
}

export async function getLastTick(db: D1Database): Promise<TickRow | null> {
  return await db
    .prepare("SELECT * FROM tick_log ORDER BY date DESC LIMIT 1")
    .first<TickRow>();
}

// === Daily insights ========================================================
// Server-side readout of "what happened on this tick". Combines portfolio
// rotation, model diagnostics, the AI's daily return + percentile rank vs
// the 100k monkey pack, and any named-monkey delta worth surfacing.
// Reuses existing tables; no schema changes.

export type FeatureImportance = { feature: string; importance: number };

export type DailyInsight = {
  date: string;
  /** Holdings rotation: which tickers stayed, which dropped, which were added. */
  rotation: {
    kept: number;
    out_count: number;
    in_count: number;
    out: string[];
    in: string[];
  };
  /** Top 3 features by permutation importance, latest train. */
  top_features: FeatureImportance[];
  /** AI portfolio % return for this day; null on the very first tick. */
  ai_daily_return: number | null;
  /** Implied SPY % return today (delta over yesterday's spy_equity). */
  spy_daily_return: number | null;
  /** AI's percentile rank vs the 100k-monkey distribution (0-100). */
  ai_percentile: number | null;
  /** AI equity today, for compactness. */
  ai_equity: number | null;
  /** Best-performing personality monkey today (largest +ve daily delta). */
  best_personality: {
    name: string;
    delta_pct: number;
    equity: number;
  } | null;
  /** Lakers Joe outcome on this date (if event present). */
  lakers: { outcome: "win" | "loss"; delta: number } | null;
};

// Feature order in the diagnostics array mirrors src/mvm/features.py's
// engineered-feature panel. Keep this in sync with the engine.
const FEATURE_COLS = ["ret_1d", "ret_5d", "ret_20d", "vol_20", "vol_60", "rsi_14", "macd_sig", "vol_z", "abn_ret"];

function pctRank(equity: number, agg: AggregateRow): number {
  // Lerp between known percentile breakpoints for a rough rank. Better than
  // pretending we have the full equity vector on D1.
  if (equity <= agg.monkey_p5) return 5 * (equity / agg.monkey_p5);
  if (equity <= agg.monkey_p25) return 5 + ((equity - agg.monkey_p5) / (agg.monkey_p25 - agg.monkey_p5)) * 20;
  if (equity <= agg.monkey_median) return 25 + ((equity - agg.monkey_p25) / (agg.monkey_median - agg.monkey_p25)) * 25;
  if (equity <= agg.monkey_p75) return 50 + ((equity - agg.monkey_median) / (agg.monkey_p75 - agg.monkey_median)) * 25;
  if (equity <= agg.monkey_p95) return 75 + ((equity - agg.monkey_p75) / (agg.monkey_p95 - agg.monkey_p75)) * 20;
  if (equity <= agg.monkey_best) return 95 + ((equity - agg.monkey_p95) / (agg.monkey_best - agg.monkey_p95)) * 5;
  return 100;
}

/** Insight for the latest tick (or a specific date if passed). */
export async function getDailyInsight(
  db: D1Database,
  date?: string,
  modelId = CHAMPION_MODEL_ID,
): Promise<DailyInsight | null> {
  // 1. Resolve target date
  const target = date
    ? date
    : (await db.prepare("SELECT MAX(date) AS d FROM tick_log").first<{ d: string | null }>())?.d;
  if (!target) return null;

  // 2. Prior tick (for rotation diff + SPY return)
  const prior = await db
    .prepare("SELECT MAX(date) AS d FROM tick_log WHERE date < ?")
    .bind(target)
    .first<{ d: string | null }>();
  const priorDate = prior?.d ?? null;

  // 3. Portfolio rotation
  const todayPort = await db
    .prepare("SELECT ticker FROM ai_portfolios WHERE date=? AND model_id=?")
    .bind(target, modelId)
    .all<{ ticker: string }>();
  const todayTickers = new Set((todayPort.results ?? []).map((r) => r.ticker));
  let outTickers: string[] = [];
  let inTickers: string[] = [];
  let kept = 0;
  if (priorDate) {
    const priorPort = await db
      .prepare("SELECT ticker FROM ai_portfolios WHERE date=? AND model_id=?")
      .bind(priorDate, modelId)
      .all<{ ticker: string }>();
    const priorTickers = new Set((priorPort.results ?? []).map((r) => r.ticker));
    outTickers = [...priorTickers].filter((t) => !todayTickers.has(t)).sort();
    inTickers = [...todayTickers].filter((t) => !priorTickers.has(t)).sort();
    kept = [...priorTickers].filter((t) => todayTickers.has(t)).length;
  }

  // 4. Top features from diagnostics
  let top_features: FeatureImportance[] = [];
  const aiHist = await db
    .prepare("SELECT diagnostics_json FROM ai_history WHERE date=? AND model_id=?")
    .bind(target, modelId)
    .first<{ diagnostics_json: string | null }>();
  if (aiHist?.diagnostics_json) {
    try {
      const d = JSON.parse(aiHist.diagnostics_json);
      const imps: number[] = d?.feature_importances ?? [];
      top_features = FEATURE_COLS
        .map((f, i) => ({ feature: f, importance: imps[i] ?? 0 }))
        .sort((a, b) => b.importance - a.importance)
        .slice(0, 3);
    } catch {
      /* malformed json: surface no features rather than crash */
    }
  }

  // 5. AI daily return + equity
  const aiEq = await db
    .prepare("SELECT equity, daily_return FROM ai_equity WHERE date=? AND model_id=?")
    .bind(target, modelId)
    .first<{ equity: number; daily_return: number | null }>();
  const ai_equity = aiEq?.equity ?? null;
  const ai_daily_return = aiEq?.daily_return ?? null;

  // 6. SPY implied daily return
  let spy_daily_return: number | null = null;
  if (priorDate) {
    const ags = await db
      .prepare("SELECT date, spy_equity FROM daily_aggregates WHERE date IN (?, ?)")
      .bind(target, priorDate)
      .all<{ date: string; spy_equity: number | null }>();
    const byDate = Object.fromEntries((ags.results ?? []).map((r) => [r.date, r.spy_equity]));
    const t = byDate[target];
    const y = byDate[priorDate];
    if (t != null && y != null && y > 0) spy_daily_return = t / y - 1;
  }

  // 7. AI percentile vs the monkey pack
  let ai_percentile: number | null = null;
  const aggToday = await db
    .prepare("SELECT * FROM daily_aggregates WHERE date=?")
    .bind(target)
    .first<AggregateRow>();
  if (aggToday && ai_equity != null) {
    ai_percentile = pctRank(ai_equity, aggToday);
  }

  // 8. Best personality monkey today (largest day-over-day % gain)
  let best_personality: DailyInsight["best_personality"] = null;
  if (priorDate) {
    const namedRows = await db
      .prepare(
        `SELECT name, equity, date FROM named_monkey_history
         WHERE category='personality' AND date IN (?, ?)`,
      )
      .bind(target, priorDate)
      .all<{ name: string; equity: number; date: string }>();
    const byName = new Map<string, { today?: number; prior?: number }>();
    for (const r of namedRows.results ?? []) {
      const slot = byName.get(r.name) ?? {};
      if (r.date === target) slot.today = r.equity;
      else slot.prior = r.equity;
      byName.set(r.name, slot);
    }
    let bestName: string | null = null;
    let bestDelta = -Infinity;
    let bestEquity = 0;
    for (const [name, { today, prior }] of byName) {
      if (today == null || prior == null || prior <= 0) continue;
      const d = (today - prior) / prior;
      if (d > bestDelta) {
        bestDelta = d;
        bestName = name;
        bestEquity = today;
      }
    }
    if (bestName && bestDelta > -Infinity) {
      best_personality = { name: bestName, delta_pct: bestDelta * 100, equity: bestEquity };
    }
  }

  // 9. Lakers Joe — was there a game today?
  let lakers: DailyInsight["lakers"] = null;
  const lakersRow = await db
    .prepare("SELECT outcome FROM external_events WHERE date=? AND event_kind='lakers_game'")
    .bind(target)
    .first<{ outcome: number }>();
  if (lakersRow) {
    const win = lakersRow.outcome === 1;
    lakers = { outcome: win ? "win" : "loss", delta: win ? 100 : -50 };
  }

  return {
    date: target,
    rotation: { kept, out_count: outTickers.length, in_count: inTickers.length, out: outTickers, in: inTickers },
    top_features,
    ai_daily_return,
    spy_daily_return,
    ai_percentile,
    ai_equity,
    best_personality,
    lakers,
  };
}

// === Race scoreboard ======================================================
// Per-tick winner across AI / SPY / median monkey + running streaks.
// One D1 subrequest: pulls equities + aggregate medians joined per date.

import type { RaceWinner } from "$lib/race";
export type { RaceWinner } from "$lib/race";

export type RaceScoreboard = {
  total_days: number;
  /** Days each contender ended the tick with the highest equity. */
  wins: Record<RaceWinner, number>;
  /** Length of the current consecutive winning streak. */
  current_streak: { winner: RaceWinner; days: number } | null;
  /** Last 10 tick winners, newest first, for an inline sparkline. */
  recent: { date: string; winner: RaceWinner }[];
};

export async function getRaceScoreboard(
  db: D1Database,
  modelId = CHAMPION_MODEL_ID,
): Promise<RaceScoreboard> {
  // Join AI equity, SPY benchmark (from daily_aggregates), and median monkey
  // (also from daily_aggregates) on date. Order ascending so the streak walk
  // is straightforward.
  const { results } = await db
    .prepare(
      `SELECT a.date, e.equity AS ai_eq, a.spy_equity, a.monkey_median
       FROM daily_aggregates a
       LEFT JOIN ai_equity e ON e.date = a.date AND e.model_id = ?
       ORDER BY a.date ASC`,
    )
    .bind(modelId)
    .all<{ date: string; ai_eq: number | null; spy_equity: number | null; monkey_median: number | null }>();

  const wins: Record<RaceWinner, number> = { ai: 0, spy: 0, median_monkey: 0 };
  const dailyWinners: { date: string; winner: RaceWinner }[] = [];

  for (const r of results ?? []) {
    const candidates: [RaceWinner, number][] = [];
    if (r.ai_eq != null) candidates.push(["ai", r.ai_eq]);
    if (r.spy_equity != null) candidates.push(["spy", r.spy_equity]);
    if (r.monkey_median != null) candidates.push(["median_monkey", r.monkey_median]);
    if (candidates.length === 0) continue;
    candidates.sort((a, b) => b[1] - a[1]);
    const [topWinner, topEq] = candidates[0];
    // Tie within 0.1% goes uncounted — same threshold as the hero "in the lead" copy.
    const tied = candidates.slice(1).some(([, eq]) => Math.abs(eq - topEq) < topEq * 0.001);
    if (tied) continue;
    wins[topWinner]++;
    dailyWinners.push({ date: r.date, winner: topWinner });
  }

  // Current streak walks backwards from the latest winner.
  let current_streak: RaceScoreboard["current_streak"] = null;
  if (dailyWinners.length > 0) {
    const latest = dailyWinners[dailyWinners.length - 1].winner;
    let days = 0;
    for (let i = dailyWinners.length - 1; i >= 0; i--) {
      if (dailyWinners[i].winner === latest) days++;
      else break;
    }
    current_streak = { winner: latest, days };
  }

  const recent = dailyWinners.slice(-10).reverse();
  return { total_days: dailyWinners.length, wins, current_streak, recent };
}

// === Monkey survival curve ================================================
// Time-series of n_monkeys_above_starting for the /aggregates survival chart.

export async function getMonkeySurvivalSeries(
  db: D1Database,
  days = 365,
): Promise<{ date: string; above: number; n_monkeys: number }[]> {
  const { results } = await db
    .prepare(
      `SELECT date, n_monkeys_above_starting AS above, n_monkeys
       FROM daily_aggregates
       ORDER BY date DESC LIMIT ?`,
    )
    .bind(days)
    .all<{ date: string; above: number; n_monkeys: number }>();
  return (results ?? []).reverse();
}

/** Last N daily insights, newest first. Used by /journal. */
export async function getRecentInsights(
  db: D1Database,
  days = 30,
  modelId = CHAMPION_MODEL_ID,
): Promise<DailyInsight[]> {
  const tickDates = await db
    .prepare("SELECT date FROM tick_log WHERE status='ok' ORDER BY date DESC LIMIT ?")
    .bind(days)
    .all<{ date: string }>();
  const out: DailyInsight[] = [];
  for (const r of tickDates.results ?? []) {
    const ins = await getDailyInsight(db, r.date, modelId);
    if (ins) out.push(ins);
  }
  return out;
}
