// Client-safe race types + label map. Kept out of $lib/server/ so SvelteKit
// can ship these to the browser without dragging the D1 types in.

export type RaceWinner = "ai" | "spy" | "median_monkey";

const RACE_LABELS: Record<RaceWinner, string> = {
  ai: "AI",
  spy: "SPY",
  median_monkey: "median monkey",
};

export function raceLabel(w: RaceWinner): string {
  return RACE_LABELS[w];
}
