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
export type NamedMonkeyRow = { date: string; name: string; monkey_id: number; category: string; equity: number };
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
