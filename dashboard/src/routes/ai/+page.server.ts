import { getAiHistory, getAiHoldings, getAiModelIds } from "$lib/server/d1";
import type { PageServerLoad } from "./$types";

export const load: PageServerLoad = async ({ platform, setHeaders }) => {
  setHeaders({ "cache-control": "public, max-age=60" });
  const db = platform!.env.DB;
  const [holdings, history, modelIds] = await Promise.all([
    getAiHoldings(db),
    getAiHistory(db, 60),
    getAiModelIds(db),
  ]);
  return { holdings, history, modelIds };
};
