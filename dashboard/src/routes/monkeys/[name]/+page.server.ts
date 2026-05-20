import { getNamedMonkeyHistory } from "$lib/server/d1";
import type { PageServerLoad } from "./$types";

export const load: PageServerLoad = async ({ params, platform, setHeaders }) => {
  setHeaders({ "cache-control": "public, max-age=60" });
  return {
    name: params.name,
    history: await getNamedMonkeyHistory(platform!.env.DB, params.name),
  };
};
