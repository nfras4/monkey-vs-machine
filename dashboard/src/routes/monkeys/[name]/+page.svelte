<script lang="ts">
  import Sparkline from "$lib/components/Sparkline.svelte";

  let { data } = $props();

  const values = data.history.map((h) => h.equity);
  const start = values[0];
  const end = values[values.length - 1];
  const pctChange = start ? ((end - start) / start) * 100 : 0;
  const fmt = (n: number | null | undefined) =>
    n == null ? "—" : `$${n.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
  const category = data.history.at(-1)?.category ?? "unknown";
  const monkeyId = data.history.at(-1)?.monkey_id ?? null;
</script>

<section class="hero">
  <p class="back"><a href="/monkeys">← all named monkeys</a></p>
  <h2>{data.name} <span class="meta">· monkey #{monkeyId ?? "?"} · category: {category}</span></h2>
  <div class="numbers">
    <span class="latest">{fmt(end)}</span>
    <span class="delta" class:up={pctChange >= 0} class:down={pctChange < 0}>
      {pctChange >= 0 ? "▲" : "▼"} {Math.abs(pctChange).toFixed(2)}%
      since {data.history[0]?.date ?? "—"}
    </span>
  </div>
</section>

{#if values.length > 0}
  <Sparkline {values} height={180} />
{/if}

<details class="raw">
  <summary>Full history ({data.history.length} rows)</summary>
  <table>
    <thead><tr><th>Date</th><th>Equity</th><th>Category that day</th></tr></thead>
    <tbody>
      {#each [...data.history].reverse() as h}
        <tr><td>{h.date}</td><td>{fmt(h.equity)}</td><td>{h.category}</td></tr>
      {/each}
    </tbody>
  </table>
</details>

<style>
  .hero { margin-bottom: 16px; }
  .back { font-size: 13px; margin: 0 0 6px; }
  .back a { color: #6b7280; text-decoration: none; }
  .back a:hover { color: #1f2937; text-decoration: underline; }
  h2 { margin: 0 0 8px; font-size: 22px; }
  .meta { color: #6b7280; font-weight: 400; font-size: 14px; }
  .numbers { display: flex; gap: 18px; align-items: baseline; }
  .latest {
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    font-size: 28px;
    font-weight: 600;
    font-variant-numeric: tabular-nums;
  }
  .delta { font-size: 14px; font-variant-numeric: tabular-nums; }
  .delta.up { color: #047857; }
  .delta.down { color: #b91c1c; }
  details.raw { margin-top: 24px; }
  details.raw summary { cursor: pointer; color: #6b7280; font-size: 13px; }
  table { width: 100%; border-collapse: collapse; font-size: 14px; margin-top: 12px; }
  th, td { padding: 6px 10px; border-bottom: 1px solid #e5e7eb; text-align: right; }
  th:first-child, td:first-child { text-align: left; }
</style>
