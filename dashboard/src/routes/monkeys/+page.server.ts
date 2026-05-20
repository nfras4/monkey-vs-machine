import { getNamedMonkeys } from "$lib/server/d1";
import type { PageServerLoad } from "./$types";

export const load: PageServerLoad = async ({ platform, setHeaders }) => {
  setHeaders({ "cache-control": "public, max-age=60" });
  return { named: await getNamedMonkeys(platform!.env.DB) };
};
