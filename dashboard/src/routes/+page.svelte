<script lang="ts">
  import EquityChart from "$lib/components/EquityChart.svelte";

  let { data } = $props();
  const fmt = (n: number | null | undefined) =>
    n == null ? "—" : `$${n.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;

  const dates = data.aggregates.map((a) => a.date);
  const aiByDate = new Map(data.aiEquity.map((e) => [e.date, e.equity] as const));
  const aiEquity = dates.map((d) => aiByDate.get(d) ?? null);
  const spyEquity = data.aggregates.map((a) => a.spy_equity);
  const monkeyMedian = data.aggregates.map((a) => a.monkey_median);
  const monkeyP5 = data.aggregates.map((a) => a.monkey_p5);
  const monkeyP95 = data.aggregates.map((a) => a.monkey_p95);
  const monkeyBest = data.aggregates.map((a) => a.monkey_best);

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
    const best = candidates.reduce((a, b) => (a.value > b.value ? a : b));
    const allTiedish = candidates.every((c) => Math.abs(c.value - best.value) < best.value * 0.001);
    return allTiedish ? null : best;
  })();
  const daysOfData = data.aggregates.length;
</script>

<section class="hero-section">
  <p class="section-num">
    <span class="section-num-num">01</span>
    <span class="section-num-line"></span>
    <span class="section-num-label">the race</span>
  </p>

  <h1 class="hero-pitch">
    <span class="muted">One AI trader,</span>
    100,000 random monkeys,
    <span class="accent">one S&amp;P 500.</span>
  </h1>

  <div class="status-row">
    <span class="status-pill">
      <span class="status-dot"></span>
      {#if data.lastTick}
        last tick <strong>{data.lastTick.date}</strong>
        <span class="sep">·</span>
        {data.lastTick.status}
        {#if data.lastTick.duration_seconds != null}
          <span class="sep">·</span>
          {data.lastTick.duration_seconds.toFixed(1)}s
        {/if}
      {:else}
        no ticks yet
      {/if}
    </span>
    <span class="winner-line">
      {#if winner}
        in the lead <strong>{winner.label}</strong>
        <span class="sep">·</span>
        {fmt(winner.value)}
        <span class="sep">·</span>
        {beating.toLocaleString()} / {totalMonkeys.toLocaleString()} monkeys above starting cash
      {:else if daysOfData < 5}
        too early to call — only {daysOfData} tick{daysOfData === 1 ? "" : "s"} of data
      {:else}
        currently tied within 0.1%
      {/if}
    </span>
  </div>
</section>

<section class="cards-section">
  <div class="cards">
    <article class="card card--ai">
      <p class="card-label">AI trader</p>
      <p class="card-value">{fmt(latestAi)}</p>
      <span class="card-rule" aria-hidden="true"></span>
    </article>
    <article class="card card--spy">
      <p class="card-label">SPY benchmark</p>
      <p class="card-value">{fmt(latestSpy)}</p>
      <span class="card-rule" aria-hidden="true"></span>
    </article>
    <article class="card card--monkey">
      <p class="card-label">Median monkey</p>
      <p class="card-value">{fmt(latestMedian)}</p>
      <span class="card-rule" aria-hidden="true"></span>
    </article>
    <article class="card card--best">
      <p class="card-label">Best monkey today</p>
      <p class="card-value">{fmt(latestBest)}</p>
      <span class="card-rule" aria-hidden="true"></span>
    </article>
  </div>
</section>

<section class="chart-section">
  <header class="chart-head">
    <h2 class="chart-title">Equity curves</h2>
    <p class="chart-sub">$10,000 starting cash · 5bp transaction cost · real S&amp;P 500 bars</p>
  </header>
  {#if data.aiEquity.length === 0}
    <p class="empty">
      No ticks yet. Run <code>scripts/bootstrap_genesis.py</code> + <code>scripts/run_tick.py</code> on openclaw, then push.
    </p>
  {:else}
    <div class="chart-frame">
      <EquityChart {dates} {aiEquity} {spyEquity} {monkeyMedian} {monkeyP5} {monkeyP95} {monkeyBest} />
    </div>
    <ul class="legend">
      <li><span class="swatch sw-ai"></span> AI trader</li>
      <li><span class="swatch sw-spy"></span> SPY benchmark</li>
      <li><span class="swatch sw-monkey"></span> Monkey median &amp; 5–95% band</li>
      <li><span class="swatch sw-best"></span> Best monkey today</li>
    </ul>
  {/if}
</section>

<style>
  /* Hero */
  .hero-section {
    padding-top: 8px;
    margin-bottom: 56px;
  }
  .section-num {
    font-family: var(--font-mono);
    font-size: 11px;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    margin: 0 0 28px;
    display: inline-flex;
    align-items: baseline;
    gap: 12px;
  }
  .section-num-num { color: var(--accent); font-weight: 500; }
  .section-num-line {
    flex: 0 0 auto;
    width: 28px;
    height: 1px;
    background: var(--fg-dim);
    transform: translateY(-3px);
  }
  .section-num-label { color: var(--fg-dim); }

  .hero-pitch {
    font-family: var(--font-serif);
    font-size: clamp(32px, 5vw, 56px);
    line-height: 1.08;
    letter-spacing: -0.02em;
    font-weight: 500;
    margin: 0 0 32px;
    max-width: 880px;
    text-wrap: balance;
  }
  .hero-pitch .accent { color: var(--accent); }
  .hero-pitch :global(.muted) { color: var(--fg-muted); }

  .status-row {
    display: flex;
    flex-wrap: wrap;
    gap: 14px 24px;
    align-items: center;
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--fg-muted);
  }
  .status-pill {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 6px 12px;
    border: 1px solid var(--border-strong);
    border-radius: 100px;
    letter-spacing: 0.04em;
  }
  .status-pill strong { color: var(--fg); font-weight: 500; }
  .status-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--accent);
    box-shadow: 0 0 8px var(--accent);
    animation: pulse 2.4s infinite;
  }
  .winner-line { letter-spacing: 0.02em; }
  .winner-line strong { color: var(--fg); font-weight: 500; }
  .sep { color: var(--fg-dim); margin: 0 4px; }

  @keyframes pulse {
    0%, 100% { box-shadow: 0 0 0 0 color-mix(in oklch, var(--accent) 50%, transparent); }
    50% { box-shadow: 0 0 0 6px color-mix(in oklch, var(--accent) 0%, transparent); }
  }

  /* Cards */
  .cards-section { margin-bottom: 64px; }
  .cards {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 0;
    border-top: 1px solid var(--border);
    border-left: 1px solid var(--border);
  }
  .card {
    position: relative;
    border-right: 1px solid var(--border);
    border-bottom: 1px solid var(--border);
    padding: 22px 22px 26px;
    background: var(--bg);
    transition: background 0.2s ease;
  }
  .card:hover { background: var(--bg-elev); }
  .card-label {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--fg-dim);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin: 0 0 12px;
  }
  .card-value {
    font-family: var(--font-mono);
    font-size: 26px;
    font-weight: 500;
    color: var(--fg);
    margin: 0;
    letter-spacing: -0.01em;
  }
  .card-rule {
    position: absolute;
    left: 22px;
    top: 22px;
    width: 18px;
    height: 2px;
    background: var(--card-color, var(--accent));
  }
  .card--ai     { --card-color: var(--c-ai); }
  .card--spy    { --card-color: var(--c-spy); }
  .card--monkey { --card-color: var(--c-monkey); }
  .card--best   { --card-color: var(--c-best); }
  .card-label { padding-left: 26px; }

  /* Chart */
  .chart-section { margin-bottom: 32px; }
  .chart-head { margin-bottom: 20px; }
  .chart-title {
    font-family: var(--font-serif);
    font-size: clamp(22px, 2.4vw, 28px);
    letter-spacing: -0.015em;
    font-weight: 500;
    margin: 0 0 4px;
  }
  .chart-sub {
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--fg-muted);
    margin: 0;
    letter-spacing: 0.02em;
  }

  .chart-frame {
    background: var(--bg-elev);
    border: 1px solid var(--border);
    border-radius: var(--r-lg);
    padding: 20px 16px 12px;
  }

  .legend {
    list-style: none;
    margin: 16px 0 0;
    padding: 0;
    display: flex;
    flex-wrap: wrap;
    gap: 8px 22px;
    font-family: var(--font-mono);
    font-size: 11px;
    letter-spacing: 0.04em;
    color: var(--fg-muted);
  }
  .legend li { display: inline-flex; align-items: center; gap: 8px; }
  .swatch {
    display: inline-block;
    width: 18px;
    height: 2px;
    background: var(--accent);
    border-radius: 1px;
  }
  .sw-ai     { background: var(--c-ai); height: 3px; }
  .sw-spy    { background: var(--c-spy); height: 2px; }
  .sw-monkey { background: var(--c-monkey); height: 2px; }
  .sw-best   { background: var(--c-best); height: 1.5px; }

  .empty {
    font-family: var(--font-mono);
    font-size: 13px;
    color: var(--fg-muted);
    background: var(--bg-elev);
    border: 1px dashed var(--border);
    padding: 24px;
    border-radius: var(--r-md);
  }

  @media (max-width: 600px) {
    .hero-pitch { margin-bottom: 28px; }
    .card-value { font-size: 22px; }
  }
</style>
