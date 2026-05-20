import { getAiEquity, getLastTick, getRecentAggregates } from "$lib/server/d1";
import type { PageServerLoad } from "./$types";

export const load: PageServerLoad = async ({ platform, setHeaders }) => {
  setHeaders({ "cache-control": "public, max-age=60" });
  const db = platform!.env.DB;
  const [aggregates, aiEquity, lastTick] = await Promise.all([
    getRecentAggregates(db, 365),
    getAiEquity(db, 365),
    getLastTick(db),
  ]);
  return { aggregates, aiEquity, lastTick };
};
