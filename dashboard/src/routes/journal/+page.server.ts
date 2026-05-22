import { getRecentInsights } from "$lib/server/d1";
import type { PageServerLoad } from "./$types";

export const load: PageServerLoad = async ({ platform, setHeaders }) => {
  setHeaders({ "cache-control": "public, max-age=60" });
  const db = platform!.env.DB;
  return { insights: await getRecentInsights(db, 30) };
};
