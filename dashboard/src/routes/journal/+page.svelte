<script lang="ts">
  let { data } = $props();

  function fmtRet(r: number | null, prefix = ""): string {
    if (r == null) return "—";
    const pct = (r * 100).toFixed(2);
    return `${prefix}${r >= 0 ? "+" : ""}${pct}%`;
  }
</script>

<section class="page-section">
  <p class="section-num">
    <span class="section-num-num">06</span>
    <span class="section-num-line"></span>
    <span class="section-num-label">journal</span>
  </p>
  <h1 class="page-title">Daily journal</h1>
  <p class="page-sub">
    One entry per tick. Newest first.
  </p>
</section>

{#if data.insights.length === 0}
  <p class="empty">No ticks yet. First entry lands after the next run.</p>
{:else}
  <ol class="journal-feed">
    {#each data.insights as ins}
      <li class="entry">
        <header class="entry-head">
          <h2 class="entry-date">{ins.date}</h2>
          <div class="entry-meta">
            {#if ins.ai_daily_return != null}
              <span class="entry-pill" class:up={ins.ai_daily_return >= 0} class:down={ins.ai_daily_return < 0}>
                AI {fmtRet(ins.ai_daily_return)}
              </span>
            {/if}
            {#if ins.spy_daily_return != null}
              <span class="entry-pill" class:up={ins.spy_daily_return >= 0} class:down={ins.spy_daily_return < 0}>
                SPY {fmtRet(ins.spy_daily_return)}
              </span>
            {/if}
            {#if ins.ai_percentile != null}
              <span class="entry-pill">
                p{ins.ai_percentile.toFixed(0)} vs pack
              </span>
            {/if}
          </div>
        </header>

        <div class="entry-body">
          <div class="entry-section">
            <p class="entry-label">Portfolio</p>
            {#if ins.rotation.in_count === 0 && ins.rotation.kept === 0}
              <p class="entry-text">First tick. No prior portfolio.</p>
            {:else}
              <p class="entry-text">
                Rotated <strong>{ins.rotation.in_count}</strong> of 10 holdings;
                kept <strong>{ins.rotation.kept}</strong>.
              </p>
              {#if ins.rotation.out.length}
                <p class="entry-detail"><span class="muted">sold</span> {ins.rotation.out.join(", ")}</p>
              {/if}
              {#if ins.rotation.in.length}
                <p class="entry-detail"><span class="muted">bought</span> {ins.rotation.in.join(", ")}</p>
              {/if}
            {/if}
          </div>

          <div class="entry-section">
            <p class="entry-label">Model</p>
            {#if ins.top_features.length}
              <p class="entry-text">
                Top features:
                {#each ins.top_features as f, i}
                  <strong>{f.feature}</strong>{i < ins.top_features.length - 1 ? ", " : ""}
                {/each}
              </p>
              <p class="entry-detail muted">
                permutation importance: {ins.top_features.map((f) => f.importance.toFixed(4)).join(" / ")}
              </p>
            {:else}
              <p class="entry-text muted">no diagnostics emitted</p>
            {/if}
          </div>

          {#if ins.best_personality || ins.lakers}
            <div class="entry-section">
              <p class="entry-label">Cast</p>
              {#if ins.best_personality}
                <p class="entry-text">
                  Best monkey: <strong>{ins.best_personality.name}</strong>
                  <span class={ins.best_personality.delta_pct >= 0 ? "up" : "down"}>
                    {ins.best_personality.delta_pct >= 0 ? "▲" : "▼"}
                    {Math.abs(ins.best_personality.delta_pct).toFixed(2)}%
                  </span>
                  to ${ins.best_personality.equity.toLocaleString(undefined, { maximumFractionDigits: 0 })}.
                </p>
              {/if}
              {#if ins.lakers}
                <p class="entry-detail">
                  Lakers <strong>{ins.lakers.outcome === "win" ? "won" : "lost"}</strong>.
                  Joe {ins.lakers.delta >= 0 ? "+" : ""}${Math.abs(ins.lakers.delta)}.
                </p>
              {/if}
            </div>
          {/if}
        </div>
      </li>
    {/each}
  </ol>
{/if}

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
    font-size: clamp(28px, 3.6vw, 38px);
    font-weight: 500;
    letter-spacing: -0.015em;
    margin: 0 0 8px;
  }
  .page-sub {
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--fg-muted);
    margin: 0;
    letter-spacing: 0.02em;
    max-width: 60ch;
    text-wrap: pretty;
  }

  .empty {
    font-family: var(--font-mono);
    font-size: 13px;
    color: var(--fg-muted);
    background: var(--bg-elev);
    border: 1px dashed var(--border);
    padding: 24px;
    border-radius: var(--r-md);
  }

  .journal-feed {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0;
    border-top: 1px solid var(--border);
  }

  .entry {
    padding: 28px 0;
    border-bottom: 1px solid var(--border);
  }

  .entry-head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 16px;
    flex-wrap: wrap;
    margin-bottom: 16px;
  }
  .entry-date {
    font-family: var(--font-mono);
    font-size: 18px;
    letter-spacing: 0.02em;
    color: var(--fg);
    margin: 0;
    font-weight: 500;
  }
  .entry-meta {
    display: inline-flex;
    flex-wrap: wrap;
    gap: 8px;
  }
  .entry-pill {
    font-family: var(--font-mono);
    font-size: 11px;
    letter-spacing: 0.04em;
    padding: 4px 10px;
    border: 1px solid var(--border);
    border-radius: 100px;
    color: var(--fg-muted);
    background: var(--bg-elev);
  }
  .entry-pill.up   { color: var(--c-up); border-color: var(--c-up); }
  .entry-pill.down { color: var(--c-down); border-color: var(--c-down); }

  .entry-body {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 24px;
    align-items: start;
  }
  .entry-section { display: flex; flex-direction: column; gap: 4px; }
  .entry-label {
    font-family: var(--font-mono);
    font-size: 11px;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--fg-dim);
    margin: 0 0 6px;
  }
  .entry-text {
    font-size: 14px;
    line-height: 1.55;
    color: var(--fg);
    margin: 0;
  }
  .entry-text strong { font-weight: 500; }
  .entry-text .up   { color: var(--c-up); }
  .entry-text .down { color: var(--c-down); }
  .entry-detail {
    font-family: var(--font-mono);
    font-size: 12px;
    letter-spacing: 0.02em;
    color: var(--fg-muted);
    margin: 4px 0 0;
    overflow-wrap: anywhere;
  }
  .entry-detail .muted, .entry-text .muted { color: var(--fg-dim); }
</style>
