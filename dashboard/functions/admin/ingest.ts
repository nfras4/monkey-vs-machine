/**
 * Cloudflare Pages Function: bearer-authenticated D1 ingest from openclaw.
 *
 *   POST /admin/ingest
 *   Authorization: Bearer ${env.MVM_INGEST_TOKEN}
 *   Content-Type: application/json
 *   Body: see scripts/push_to_d1.py build_payload()
 *
 * Idempotent via INSERT OR REPLACE on every table.
 */

interface Env {
  DB: D1Database;
  MVM_INGEST_TOKEN: string;
  PUBLISH_SCHEMA_VERSION: string;
}

interface IngestPayload {
  publish_schema_version: number;
  date: string;
  daily_aggregates: Record<string, unknown> | null;
  ai_history: Record<string, unknown>[];
  ai_portfolios: Record<string, unknown>[];
  ai_equity: Record<string, unknown>[];
  named_monkey_history: Record<string, unknown>[];
  tick: Record<string, unknown> | null;
}

function constantTimeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

export const onRequestPost: PagesFunction<Env> = async ({ request, env }) => {
  // --- Auth -----------------------------------------------------------------
  const authHeader = request.headers.get("Authorization") ?? "";
  const m = authHeader.match(/^Bearer\s+(.+)$/);
  if (!m || !env.MVM_INGEST_TOKEN || !constantTimeEqual(m[1], env.MVM_INGEST_TOKEN)) {
    return new Response("unauthorized", { status: 401 });
  }

  // --- Parse + schema version ----------------------------------------------
  let payload: IngestPayload;
  try {
    payload = (await request.json()) as IngestPayload;
  } catch (e) {
    return new Response(`invalid json: ${(e as Error).message}`, { status: 400 });
  }

  // Fail closed if the env binding is missing — a misconfigured Pages env
  // must never silently accept v1 payloads with no version check.
  const versionEnv = env.PUBLISH_SCHEMA_VERSION;
  if (!versionEnv) {
    return new Response("PUBLISH_SCHEMA_VERSION env binding is missing", { status: 500 });
  }
  const expectedVersion = Number(versionEnv);
  if (!Number.isFinite(expectedVersion)) {
    return new Response(`PUBLISH_SCHEMA_VERSION must be a number; got ${versionEnv}`, { status: 500 });
  }
  if (payload.publish_schema_version !== expectedVersion) {
    return new Response(
      `publish_schema_version mismatch: payload=${payload.publish_schema_version} expected=${expectedVersion}`,
      { status: 409 },
    );
  }

  // --- Build batched statements --------------------------------------------
  const stmts: D1PreparedStatement[] = [];
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

  // Replace today's per-(date, model_id) portfolio rows by deleting first, then inserting.
  const seenPortfolioKeys = new Set<string>();
  for (const r of payload.ai_portfolios) {
    const key = `${r.date}|${r.model_id}`;
    if (!seenPortfolioKeys.has(key)) {
      seenPortfolioKeys.add(key);
      stmts.push(
        env.DB.prepare("DELETE FROM ai_portfolios WHERE date=? AND model_id=?").bind(r.date, r.model_id),
      );
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
        "INSERT OR REPLACE INTO named_monkey_history (date, name, monkey_id, category, equity) VALUES (?, ?, ?, ?, ?)",
      ).bind(r.date, r.name, r.monkey_id, r.category, r.equity),
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
    return new Response(`d1 batch failed: ${(e as Error).message}`, { status: 500 });
  }

  return new Response(JSON.stringify({ ok: true, date: d, statements: stmts.length }), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
};
