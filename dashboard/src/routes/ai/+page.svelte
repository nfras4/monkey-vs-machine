<script lang="ts">
  let { data } = $props();
  $: latestDiag = data.history.at(-1)?.diagnostics_json;
  $: importances = (() => {
    try {
      const d = latestDiag ? JSON.parse(latestDiag) : null;
      const cols = ["ret_1d","ret_5d","ret_20d","vol_20","vol_60","rsi_14","macd_sig","vol_z","abn_ret"];
      const imps: number[] = d?.feature_importances ?? [];
      return cols.map((c, i) => ({ feature: c, imp: imps[i] ?? 0 }))
                 .sort((a, b) => b.imp - a.imp);
    } catch { return []; }
  })();
</script>

<h2>AI internals — registered model_ids: {data.modelIds.join(", ") || "(none yet)"}</h2>

<h3>Current holdings (champion)</h3>
<table>
  <thead><tr><th>Ticker</th><th>Weight</th></tr></thead>
  <tbody>
    {#each data.holdings as h}
      <tr><td>{h.ticker}</td><td>{(h.weight * 100).toFixed(1)}%</td></tr>
    {/each}
  </tbody>
</table>

<h3>Permutation importance (latest train)</h3>
<table>
  <thead><tr><th>Feature</th><th>Importance</th></tr></thead>
  <tbody>
    {#each importances as i}
      <tr><td>{i.feature}</td><td>{i.imp.toFixed(4)}</td></tr>
    {/each}
  </tbody>
</table>

<h3>Retrain log (last 60 days)</h3>
<table>
  <thead><tr><th>Date</th><th>Train end</th><th>Train seconds</th><th>Family</th></tr></thead>
  <tbody>
    {#each data.history as r}
      <tr>
        <td>{r.date}</td>
        <td>{r.train_window_end}</td>
        <td>{r.training_seconds?.toFixed(2) ?? "—"}</td>
        <td>{r.model_family}</td>
      </tr>
    {/each}
  </tbody>
</table>

<style>
  h3 { margin-top: 24px; font-size: 15px; }
  table { width: 100%; border-collapse: collapse; font-size: 14px; }
  th, td { padding: 6px 10px; border-bottom: 1px solid #e5e7eb; text-align: right; }
  th:first-child, td:first-child { text-align: left; }
</style>
