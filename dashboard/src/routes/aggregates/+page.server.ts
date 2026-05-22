import { getMonkeySurvivalSeries, getRecentAggregates } from "$lib/server/d1";
import type { PageServerLoad } from "./$types";

export const load: PageServerLoad = async ({ platform, setHeaders }) => {
  setHeaders({ "cache-control": "public, max-age=60" });
  const db = platform!.env.DB;
  const [aggregates, survival] = await Promise.all([
    getRecentAggregates(db, 365),
    getMonkeySurvivalSeries(db, 365),
  ]);
  return { aggregates, survival };
};
