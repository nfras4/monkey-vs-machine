import { getNamedMonkeys, getRecentNamedMonkeyHistory } from "$lib/server/d1";
import type { PageServerLoad } from "./$types";

export const load: PageServerLoad = async ({ platform, setHeaders }) => {
  setHeaders({ "cache-control": "public, max-age=60" });
  const db = platform!.env.DB;
  const [named, recent] = await Promise.all([
    getNamedMonkeys(db),
    getRecentNamedMonkeyHistory(db, 21),
  ]);
  return { named, recent };
};
