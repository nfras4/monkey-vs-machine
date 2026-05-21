<script lang="ts">
  import Sparkline from "$lib/components/Sparkline.svelte";

  let { data } = $props();

  // Tagline + sparkline variant from the personality_config JSON.
  // Falls back to plain category text for daily-refreshed slots (top/bottom/mover).
  function describe(name: string, category: string, configRaw: string | null): {
    tagline: string;
    variant: "ai" | "monkey" | "spy" | "best";
  } {
    if (!configRaw) {
      if (category === "top") return { tagline: "today's leaderboard", variant: "ai" };
      if (category === "bottom") return { tagline: "today's stragglers", variant: "best" };
      if (category === "mover") return { tagline: "biggest 24h swing", variant: "monkey" };
      return { tagline: category, variant: "monkey" };
    }
    try {
      const c = JSON.parse(configRaw);
      switch (c.kind) {
        case "tech_lover":
          return { tagline: `tech sector affinity · ${Math.round((c.bias ?? 0.7) * 100)}% bias`, variant: "ai" };
        case "value_hunter":
          return { tagline: "value tilt · avoids tech", variant: "spy" };
        case "weekday_trader": {
          const days = (c.trade_days as number[] | undefined)?.map((d) => ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"][d]).join("/") ?? "Mon";
          return { tagline: `trades only ${days}`, variant: "monkey" };
        }
        case "contrarian_weekday":
          return { tagline: "buys Mon · sells Fri", variant: "monkey" };
        case "dip_buyer":
          return { tagline: `buys after ${c.lookback ?? 3}-day dips`, variant: "ai" };
        case "momentum_chaser":
          return { tagline: `rides ${c.lookback ?? 5}-day momentum`, variant: "best" };
        case "lakers_fan":
          return { tagline: `+$${c.win_bonus ?? 100} per Lakers W`, variant: "best" };
        case "babysitter":
          return { tagline: `+$${c.credit_amount ?? 25} every Monday`, variant: "monkey" };
        default:
          return { tagline: c.kind ?? "unknown", variant: "monkey" };
      }
    } catch {
      return { tagline: category, variant: "monkey" };
    }
  }

  // Pre-compute card view-models so the template stays clean.
  // pct is `null` when we have <2 history points — showing "▲ 0.00%" green
  // would be a false-positive signal on a brand-new cast.
  const cards = $derived(
    data.named.map((m) => {
      const history = data.recent[m.name] ?? [];
      const values = history.map((h) => h.equity);
      let pct: number | null = null;
      if (values.length >= 2) {
        const start = values[0];
        const end = values[values.length - 1];
        if (start) pct = ((end - start) / start) * 100;
      }
      const { tagline, variant } = describe(m.name, m.category, m.personality_config);
      return {
        name: m.name,
        monkey_id: m.monkey_id,
        category: m.category,
        equity: m.equity,
        tagline,
        variant,
        values,
        pct,
        isPersonality: m.category === "personality",
      };
    }),
  );

  const personality = $derived(cards.filter((c) => c.isPersonality));
  const slots = $derived(cards.filter((c) => !c.isPersonality));

  const fmt = (n: number) => `$${n.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
</script>

<section class="page-section">
  <p class="section-num">
    <span class="section-num-num">03</span>
    <span class="section-num-line"></span>
    <span class="section-num-label">named monkeys</span>
  </p>
  <h1 class="page-title">The cast</h1>
  <p class="page-sub">Eight characters with deterministic quirks · plus the daily leaderboard.</p>
</section>

{#if personality.length > 0}
  <section class="roster">
    <header class="roster-head">
      <h2 class="roster-title">Personalities</h2>
      <p class="roster-count">{personality.length} characters</p>
    </header>
    <div class="roster-grid">
      {#each personality as c}
        <a class="card" href={`/monkeys/${c.name}`}>
          <header class="card-head">
            <span class="card-name">{c.name}</span>
            {#if c.pct == null}
              <span class="card-delta neutral">— new</span>
            {:else}
              <span class="card-delta" class:up={c.pct >= 0} class:down={c.pct < 0}>
                {c.pct >= 0 ? "▲" : "▼"} {Math.abs(c.pct).toFixed(2)}%
              </span>
            {/if}
          </header>
          <p class="card-tagline">{c.tagline}</p>
          <div class="card-spark">
            {#if c.values.length > 1}
              <Sparkline values={c.values} height={60} variant={c.variant} />
            {:else}
              <div class="card-spark-empty">no history yet</div>
            {/if}
          </div>
          <footer class="card-foot">
            <span class="card-equity">{fmt(c.equity)}</span>
            <span class="card-id">#{c.monkey_id}</span>
          </footer>
        </a>
      {/each}
    </div>
  </section>
{/if}

{#if slots.length > 0}
  <section class="roster">
    <header class="roster-head">
      <h2 class="roster-title">Today's leaderboard</h2>
      <p class="roster-count">refreshed every tick</p>
    </header>
    <div class="table-wrap">
      <table class="data-table">
        <thead>
          <tr>
            <th class="left">Slot</th>
            <th class="left">Tagline</th>
            <th>Monkey ID</th>
            <th>Equity</th>
          </tr>
        </thead>
        <tbody>
          {#each slots as c}
            <tr>
              <td class="left">
                <a href={`/monkeys/${c.name}`} class="name-link">{c.name}</a>
              </td>
              <td class="left muted">{c.tagline}</td>
              <td class="muted">#{c.monkey_id}</td>
              <td class="strong">{fmt(c.equity)}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  </section>
{/if}

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

  .roster { margin-bottom: 48px; }
  .roster-head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    border-bottom: 1px solid var(--border);
    padding-bottom: 10px;
    margin-bottom: 16px;
  }
  .roster-title {
    font-family: var(--font-mono);
    font-size: 11px;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    margin: 0;
    color: var(--fg-dim);
    font-weight: 500;
  }
  .roster-count {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--fg-dim);
    margin: 0;
    letter-spacing: 0.04em;
  }

  /* 2-col character grid. Each row is 2 cards on desktop, 1 on mobile. */
  .roster-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 0;
    border-top: 1px solid var(--border);
    border-left: 1px solid var(--border);
  }
  .card {
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding: 20px;
    border-right: 1px solid var(--border);
    border-bottom: 1px solid var(--border);
    color: var(--fg);
    transition: background 0.18s ease, transform 0.18s ease;
  }
  .card:hover {
    background: var(--bg-elev);
  }
  .card:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: -2px;
  }

  .card-head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 12px;
  }
  .card-name {
    font-family: var(--font-serif);
    font-size: 17px;
    letter-spacing: -0.005em;
    line-height: 1.2;
  }
  .card-delta {
    font-family: var(--font-mono);
    font-size: 12px;
    letter-spacing: 0.02em;
    color: var(--fg-dim);
  }
  .card-delta.up { color: var(--c-up); }
  .card-delta.down { color: var(--c-down); }
  .card-delta.neutral { color: var(--fg-dim); letter-spacing: 0.04em; }

  .card-tagline {
    font-family: var(--font-mono);
    font-size: 11px;
    letter-spacing: 0.04em;
    color: var(--fg-muted);
    margin: 0;
    text-transform: lowercase;
  }

  .card-spark {
    min-height: 60px;
    display: flex;
    align-items: center;
  }
  .card-spark-empty {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--fg-dim);
    letter-spacing: 0.04em;
    text-align: center;
    width: 100%;
  }

  .card-foot {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    border-top: 1px dashed var(--border);
    padding-top: 8px;
  }
  .card-equity {
    font-family: var(--font-mono);
    font-size: 16px;
    font-weight: 500;
    letter-spacing: -0.005em;
  }
  .card-id {
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--fg-dim);
  }

  /* Daily-slot table reuses earlier dashboard styles. */
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
