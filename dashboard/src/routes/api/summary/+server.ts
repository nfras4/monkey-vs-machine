/**
 * Public read-only race summary, used by the portfolio site's project card
 * (nickwfraser.dev) to show the current standings on a sticky note.
 *
 *   GET /api/summary
 *   -> { date, ai_equity, monkey_mean, spy_equity, n_monkeys }
 *
 * CORS is wide open on purpose: this is the same public data the dashboard
 * itself renders, one row of it.
 */
import { json } from "@sveltejs/kit";
import { CHAMPION_MODEL_ID } from "$lib/server/d1";
import type { RequestHandler } from "./$types";

const CORS = { "access-control-allow-origin": "*" };

export const GET: RequestHandler = async ({ platform, setHeaders }) => {
  const db = platform?.env?.DB;
  if (!db) {
    return json({ error: "no database binding" }, { status: 503, headers: CORS });
  }

  setHeaders({ "cache-control": "public, max-age=300" });

  const row = await db
    .prepare(
      `SELECT a.date, a.monkey_mean, a.spy_equity, a.n_monkeys, e.equity AS ai_equity
       FROM daily_aggregates a
       LEFT JOIN ai_equity e ON e.date = a.date AND e.model_id = ?
       ORDER BY a.date DESC LIMIT 1`
    )
    .bind(CHAMPION_MODEL_ID)
    .first<{
      date: string;
      monkey_mean: number;
      spy_equity: number | null;
      n_monkeys: number;
      ai_equity: number | null;
    }>();

  if (!row) {
    return json({ error: "no data yet" }, { status: 404, headers: CORS });
  }

  return json(
    {
      date: row.date,
      ai_equity: row.ai_equity,
      monkey_mean: row.monkey_mean,
      spy_equity: row.spy_equity,
      n_monkeys: row.n_monkeys,
    },
    { headers: CORS }
  );
};
