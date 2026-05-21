<script lang="ts">
  // Generic two-column wrapper. Collapses to single-column when the container
  // (not the viewport) is narrower than `breakpoint`, so a SplitPanel inside
  // a constrained sidebar collapses correctly even on a wide viewport.
  // Used by home (chart split), /monkeys (character roster), /aggregates
  // (tendency vs percentiles).
  let {
    left,
    right,
    breakpoint = 800,
    gap = 24,
    title = "",
    sub = "",
  }: {
    left: import("svelte").Snippet;
    right: import("svelte").Snippet;
    breakpoint?: number;
    gap?: number;
    title?: string;
    sub?: string;
  } = $props();

  const styleVar = `--split-breakpoint: ${breakpoint}px; --split-gap: ${gap}px;`;
</script>

{#if title || sub}
  <header class="split-head">
    {#if title}<h2 class="split-title">{title}</h2>{/if}
    {#if sub}<p class="split-sub">{sub}</p>{/if}
  </header>
{/if}

<div class="split-container" style={styleVar}>
  <div class="split">
    <div class="split-side split-left">{@render left()}</div>
    <div class="split-side split-right">{@render right()}</div>
  </div>
</div>

<style>
  .split-head { margin-bottom: 20px; }
  .split-title {
    font-family: var(--font-serif);
    font-size: clamp(22px, 2.4vw, 28px);
    letter-spacing: -0.015em;
    font-weight: 500;
    margin: 0 0 4px;
  }
  .split-sub {
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--fg-muted);
    margin: 0;
    letter-spacing: 0.02em;
  }

  .split-container { container-type: inline-size; }

  .split {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--split-gap);
    align-items: start;
  }
  .split-side { min-width: 0; }

  @container (max-width: 800px) {
    .split { grid-template-columns: 1fr; }
  }
</style>
