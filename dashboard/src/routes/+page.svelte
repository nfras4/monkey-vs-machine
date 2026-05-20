<script lang="ts">
  import EquityChart from "$lib/components/EquityChart.svelte";

  let { data } = $props();
  const fmt = (n: number | null | undefined) =>
    n == null ? "—" : `$${n.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;

  // Build chart arrays aligned by date (aggregates is the authoritative ordering).
  const dates = data.aggregates.map((a) => a.date);
  const aiByDate = new Map(data.aiEquity.map((e) => [e.date, e.equity] as const));
  const aiEquity = dates.map((d) => aiByDate.get(d) ?? null);
  const spyEquity = data.aggregates.map((a) => a.spy_equity);
  const monkeyMedian = data.aggregates.map((a) => a.monkey_median);
  const monkeyP5 = data.aggregates.map((a) => a.monkey_p5);
  const monkeyP95 = data.aggregates.map((a) => a.monkey_p95);
  const monkeyBest = data.aggregates.map((a) => a.monkey_best);

  // Headline numbers: latest equity for each leader
  const latestAi = data.aiEquity.at(-1)?.equity ?? null;
  const latestAgg = data.aggregates.at(-1);
  const latestSpy = latestAgg?.spy_equity ?? null;
  const latestMedian = latestAgg?.monkey_median ?? null;
  const latestBest = latestAgg?.monkey_best ?? null;
  const totalMonkeys = latestAgg?.n_monkeys ?? 100_000;
  const beating = latestAgg?.n_monkeys_above_starting ?? 0;

  const winner = (() => {
    const candidates: { label: string; value: number | null }[] = [
      { label: "AI", value: latestAi },
      { label: "SPY", value: latestSpy },
      { label: "median monkey", value: latestMedian },
    ].filter((c): c is { label: string; value: number } => c.value != null);
    if (candidates.length === 0) return null;
    return candidates.reduce((a, b) => (a.value >= b.value ? a : b));
  })();
</script>

<section class="header">
  <p class="tick">
    {#if data.lastTick}
      Last tick: <strong>{data.lastTick.date}</strong>
      <span class="dot">·</span>
      {data.lastTick.status}
      <span class="dot">·</span>
      {data.lastTick.duration_seconds?.toFixed(1)}s
    {:else}
      No ticks yet.
    {/if}
  </p>
  {#if winner}
    <p class="winner">
      Currently in the lead: <strong>{winner.label}</strong> at <strong>{fmt(winner.value)}</strong>
      &nbsp;·&nbsp;
      {beating.toLocaleString()} of {totalMonkeys.toLocaleString()} monkeys above their starting cash
    </p>
  {/if}
</section>

<section class="cards">
  <div class="card ai">
    <p class="label">AI trader</p>
    <p class="value">{fmt(latestAi)}</p>
  </div>
  <div class="card spy">
    <p class="label">SPY benchmark</p>
    <p class="value">{fmt(latestSpy)}</p>
  </div>
  <div class="card monkey">
    <p class="label">Median monkey</p>
    <p class="value">{fmt(latestMedian)}</p>
  </div>
  <div class="card best">
    <p class="label">Best monkey today</p>
    <p class="value">{fmt(latestBest)}</p>
  </div>
</section>

<section>
  <h2>The race</h2>
  {#if data.aiEquity.length === 0}
    <p>No ticks yet. Run <code>scripts/bootstrap_genesis.py</code> + <code>scripts/run_tick.py</code> on openclaw, then push.</p>
  {:else}
    <EquityChart {dates} {aiEquity} {spyEquity} {monkeyMedian} {monkeyP5} {monkeyP95} {monkeyBest} />
  {/if}
</section>

<style>
  .header { margin-bottom: 16px; }
  .tick { color: #6b7280; font-size: 13px; margin: 0 0 4px; }
  .winner { font-size: 14px; margin: 0; color: #1f2937; }
  .dot { color: #d1d5db; margin: 0 2px; }

  .cards {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 12px;
    margin: 16px 0 24px;
  }
  .card {
    background: #fff;
    border: 1px solid #e5e7eb;
    border-left: 4px solid var(--accent, #9ca3af);
    border-radius: 8px;
    padding: 14px 16px;
  }
  .card.ai     { --accent: #22c55e; }
  .card.spy    { --accent: #6b7280; }
  .card.monkey { --accent: #f59e0b; }
  .card.best   { --accent: #ef4444; }
  .label { font-size: 11px; color: #6b7280; text-transform: uppercase; letter-spacing: 0.06em; margin: 0 0 6px; }
  .value {
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    font-size: 22px;
    font-weight: 600;
    color: #1a1a1a;
    margin: 0;
    font-variant-numeric: tabular-nums;
  }

  h2 { margin-top: 8px; font-size: 18px; }
</style>
