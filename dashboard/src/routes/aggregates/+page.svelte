<script lang="ts">
  import SplitPanel from "$lib/components/SplitPanel.svelte";
  import SurvivalChart from "$lib/components/SurvivalChart.svelte";
  let { data } = $props();

  // Convert raw counts into percentage time-series for the chart.
  const survivalDates = data.survival.map((r) => r.date);
  const survivalPct = data.survival.map((r) =>
    r.n_monkeys > 0 ? (r.above / r.n_monkeys) * 100 : 0,
  );
  const latest = data.survival.at(-1);
  const latestPct = latest && latest.n_monkeys > 0 ? (latest.above / latest.n_monkeys) * 100 : null;
</script>

<section class="page-section">
  <p class="section-num">
    <span class="section-num-num">02</span>
    <span class="section-num-line"></span>
    <span class="section-num-label">aggregates</span>
  </p>

  <h1 class="page-title">Monkey distribution by day</h1>
  <p class="page-sub">Daily statistics across all 100,000 monkeys.</p>
</section>

{#if data.survival.length > 0}
  <section class="survival-section">
    <header class="survival-head">
      <h3 class="survival-title">Pack survival rate</h3>
      <p class="survival-sub">
        {#if latestPct != null}
          <strong>{latestPct.toFixed(1)}%</strong> of {latest!.n_monkeys.toLocaleString()} monkeys are currently above their $10,000 starting cash
        {:else}
          % of monkeys still above starting cash over time
        {/if}
      </p>
    </header>
    <div class="chart-frame">
      <SurvivalChart dates={survivalDates} pct={survivalPct} />
    </div>
  </section>
{/if}

<SplitPanel breakpoint={900}>
  {#snippet left()}
    <article class="panel">
      <header class="panel-head">
        <h3 class="panel-title">Central tendency</h3>
        <p class="panel-sub">mean &amp; median equity per day</p>
      </header>
      <div class="table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th class="left">Date</th>
              <th>Mean</th>
              <th>Median</th>
            </tr>
          </thead>
          <tbody>
            {#each data.aggregates as a}
              <tr>
                <td class="left date">{a.date}</td>
                <td>{a.monkey_mean.toFixed(0)}</td>
                <td class="strong">{a.monkey_median.toFixed(0)}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </article>
  {/snippet}

  {#snippet right()}
    <article class="panel">
      <header class="panel-head">
        <h3 class="panel-title">Distribution percentiles</h3>
        <p class="panel-sub">spread of the pack from p5 to p95</p>
      </header>
      <div class="table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th class="left">Date</th>
              <th>p5</th>
              <th>p25</th>
              <th>p75</th>
              <th>p95</th>
            </tr>
          </thead>
          <tbody>
            {#each data.aggregates as a}
              <tr>
                <td class="left date">{a.date}</td>
                <td>{a.monkey_p5.toFixed(0)}</td>
                <td>{a.monkey_p25.toFixed(0)}</td>
                <td>{a.monkey_p75.toFixed(0)}</td>
                <td>{a.monkey_p95.toFixed(0)}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </article>
  {/snippet}
</SplitPanel>

<style>
  .page-section { margin-bottom: 32px; }
  .section-num {
    font-family: var(--font-mono);
    font-size: 11px;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    margin: 0 0 24px;
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

  .page-title {
    font-family: var(--font-serif);
    font-size: clamp(26px, 3.2vw, 34px);
    font-weight: 500;
    letter-spacing: -0.015em;
    margin: 0 0 6px;
  }
  .page-sub {
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--fg-muted);
    margin: 0;
    letter-spacing: 0.02em;
  }

  /* Survival chart block */
  .survival-section { margin-bottom: 48px; }
  .survival-head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    border-bottom: 1px solid var(--border);
    padding-bottom: 10px;
    margin-bottom: 14px;
    gap: 12px;
    flex-wrap: wrap;
  }
  .survival-title {
    font-family: var(--font-mono);
    font-size: 11px;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--fg-dim);
    margin: 0;
    font-weight: 500;
  }
  .survival-sub {
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--fg-muted);
    margin: 0;
    letter-spacing: 0.02em;
  }
  .survival-sub strong { color: var(--fg); font-weight: 500; }
  .chart-frame {
    background: var(--bg-elev);
    border: 1px solid var(--border);
    border-radius: var(--r-lg);
    padding: 20px 16px 12px;
  }

  .panel { display: flex; flex-direction: column; gap: 12px; }
  .panel-head { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
  .panel-title {
    font-family: var(--font-mono);
    font-size: 11px;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--fg-dim);
    margin: 0;
    font-weight: 500;
  }
  .panel-sub {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--fg-dim);
    margin: 0;
    letter-spacing: 0.02em;
  }

  .table-wrap {
    overflow-x: auto;
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    background: var(--bg-elev);
  }
  .data-table {
    width: 100%;
    border-collapse: collapse;
    font-family: var(--font-mono);
    font-size: 13px;
  }
  .data-table th {
    font-weight: 500;
    text-align: right;
    padding: 12px 14px;
    color: var(--fg-dim);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-size: 11px;
    border-bottom: 1px solid var(--border);
    background: var(--bg-card);
  }
  .data-table th.left { text-align: left; }
  .data-table td {
    padding: 10px 14px;
    text-align: right;
    color: var(--fg-muted);
    border-bottom: 1px solid var(--border);
  }
  .data-table td.left { text-align: left; }
  .data-table td.date { color: var(--fg-dim); }
  .data-table td.strong { color: var(--fg); font-weight: 500; }
  .data-table tr:last-child td { border-bottom: none; }
  .data-table tbody tr:hover td { background: var(--bg-card); }
</style>
