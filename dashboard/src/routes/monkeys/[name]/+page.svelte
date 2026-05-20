<script lang="ts">
  import Sparkline from "$lib/components/Sparkline.svelte";

  let { data } = $props();

  const values = $derived(data.history.map((h) => h.equity));
  const start = $derived(values[0]);
  const end = $derived(values[values.length - 1]);
  const pctChange = $derived(start ? ((end - start) / start) * 100 : 0);
  const fmt = (n: number | null | undefined) =>
    n == null ? "—" : `$${n.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
  const category = $derived(data.history.at(-1)?.category ?? "unknown");
  const monkeyId = $derived(data.history.at(-1)?.monkey_id ?? null);
</script>

<section class="hero">
  <p class="back">
    <a href="/monkeys">← all named monkeys</a>
  </p>

  <h1 class="name">
    {data.name}
    <span class="meta">monkey #{monkeyId ?? "?"} · {category}</span>
  </h1>

  <div class="numbers">
    <span class="latest">{fmt(end)}</span>
    <span class="delta" class:up={pctChange >= 0} class:down={pctChange < 0}>
      {pctChange >= 0 ? "▲" : "▼"} {Math.abs(pctChange).toFixed(2)}%
      <span class="since">since {data.history[0]?.date ?? "—"}</span>
    </span>
  </div>
</section>

{#if values.length > 0}
  <div class="spark-frame">
    <Sparkline {values} height={180} variant="monkey" />
  </div>
{/if}

<details class="raw">
  <summary>Full history <span class="muted">({data.history.length} rows)</span></summary>
  <div class="table-wrap">
    <table class="data-table">
      <thead>
        <tr>
          <th class="left">Date</th>
          <th>Equity</th>
          <th class="left">Category that day</th>
        </tr>
      </thead>
      <tbody>
        {#each [...data.history].reverse() as h}
          <tr>
            <td class="left date">{h.date}</td>
            <td>{fmt(h.equity)}</td>
            <td class="left muted">{h.category}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
</details>

<style>
  .hero { margin-bottom: 24px; }
  .back {
    font-family: var(--font-mono);
    font-size: 12px;
    margin: 0 0 14px;
    letter-spacing: 0.02em;
  }
  .back a {
    color: var(--fg-muted);
    transition: color 0.15s ease;
  }
  .back a:hover { color: var(--accent); }

  .name {
    font-family: var(--font-serif);
    font-size: clamp(28px, 3.6vw, 38px);
    font-weight: 500;
    letter-spacing: -0.02em;
    margin: 0 0 14px;
    line-height: 1.1;
  }
  .meta {
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--fg-dim);
    margin-left: 12px;
    letter-spacing: 0.04em;
    font-weight: 400;
  }

  .numbers {
    display: flex;
    gap: 20px;
    align-items: baseline;
    border-top: 1px solid var(--border);
    border-bottom: 1px solid var(--border);
    padding: 14px 0;
  }
  .latest {
    font-family: var(--font-mono);
    font-size: clamp(24px, 3vw, 30px);
    font-weight: 500;
    color: var(--fg);
    letter-spacing: -0.01em;
  }
  .delta {
    font-family: var(--font-mono);
    font-size: 13px;
    letter-spacing: 0.02em;
  }
  .delta.up { color: var(--c-up); }
  .delta.down { color: var(--c-down); }
  .since {
    color: var(--fg-dim);
    margin-left: 6px;
  }

  .spark-frame {
    margin: 24px 0 32px;
    background: var(--bg-elev);
    border: 1px solid var(--border);
    border-radius: var(--r-md);
    padding: 16px;
  }

  .raw {
    margin-top: 8px;
    font-family: var(--font-mono);
    font-size: 12px;
  }
  .raw summary {
    cursor: pointer;
    color: var(--fg-muted);
    padding: 8px 0;
    letter-spacing: 0.02em;
    transition: color 0.15s ease;
    user-select: none;
  }
  .raw summary:hover { color: var(--fg); }
  .raw summary :global(.muted) { color: var(--fg-dim); }

  .table-wrap {
    margin-top: 12px;
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
  .data-table td.muted { color: var(--fg-dim); }
  .data-table tr:last-child td { border-bottom: none; }
  .data-table tbody tr:hover td { background: var(--bg-card); }
</style>
