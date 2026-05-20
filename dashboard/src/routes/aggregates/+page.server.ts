import { getRecentAggregates } from "$lib/server/d1";
import type { PageServerLoad } from "./$types";

export const load: PageServerLoad = async ({ platform, setHeaders }) => {
  setHeaders({ "cache-control": "public, max-age=60" });
  return { aggregates: await getRecentAggregates(platform!.env.DB, 365) };
};
