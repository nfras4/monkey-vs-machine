<script lang="ts">
  let { data } = $props();
</script>

<section class="page-section">
  <p class="section-num">
    <span class="section-num-num">03</span>
    <span class="section-num-line"></span>
    <span class="section-num-label">named monkeys</span>
  </p>
  <h1 class="page-title">Named monkeys</h1>
  <p class="page-sub">A handful of monkeys with identities — track them through the race.</p>
</section>

<div class="table-wrap">
  <table class="data-table">
    <thead>
      <tr>
        <th class="left">Name</th>
        <th class="left">Category</th>
        <th>Monkey ID</th>
        <th>Equity</th>
      </tr>
    </thead>
    <tbody>
      {#each data.named as m}
        <tr>
          <td class="left">
            <a href={`/monkeys/${m.name}`} class="name-link">{m.name}</a>
          </td>
          <td class="left muted">{m.category}</td>
          <td class="muted">#{m.monkey_id}</td>
          <td class="strong">${m.equity.toFixed(0)}</td>
        </tr>
      {/each}
    </tbody>
  </table>
</div>

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
  .data-table td.muted { color: var(--fg-dim); }
  .data-table td.strong { color: var(--fg); font-weight: 500; }
  .data-table tr:last-child td { border-bottom: none; }
  .data-table tbody tr:hover td { background: var(--bg-card); }

  .name-link {
    color: var(--fg);
    transition: color 0.15s ease;
    border-bottom: 1px dashed var(--border-strong);
  }
  .name-link:hover { color: var(--accent); border-bottom-color: var(--accent); }
</style>
