/**
 * SvelteKit server endpoint: bearer-authenticated D1 ingest from openclaw.
 *
 *   POST /admin/ingest
 *   Authorization: Bearer ${env.MVM_INGEST_TOKEN}
 *   Content-Type: application/json
 *
 * Lives inside the SvelteKit worker (rather than as a Pages Function) because
 * the SvelteKit adapter's _worker.js catches everything — Pages Functions only
 * fire on routes the SvelteKit router doesn't claim, and `/admin/ingest` was
 * being swallowed by the SvelteKit 404 page. Same behaviour, same auth, same
 * D1 batch.
 */
import { json, error } from "@sveltejs/kit";
import type { RequestHandler } from "./$types";

interface IngestPayload {
  publish_schema_version: number;
  date: string;
  daily_aggregates: Record<string, unknown> | null;
  ai_history: Record<string, unknown>[];
  ai_portfolios: Record<string, unknown>[];
  ai_equity: Record<string, unknown>[];
  named_monkey_history: Record<string, unknown>[];
  tick: Record<string, unknown> | null;
  // v2: 8-monkey personality cast + frozen external events.
  // external_events is the FULL frozen table from genesis — INSERT OR IGNORE
  // on the receive side keeps it idempotent and cheap (247 rows for Lakers).
  external_events?: Record<string, unknown>[];
}

function constantTimeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

export const POST: RequestHandler = async ({ request, platform }) => {
  if (!platform?.env?.DB) {
    throw error(500, "DB binding not available");
  }
  const env = platform.env;

  // Auth
  const authHeader = request.headers.get("Authorization") ?? "";
  const m = authHeader.match(/^Bearer\s+(.+)$/);
  if (!m || !env.MVM_INGEST_TOKEN || !constantTimeEqual(m[1], env.MVM_INGEST_TOKEN)) {
    throw error(401, "unauthorized");
  }

  // Parse + version check
  let payload: IngestPayload;
  try {
    payload = (await request.json()) as IngestPayload;
  } catch (e) {
    throw error(400, `invalid json: ${(e as Error).message}`);
  }

  const versionEnv = env.PUBLISH_SCHEMA_VERSION;
  if (!versionEnv) {
    throw error(500, "PUBLISH_SCHEMA_VERSION env binding is missing");
  }
  const expectedVersion = Number(versionEnv);
  if (!Number.isFinite(expectedVersion)) {
    throw error(500, `PUBLISH_SCHEMA_VERSION must be a number; got ${versionEnv}`);
  }
  if (payload.publish_schema_version !== expectedVersion) {
    throw error(
      409,
      `publish_schema_version mismatch: payload=${payload.publish_schema_version} expected=${expectedVersion}`,
    );
  }

  // Build batched statements
  const stmts = [];
  const d = payload.date;

  if (payload.daily_aggregates) {
    const a = payload.daily_aggregates as Record<string, number | null>;
    stmts.push(
      env.DB.prepare(
        `INSERT OR REPLACE INTO daily_aggregates
         (date, monkey_mean, monkey_median, monkey_p5, monkey_p25, monkey_p75, monkey_p95,
          monkey_best, monkey_worst, n_monkeys, n_monkeys_above_starting, spy_equity)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      ).bind(
        d, a.monkey_mean, a.monkey_median, a.monkey_p5, a.monkey_p25, a.monkey_p75,
        a.monkey_p95, a.monkey_best, a.monkey_worst, a.n_monkeys, a.n_monkeys_above_starting,
        a.spy_equity,
      ),
    );
  }

  for (const r of payload.ai_history) {
    stmts.push(
      env.DB.prepare(
        `INSERT OR REPLACE INTO ai_history
         (date, model_id, model_family, config_json, diagnostics_json,
          runtime_fingerprint, features_hash, train_window_end, training_seconds)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      ).bind(
        r.date, r.model_id, r.model_family, r.config_json, r.diagnostics_json,
        r.runtime_fingerprint, r.features_hash, r.train_window_end, r.training_seconds,
      ),
    );
  }

  const seen = new Set<string>();
  for (const r of payload.ai_portfolios) {
    const key = `${r.date}|${r.model_id}`;
    if (!seen.has(key)) {
      seen.add(key);
      stmts.push(env.DB.prepare("DELETE FROM ai_portfolios WHERE date=? AND model_id=?").bind(r.date, r.model_id));
    }
    stmts.push(
      env.DB.prepare(
        "INSERT OR REPLACE INTO ai_portfolios (date, ticker, model_id, weight) VALUES (?, ?, ?, ?)",
      ).bind(r.date, r.ticker, r.model_id, r.weight),
    );
  }

  for (const r of payload.ai_equity) {
    stmts.push(
      env.DB.prepare(
        "INSERT OR REPLACE INTO ai_equity (date, model_id, equity, daily_return) VALUES (?, ?, ?, ?)",
      ).bind(r.date, r.model_id, r.equity, r.daily_return),
    );
  }

  for (const r of payload.named_monkey_history) {
    stmts.push(
      env.DB.prepare(
        `INSERT OR REPLACE INTO named_monkey_history
         (date, name, monkey_id, category, equity, personality_config)
         VALUES (?, ?, ?, ?, ?, ?)`,
      ).bind(
        r.date, r.name, r.monkey_id, r.category, r.equity,
        // v2: personality_config is denormalised onto each history row so
        // /monkeys can render character cards without a second table fetch.
        (r.personality_config as string | null | undefined) ?? null,
      ),
    );
  }

  // v2: frozen external_events (Lakers results etc.). Always idempotent —
  // INSERT OR IGNORE preserves the first-write-wins genesis fingerprint.
  for (const r of payload.external_events ?? []) {
    stmts.push(
      env.DB.prepare(
        `INSERT OR IGNORE INTO external_events
         (date, event_kind, outcome, payload_json)
         VALUES (?, ?, ?, ?)`,
      ).bind(r.date, r.event_kind, r.outcome, (r.payload_json as string | null | undefined) ?? null),
    );
  }

  if (payload.tick) {
    const t = payload.tick as Record<string, unknown>;
    stmts.push(
      env.DB.prepare(
        `INSERT OR REPLACE INTO tick_log (date, status, duration_seconds, note, pushed_at)
         VALUES (?, ?, ?, ?, datetime('now'))`,
      ).bind(t.date, t.status, t.duration_seconds ?? null, t.note ?? null),
    );
  }

  try {
    await env.DB.batch(stmts);
  } catch (e) {
    throw error(500, `d1 batch failed: ${(e as Error).message}`);
  }

  return json({ ok: true, date: d, statements: stmts.length });
};
