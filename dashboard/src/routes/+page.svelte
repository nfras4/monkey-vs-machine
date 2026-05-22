<script lang="ts">
  import EquityChart from "$lib/components/EquityChart.svelte";
  import SplitPanel from "$lib/components/SplitPanel.svelte";
  import { raceLabel, type RaceWinner } from "$lib/race";

  let { data } = $props();

  function winnerVariant(w: RaceWinner): "ai" | "spy" | "monkey" {
    return w === "ai" ? "ai" : w === "spy" ? "spy" : "monkey";
  }
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
    Can a <span class="accent">scikit-learn model</span> beat
    100,000 monkeys <span class="muted">throwing darts?</span>
  </h1>

  <div class="status-row">
    <span class="status-pill" data-freshness={data.freshness?.state ?? "missing"}>
      <span class="status-dot"></span>
      {#if data.lastTick}
        last tick <strong>{data.lastTick.date}</strong>
        <span class="sep">·</span>
        {data.lastTick.status}
        {#if data.lastTick.duration_seconds != null}
          <span class="sep">·</span>
          {data.lastTick.duration_seconds.toFixed(1)}s
        {/if}
        {#if data.freshness?.state === "stale"}
          <span class="sep">·</span>
          <span class="stale-flag">{data.freshness.daysBehind} day{data.freshness.daysBehind === 1 ? "" : "s"} behind</span>
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
        too early to call · only {daysOfData} tick{daysOfData === 1 ? "" : "s"} of data
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
  {#if data.aiEquity.length === 0}
    <header class="chart-head">
      <h2 class="chart-title">Equity curves</h2>
    </header>
    <p class="empty">
      No ticks yet. Run <code>scripts/bootstrap_genesis.py</code> + <code>scripts/run_tick.py</code>, then push.
    </p>
  {:else}
    <SplitPanel
      title="Equity curves"
      sub="$10,000 starting cash · 5bp transaction cost · real S&P 500 bars"
    >
      {#snippet left()}
        <article class="chart-card">
          <header class="chart-card-head">
            <h3 class="chart-card-title">AI vs SPY</h3>
            <ul class="legend legend--inline">
              <li><span class="swatch sw-ai"></span> AI trader</li>
              <li><span class="swatch sw-spy"></span> SPY benchmark</li>
            </ul>
          </header>
          <div class="chart-frame">
            <EquityChart
              {dates}
              {aiEquity}
              {spyEquity}
              {monkeyMedian}
              {monkeyP5}
              {monkeyP95}
              {monkeyBest}
              variant="ai-vs-spy"
              height="340px"
            />
          </div>
        </article>
      {/snippet}
      {#snippet right()}
        <article class="chart-card">
          <header class="chart-card-head">
            <h3 class="chart-card-title">Monkey distribution</h3>
            <ul class="legend legend--inline">
              <li><span class="swatch sw-monkey"></span> Median &amp; 5–95% band</li>
            </ul>
          </header>
          <div class="chart-frame">
            <EquityChart
              {dates}
              {aiEquity}
              {spyEquity}
              {monkeyMedian}
              {monkeyP5}
              {monkeyP95}
              {monkeyBest}
              variant="monkey-band"
              height="340px"
            />
          </div>
        </article>
      {/snippet}
    </SplitPanel>
  {/if}
</section>

{#if data.scoreboard && data.scoreboard.total_days > 0}
  {@const sb = data.scoreboard}
  <section class="scoreboard-section">
    <header class="scoreboard-head">
      <h2 class="scoreboard-title">Race scoreboard</h2>
      <p class="scoreboard-sub">days each leader closed the tick on top · ignores ties within 0.1%</p>
    </header>
    <div class="scoreboard-grid">
      <article class="score-card score-ai">
        <p class="score-label">AI trader</p>
        <p class="score-value">{sb.wins.ai} <span class="score-of">/ {sb.total_days}</span></p>
      </article>
      <article class="score-card score-spy">
        <p class="score-label">SPY benchmark</p>
        <p class="score-value">{sb.wins.spy} <span class="score-of">/ {sb.total_days}</span></p>
      </article>
      <article class="score-card score-monkey">
        <p class="score-label">Median monkey</p>
        <p class="score-value">{sb.wins.median_monkey} <span class="score-of">/ {sb.total_days}</span></p>
      </article>
      {#if sb.current_streak}
        <article class="score-card score-streak">
          <p class="score-label">Current streak</p>
          <p class="score-value">
            <strong class="streak-{winnerVariant(sb.current_streak.winner)}">{raceLabel(sb.current_streak.winner)}</strong>
            {sb.current_streak.days}d
          </p>
        </article>
      {/if}
    </div>
    {#if sb.recent.length > 1}
      <ol class="streak-strip" aria-label="last {sb.recent.length} winners, newest first">
        {#each sb.recent as r}
          <li
            class="streak-pip streak-{winnerVariant(r.winner)}"
            title={`${r.date}: ${raceLabel(r.winner)}`}
          ></li>
        {/each}
        <span class="streak-strip-label">last {sb.recent.length} ticks →</span>
      </ol>
    {/if}
  </section>
{/if}

{#if data.insight}
  {@const ins = data.insight}
  <section class="insight-section">
    <header class="insight-head">
      <h2 class="insight-title">Today's read</h2>
      <p class="insight-sub">
        <a href="/journal">see full journal →</a>
      </p>
    </header>
    <div class="insight-grid">
      <article class="insight-card">
        <p class="insight-label">Portfolio rotation</p>
        {#if ins.rotation.in_count === 0 && ins.rotation.kept === 0}
          <p class="insight-value">first tick — no prior portfolio</p>
        {:else}
          <p class="insight-value">
            <strong>{ins.rotation.in_count}</strong> of 10 holdings rotated
          </p>
          <p class="insight-detail">
            {#if ins.rotation.out.length}<span class="muted">sold</span> {ins.rotation.out.slice(0, 3).join(", ")}{#if ins.rotation.out.length > 3}…{/if}{/if}
            {#if ins.rotation.in.length}{#if ins.rotation.out.length} · {/if}<span class="muted">bought</span> {ins.rotation.in.slice(0, 3).join(", ")}{#if ins.rotation.in.length > 3}…{/if}{/if}
          </p>
        {/if}
      </article>

      <article class="insight-card">
        <p class="insight-label">Top features today</p>
        {#if ins.top_features.length}
          <ul class="feature-list">
            {#each ins.top_features as f}
              <li>
                <span class="feature-name">{f.feature}</span>
                <span class="feature-bar">
                  <span class="feature-fill" style="width: {Math.min(100, (f.importance / (ins.top_features[0].importance || 1)) * 100)}%"></span>
                </span>
                <span class="feature-val">{f.importance.toFixed(4)}</span>
              </li>
            {/each}
          </ul>
        {:else}
          <p class="insight-value muted">no diagnostics</p>
        {/if}
      </article>

      <article class="insight-card">
        <p class="insight-label">AI vs SPY today</p>
        <p class="insight-value">
          {#if ins.ai_daily_return != null}
            <span class={ins.ai_daily_return >= 0 ? "up" : "down"}>
              AI {(ins.ai_daily_return * 100).toFixed(2)}%
            </span>
          {:else}
            <span class="muted">AI —</span>
          {/if}
          {#if ins.spy_daily_return != null}
            <span class="sep">·</span>
            <span class={ins.spy_daily_return >= 0 ? "up" : "down"}>
              SPY {(ins.spy_daily_return * 100).toFixed(2)}%
            </span>
          {/if}
        </p>
        <p class="insight-detail">
          {#if ins.ai_daily_return != null && ins.spy_daily_return != null}
            {@const bp = Math.round((ins.ai_daily_return - ins.spy_daily_return) * 10000)}
            <span class="muted">delta</span> {bp >= 0 ? "+" : ""}{bp} bp
          {/if}
        </p>
      </article>

      <article class="insight-card">
        <p class="insight-label">AI rank in the pack</p>
        {#if ins.ai_percentile != null}
          <p class="insight-value">
            <strong>{ins.ai_percentile.toFixed(0)}<sup class="ordinal">th</sup></strong> percentile
          </p>
          <p class="insight-detail muted">
            of 100,000 monkeys
          </p>
        {:else}
          <p class="insight-value muted">no rank yet</p>
        {/if}
      </article>

      {#if ins.best_personality}
        <article class="insight-card">
          <p class="insight-label">Cast standout</p>
          <p class="insight-value">
            <strong>{ins.best_personality.name}</strong>
            <span class={ins.best_personality.delta_pct >= 0 ? "up" : "down"}>
              {ins.best_personality.delta_pct >= 0 ? "▲" : "▼"} {Math.abs(ins.best_personality.delta_pct).toFixed(2)}%
            </span>
          </p>
          <p class="insight-detail muted">
            ${ins.best_personality.equity.toLocaleString(undefined, { maximumFractionDigits: 0 })}
          </p>
        </article>
      {/if}

      {#if ins.lakers}
        <article class="insight-card">
          <p class="insight-label">Lakers Joe</p>
          <p class="insight-value">
            Lakers <strong>{ins.lakers.outcome === "win" ? "W" : "L"}</strong>
            <span class={ins.lakers.delta >= 0 ? "up" : "down"}>
              {ins.lakers.delta >= 0 ? "+" : ""}${Math.abs(ins.lakers.delta)}
            </span>
          </p>
        </article>
      {/if}
    </div>
  </section>
{/if}

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
    transition: border-color 0.2s ease, color 0.2s ease;
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
  /* Stale / missing freshness — visible signal, not silent rot. */
  .status-pill[data-freshness="stale"] {
    border-color: var(--c-down);
    color: var(--fg);
  }
  .status-pill[data-freshness="stale"] .status-dot {
    background: var(--c-down);
    box-shadow: 0 0 8px var(--c-down);
  }
  .status-pill[data-freshness="missing"] {
    border-color: var(--fg-dim);
    color: var(--fg-muted);
  }
  .status-pill[data-freshness="missing"] .status-dot {
    background: var(--fg-dim);
    box-shadow: none;
    animation: none;
  }
  .stale-flag {
    color: var(--c-down);
    font-weight: 500;
    letter-spacing: 0.04em;
  }
  .winner-line { letter-spacing: 0.02em; }
  .winner-line strong { color: var(--fg); font-weight: 500; }
  .sep { color: var(--fg-dim); margin: 0 4px; }

  /* Race scoreboard */
  .scoreboard-section { margin-bottom: 56px; }
  .scoreboard-head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    border-bottom: 1px solid var(--border);
    padding-bottom: 10px;
    margin-bottom: 16px;
    flex-wrap: wrap;
    gap: 12px;
  }
  .scoreboard-title {
    font-family: var(--font-mono);
    font-size: 11px;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: var(--fg-dim);
    margin: 0;
    font-weight: 500;
  }
  .scoreboard-sub {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--fg-dim);
    margin: 0;
    letter-spacing: 0.04em;
  }
  .scoreboard-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 0;
    border-top: 1px solid var(--border);
    border-left: 1px solid var(--border);
  }
  .score-card {
    border-right: 1px solid var(--border);
    border-bottom: 1px solid var(--border);
    padding: 16px 18px 18px;
    position: relative;
    background: var(--bg);
  }
  .score-card::before {
    content: "";
    position: absolute;
    left: 18px;
    top: 18px;
    width: 18px;
    height: 2px;
    background: var(--score-color, var(--accent));
  }
  .score-ai     { --score-color: var(--c-ai); }
  .score-spy    { --score-color: var(--c-spy); }
  .score-monkey { --score-color: var(--c-monkey); }
  .score-streak { --score-color: var(--accent); }
  .score-label {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--fg-dim);
    letter-spacing: 0.08em;
    text-transform: uppercase;
    margin: 0 0 12px;
    padding-left: 26px;
  }
  .score-value {
    font-family: var(--font-mono);
    font-size: 26px;
    font-weight: 500;
    color: var(--fg);
    margin: 0;
    letter-spacing: -0.01em;
  }
  .score-of {
    color: var(--fg-dim);
    font-size: 14px;
    font-weight: 400;
    margin-left: 2px;
  }
  .streak-ai      { color: var(--c-ai); }
  .streak-spy     { color: var(--c-spy); }
  .streak-monkey  { color: var(--c-monkey); }

  /* Mini pip strip of recent winners */
  .streak-strip {
    list-style: none;
    margin: 14px 0 0;
    padding: 0;
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 4px;
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--fg-dim);
    letter-spacing: 0.04em;
  }
  .streak-pip {
    width: 10px;
    height: 10px;
    border-radius: 2px;
    display: inline-block;
    background: var(--fg-dim);
  }
  .streak-pip.streak-ai     { background: var(--c-ai); }
  .streak-pip.streak-spy    { background: var(--c-spy); }
  .streak-pip.streak-monkey { background: var(--c-monkey); }
  .streak-strip-label { margin-left: 6px; }

  /* Today's read */
  .insight-section { margin-bottom: 56px; }
  .insight-head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    border-bottom: 1px solid var(--border);
    padding-bottom: 10px;
    margin-bottom: 16px;
  }
  .insight-title {
    font-family: var(--font-mono);
    font-size: 11px;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: var(--fg-dim);
    margin: 0;
    font-weight: 500;
  }
  .insight-sub {
    margin: 0;
    font-family: var(--font-mono);
    font-size: 11px;
    letter-spacing: 0.04em;
  }
  .insight-sub a { color: var(--accent); }
  .insight-sub a:hover { color: var(--fg); }

  .insight-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    gap: 0;
    border-top: 1px solid var(--border);
    border-left: 1px solid var(--border);
  }
  .insight-card {
    border-right: 1px solid var(--border);
    border-bottom: 1px solid var(--border);
    padding: 18px 20px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .insight-label {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--fg-dim);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin: 0;
  }
  .insight-value {
    font-family: var(--font-mono);
    font-size: 16px;
    letter-spacing: -0.005em;
    margin: 0;
  }
  .insight-value strong { font-weight: 500; }
  .insight-detail {
    font-family: var(--font-mono);
    font-size: 11px;
    letter-spacing: 0.04em;
    color: var(--fg-muted);
    margin: 0;
  }
  .insight-detail .muted,
  .insight-value .muted { color: var(--fg-dim); }
  .insight-value .up   { color: var(--c-up); }
  .insight-value .down { color: var(--c-down); }
  .insight-value .sep  { color: var(--fg-dim); margin: 0 4px; }
  .ordinal {
    font-size: 0.6em;
    letter-spacing: 0;
    margin-left: 1px;
    color: var(--fg-dim);
  }

  /* Importance bars in the insight card */
  .feature-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 4px;
    font-family: var(--font-mono);
    font-size: 11px;
  }
  .feature-list li {
    display: grid;
    grid-template-columns: 64px 1fr 52px;
    align-items: center;
    gap: 8px;
  }
  .feature-name { color: var(--fg); }
  .feature-bar {
    display: block;
    height: 4px;
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 100px;
    overflow: hidden;
  }
  .feature-fill {
    display: block;
    height: 100%;
    background: var(--accent);
  }
  .feature-val {
    text-align: right;
    color: var(--fg-muted);
  }

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

  /* Each panel inside the split */
  .chart-card { display: flex; flex-direction: column; gap: 12px; }
  .chart-card-head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 12px;
    flex-wrap: wrap;
  }
  .chart-card-title {
    font-family: var(--font-mono);
    font-size: 11px;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--fg-dim);
    margin: 0;
    font-weight: 500;
  }

  .chart-frame {
    background: var(--bg-elev);
    border: 1px solid var(--border);
    border-radius: var(--r-lg);
    padding: 20px 16px 12px;
  }

  .legend {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-wrap: wrap;
    gap: 8px 18px;
    font-family: var(--font-mono);
    font-size: 11px;
    letter-spacing: 0.04em;
    color: var(--fg-muted);
  }
  .legend--inline { margin: 0; }
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
