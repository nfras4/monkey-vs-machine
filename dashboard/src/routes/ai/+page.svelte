<script lang="ts">
  let { data } = $props();
  const latestDiag = $derived(data.history.at(-1)?.diagnostics_json);
  const importances = $derived.by(() => {
    try {
      const d = latestDiag ? JSON.parse(latestDiag) : null;
      const cols = ["ret_1d","ret_5d","ret_20d","vol_20","vol_60","rsi_14","macd_sig","vol_z","abn_ret"];
      const imps: number[] = d?.feature_importances ?? [];
      return cols.map((c, i) => ({ feature: c, imp: imps[i] ?? 0 }))
                 .sort((a, b) => b.imp - a.imp);
    } catch { return []; }
  });
  const maxImp = $derived(importances[0]?.imp ?? 1);
</script>

<section class="page-section">
  <p class="section-num">
    <span class="section-num-num">04</span>
    <span class="section-num-line"></span>
    <span class="section-num-label">AI internals</span>
  </p>
  <h1 class="page-title">Inside the trader</h1>
  <p class="page-sub">
    registered model_ids · {data.modelIds.join(", ") || "(none yet)"}
  </p>
</section>

<div class="grid">
  <section class="block">
    <h2 class="block-title">Current holdings <span class="muted">(champion)</span></h2>
    <div class="table-wrap">
      <table class="data-table">
        <thead><tr><th class="left">Ticker</th><th>Weight</th></tr></thead>
        <tbody>
          {#each data.holdings as h}
            <tr>
              <td class="left strong">{h.ticker}</td>
              <td>{(h.weight * 100).toFixed(1)}%</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  </section>

  <section class="block">
    <h2 class="block-title">Permutation importance <span class="muted">(latest train)</span></h2>
    <ul class="bar-list">
      {#each importances as i}
        <li>
          <span class="bar-label">{i.feature}</span>
          <span class="bar-track">
            <span class="bar-fill" style="width: {maxImp > 0 ? (Math.max(0, i.imp) / maxImp) * 100 : 0}%"></span>
          </span>
          <span class="bar-val">{i.imp.toFixed(4)}</span>
        </li>
      {/each}
    </ul>
  </section>
</div>

<section class="block">
  <h2 class="block-title">Retrain log <span class="muted">(last 60 days)</span></h2>
  <div class="table-wrap">
    <table class="data-table">
      <thead>
        <tr>
          <th class="left">Date</th>
          <th>Train end</th>
          <th>Train seconds</th>
          <th class="left">Family</th>
        </tr>
      </thead>
      <tbody>
        {#each data.history as r}
          <tr>
            <td class="left date">{r.date}</td>
            <td>{r.train_window_end}</td>
            <td>{r.training_seconds?.toFixed(2) ?? "—"}</td>
            <td class="left">{r.model_family}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
</section>

<style>
  .page-section { margin-bottom: 40px; }
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

  .grid {
    display: grid;
    grid-template-columns: 1fr 1.4fr;
    gap: 40px;
    margin-bottom: 56px;
  }
  @media (max-width: 800px) {
    .grid { grid-template-columns: 1fr; gap: 32px; }
  }

  .block { margin-bottom: 40px; }
  .block-title {
    font-family: var(--font-mono);
    font-size: 11px;
    letter-spacing: 0.12em;
    color: var(--fg-dim);
    text-transform: uppercase;
    margin: 0 0 14px;
    font-weight: 500;
  }
  .block-title :global(.muted) { color: var(--fg-dim); }

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

  /* Importance bar list */
  .bar-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 8px;
    font-family: var(--font-mono);
    font-size: 12px;
  }
  .bar-list li {
    display: grid;
    grid-template-columns: 90px 1fr 64px;
    align-items: center;
    gap: 12px;
  }
  .bar-label { color: var(--fg); letter-spacing: 0.02em; }
  .bar-track {
    display: block;
    width: 100%;
    height: 6px;
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 100px;
    overflow: hidden;
  }
  .bar-fill {
    display: block;
    height: 100%;
    background: var(--accent);
    transition: width 0.3s ease;
  }
  .bar-val { color: var(--fg-muted); text-align: right; }
</style>
