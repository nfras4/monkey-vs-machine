<script lang="ts">
  let { children } = $props();
</script>

<svelte:head>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin="anonymous" />
  <link
    href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap"
    rel="stylesheet"
  />
</svelte:head>

<div class="page">
  <header>
    <div class="brand">
      <span class="emoji" aria-hidden>🐒</span>
      <span class="brand-name">Monkey vs Machine</span>
    </div>
    <nav>
      <a href="/">Race</a>
      <a href="/aggregates">Aggregates</a>
      <a href="/monkeys">Named monkeys</a>
      <a href="/ai">AI internals</a>
      <a href="/about">About</a>
    </nav>
  </header>

  <main>
    {@render children()}
  </main>

  <footer>
    <p>
      100,000 random monkeys vs a sklearn HistGradientBoosting classifier · daily ticks · <a href="/about">read the methodology</a>
    </p>
  </footer>
</div>

<style>
  :global(:root) {
    --ink: #111827;
    --muted: #6b7280;
    --line: #e5e7eb;
    --bg: #fafafa;
    --card: #ffffff;
    --green: #22c55e;
    --amber: #f59e0b;
    --red: #ef4444;
    --slate: #6b7280;
    --blue: #1d4ed8;
  }
  :global(body) {
    font-family: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    margin: 0;
    background: var(--bg);
    color: var(--ink);
    font-feature-settings: "cv11", "ss01";
  }
  :global(table) { font-variant-numeric: tabular-nums; }
  :global(code) {
    font-family: "JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  }
  .page { display: flex; flex-direction: column; min-height: 100vh; }
  header {
    border-bottom: 1px solid var(--line);
    padding: 14px 32px;
    background: var(--card);
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 32px;
    position: sticky;
    top: 0;
    z-index: 10;
  }
  .brand { display: flex; align-items: center; gap: 10px; }
  .emoji { font-size: 22px; line-height: 1; }
  .brand-name {
    font-weight: 700;
    font-size: 16px;
    letter-spacing: -0.01em;
  }
  nav { display: flex; gap: 22px; font-size: 14px; }
  nav a { color: var(--ink); text-decoration: none; font-weight: 500; }
  nav a:hover { color: var(--blue); }
  main { max-width: 1100px; width: 100%; margin: 0 auto; padding: 28px 32px; flex: 1; box-sizing: border-box; }
  footer {
    border-top: 1px solid var(--line);
    background: var(--card);
    padding: 14px 32px;
    color: var(--muted);
    font-size: 13px;
  }
  footer a { color: var(--muted); }
  footer p { margin: 0; }
  @media (max-width: 720px) {
    header { flex-direction: column; align-items: flex-start; gap: 10px; padding: 12px 20px; }
    nav { flex-wrap: wrap; gap: 14px; }
    main { padding: 20px; }
  }
</style>
