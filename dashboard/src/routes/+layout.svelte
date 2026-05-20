<script lang="ts">
  import { page } from "$app/state";
  import ThemeToggle from "$lib/components/ThemeToggle.svelte";

  let { children } = $props();

  const navItems = [
    { href: "/", label: "Race", num: "01" },
    { href: "/aggregates", label: "Aggregates", num: "02" },
    { href: "/monkeys", label: "Monkeys", num: "03" },
    { href: "/ai", label: "AI", num: "04" },
    { href: "/about", label: "About", num: "05" },
  ];

  let menuOpen = $state(false);
  let isMobile = $state(false);

  $effect(() => {
    const mq = window.matchMedia("(max-width: 800px)");
    const sync = () => {
      isMobile = mq.matches;
      if (!mq.matches) menuOpen = false;
    };
    sync();
    mq.addEventListener("change", sync);
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && menuOpen) menuOpen = false;
    };
    window.addEventListener("keydown", onKey);
    return () => {
      mq.removeEventListener("change", sync);
      window.removeEventListener("keydown", onKey);
    };
  });

  // On mobile, nav links must be unreachable to keyboard / SR when the menu is closed.
  const linksInert = $derived(isMobile && !menuOpen);

  function isCurrent(href: string) {
    const path = page.url.pathname;
    if (href === "/") return path === "/";
    return path === href || path.startsWith(href + "/");
  }
</script>

<svelte:head>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin="anonymous" />
  <link
    href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Lora:ital,wght@0,400;0,500;1,400&family=JetBrains+Mono:wght@400;500&display=swap"
    rel="stylesheet"
  />
</svelte:head>

<a href="#main" class="skip-link">Skip to main content</a>

<div class="page">
  <header class="nav">
    <div class="nav-inner shell">
      <a href="/" class="nav-brand">
        <span class="nav-brand-mark">mvm</span>
        <span class="nav-brand-slash">/</span>
        <span class="nav-brand-sub">monkey vs machine</span>
      </a>

      <nav id="primary-nav" class="nav-links" data-open={menuOpen} inert={linksInert ? true : undefined} aria-label="Primary">
        {#each navItems as item}
          <a
            class="nav-link"
            href={item.href}
            aria-current={isCurrent(item.href) ? "page" : undefined}
            onclick={() => (menuOpen = false)}
          >
            <span class="nav-link-num">{item.num}</span>{item.label}
          </a>
        {/each}
      </nav>

      <div class="nav-end">
        <ThemeToggle />
        <button
          class="nav-toggle"
          type="button"
          aria-label={menuOpen ? "Close navigation" : "Open navigation"}
          aria-expanded={menuOpen}
          aria-controls="primary-nav"
          onclick={() => (menuOpen = !menuOpen)}
        >
          <span></span><span></span><span></span>
        </button>
      </div>
    </div>
  </header>

  <main class="shell" id="main">
    {@render children()}
  </main>

  <footer class="footer">
    <div class="shell footer-inner">
      <span class="footer-blurb">
        <span class="muted">100,000 random monkeys</span> · sklearn HistGradientBoosting · daily ticks
      </span>
      <span class="footer-links">
        <a href="/about">methodology</a>
        <span class="footer-sep">·</span>
        <a href="https://github.com/nfras4/monkey-vs-machine" target="_blank" rel="noreferrer">github ↗</a>
      </span>
    </div>
  </footer>
</div>

<style>
  /* ============================================
     Design tokens — light (default) + dark
     Adapted from D:/claudecode/portfolio/src/styles.css
     ============================================ */
  :global(:root),
  :global([data-theme="light"]) {
    --bg: oklch(0.96 0.015 75);
    --bg-elev: oklch(0.93 0.022 70);
    --bg-card: oklch(0.89 0.028 70);
    --border: oklch(0.78 0.04 70);
    --border-strong: oklch(0.62 0.06 60);
    --fg: oklch(0.21 0.04 50);
    --fg-muted: oklch(0.36 0.05 55);
    --fg-dim: oklch(0.44 0.05 60);
    --accent: oklch(0.46 0.16 42);
    --accent-soft: oklch(0.46 0.16 42 / 0.14);

    /* Race palette — calibrated for warm paper */
    --c-ai: oklch(0.55 0.16 145);
    --c-ai-soft: oklch(0.55 0.16 145 / 0.14);
    --c-spy: oklch(0.5 0.03 60);
    --c-monkey: oklch(0.66 0.15 75);
    --c-monkey-soft: oklch(0.66 0.15 75 / 0.16);
    --c-best: oklch(0.55 0.18 28);
    --c-up: oklch(0.5 0.14 145);
    --c-down: oklch(0.5 0.18 28);

    --font-sans: "Inter", "Helvetica Neue", Helvetica, Arial, sans-serif;
    --font-serif: "Lora", "Iowan Old Style", Georgia, serif;
    --font-mono: "JetBrains Mono", "SF Mono", Menlo, Consolas, monospace;

    --r-sm: 4px;
    --r-md: 8px;
    --r-lg: 12px;

    color-scheme: light;
  }

  :global([data-theme="dark"]) {
    --bg: oklch(0.19 0.012 60);
    --bg-elev: oklch(0.235 0.015 60);
    --bg-card: oklch(0.27 0.02 60);
    --border: oklch(0.36 0.025 60);
    --border-strong: oklch(0.52 0.04 60);
    --fg: oklch(0.95 0.012 80);
    --fg-muted: oklch(0.78 0.02 70);
    --fg-dim: oklch(0.62 0.025 65);
    --accent: oklch(0.74 0.16 50);
    --accent-soft: oklch(0.74 0.16 50 / 0.18);

    --c-ai: oklch(0.78 0.17 145);
    --c-ai-soft: oklch(0.78 0.17 145 / 0.18);
    --c-spy: oklch(0.7 0.02 70);
    --c-monkey: oklch(0.8 0.15 78);
    --c-monkey-soft: oklch(0.8 0.15 78 / 0.18);
    --c-best: oklch(0.72 0.19 28);
    --c-up: oklch(0.78 0.17 145);
    --c-down: oklch(0.72 0.19 28);

    color-scheme: dark;
  }

  :global(*) { box-sizing: border-box; }

  :global(html) {
    scroll-behavior: smooth;
    overflow-x: clip;
  }

  :global(html, body) {
    margin: 0;
    padding: 0;
    background: var(--bg);
    color: var(--fg);
    font-family: var(--font-sans);
    font-size: 16px;
    line-height: 1.55;
    -webkit-font-smoothing: antialiased;
    text-rendering: optimizeLegibility;
    transition: background 0.25s ease, color 0.25s ease;
  }

  :global(body) {
    min-height: 100vh;
    overflow-x: hidden;
    font-feature-settings: "cv11", "ss01";
  }

  :global(a) { color: inherit; text-decoration: none; }
  :global(button) {
    font-family: inherit;
    cursor: pointer;
    border: none;
    background: none;
    color: inherit;
  }
  :global(::selection) { background: var(--accent); color: var(--bg); }
  :global(:focus) { outline: none; }
  :global(:focus-visible) {
    outline: 2px solid var(--accent);
    outline-offset: 3px;
    border-radius: 2px;
  }
  :global(code) {
    font-family: var(--font-mono);
    font-size: 0.92em;
    background: var(--bg-card);
    border: 1px solid var(--border);
    padding: 1px 6px;
    border-radius: var(--r-sm);
    color: var(--fg);
  }
  :global(table) { font-variant-numeric: tabular-nums; }

  :global(::-webkit-scrollbar) { width: 10px; height: 10px; }
  :global(::-webkit-scrollbar-track) { background: var(--bg); }
  :global(::-webkit-scrollbar-thumb) {
    background: var(--border-strong);
    border-radius: 5px;
  }

  @media (prefers-reduced-motion: reduce) {
    :global(html) { scroll-behavior: auto; }
    :global(*, *::before, *::after) {
      animation-duration: 0.01ms !important;
      animation-iteration-count: 1 !important;
      transition-duration: 0.01ms !important;
    }
  }

  /* ============================================
     Shell / layout
     ============================================ */
  :global(.shell) {
    width: 100%;
    max-width: 1180px;
    margin: 0 auto;
    padding: 0 40px;
  }
  @media (max-width: 600px) {
    :global(.shell) { padding: 0 20px; }
  }

  :global(.mono) { font-family: var(--font-mono); }
  :global(.serif) { font-family: var(--font-serif); }
  :global(.muted) { color: var(--fg-muted); }

  /* ============================================
     Nav
     ============================================ */
  .page { display: flex; flex-direction: column; min-height: 100vh; }

  /* Skip link — visible when keyboard-focused */
  .skip-link {
    position: absolute;
    top: 8px;
    left: 8px;
    z-index: 100;
    padding: 10px 14px;
    background: var(--accent);
    color: var(--bg);
    font-family: var(--font-mono);
    font-size: 12px;
    letter-spacing: 0.04em;
    border-radius: var(--r-sm);
    transform: translateY(-150%);
    transition: transform 0.18s ease;
  }
  .skip-link:focus-visible {
    transform: translateY(0);
    outline: 2px solid var(--fg);
    outline-offset: 2px;
  }
  .nav {
    position: sticky;
    top: 0;
    z-index: 50;
    background: color-mix(in oklch, var(--bg) 82%, transparent);
    backdrop-filter: blur(12px) saturate(140%);
    -webkit-backdrop-filter: blur(12px) saturate(140%);
    border-bottom: 1px solid var(--border);
  }
  .nav-inner {
    display: flex;
    align-items: center;
    justify-content: space-between;
    height: 64px;
    gap: 24px;
  }
  .nav-brand {
    display: inline-flex;
    align-items: baseline;
    gap: 6px;
    font-family: var(--font-mono);
    font-size: 13px;
    letter-spacing: 0.04em;
    color: var(--fg);
  }
  .nav-brand-mark { font-weight: 600; }
  .nav-brand-slash { color: var(--fg-dim); }
  .nav-brand-sub {
    color: var(--fg-muted);
    font-size: 12px;
    letter-spacing: 0.02em;
  }
  @media (max-width: 720px) {
    .nav-brand-sub { display: none; }
  }

  .nav-links {
    display: flex;
    gap: 24px;
  }
  .nav-link {
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--fg-muted);
    letter-spacing: 0.02em;
    transition: color 0.15s ease;
  }
  .nav-link:hover { color: var(--fg); }
  .nav-link[aria-current="true"] { color: var(--fg); }
  .nav-link[aria-current="true"] .nav-link-num { color: var(--accent); }
  .nav-link-num { color: var(--fg-dim); margin-right: 6px; }

  .nav-end {
    display: inline-flex;
    align-items: center;
    gap: 10px;
  }

  .nav-toggle {
    display: none;
    width: 40px;
    height: 40px;
    align-items: center;
    justify-content: center;
    flex-direction: column;
    gap: 4px;
    padding: 0;
  }
  .nav-toggle span {
    display: block;
    width: 18px;
    height: 1.5px;
    background: var(--fg);
    transition: transform 0.2s ease, opacity 0.2s ease;
  }
  .nav-toggle[aria-expanded="true"] span:nth-child(1) {
    transform: translateY(5.5px) rotate(45deg);
  }
  .nav-toggle[aria-expanded="true"] span:nth-child(2) { opacity: 0; }
  .nav-toggle[aria-expanded="true"] span:nth-child(3) {
    transform: translateY(-5.5px) rotate(-45deg);
  }

  @media (max-width: 800px) {
    .nav-toggle { display: inline-flex; }
    .nav-links {
      position: absolute;
      top: 64px;
      left: 0;
      right: 0;
      flex-direction: column;
      gap: 0;
      background: color-mix(in oklch, var(--bg) 96%, transparent);
      backdrop-filter: blur(12px) saturate(140%);
      -webkit-backdrop-filter: blur(12px) saturate(140%);
      border-bottom: 1px solid var(--border);
      padding: 8px 40px 16px;
      transform: translateY(-12px);
      opacity: 0;
      pointer-events: none;
      transition: transform 0.2s ease, opacity 0.2s ease;
    }
    .nav-links[data-open="true"] {
      transform: translateY(0);
      opacity: 1;
      pointer-events: auto;
    }
    .nav-link {
      padding: 14px 0;
      font-size: 14px;
      border-top: 1px solid var(--border);
    }
    .nav-link:first-child { border-top: none; }
  }

  /* ============================================
     Main + footer
     ============================================ */
  main {
    flex: 1;
    padding: 48px 40px 80px;
    width: 100%;
    max-width: 1180px;
    margin: 0 auto;
    box-sizing: border-box;
  }
  @media (max-width: 600px) {
    main { padding: 28px 20px 56px; }
  }

  .footer {
    border-top: 1px solid var(--border);
    background: var(--bg);
    padding: 28px 0 40px;
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--fg-dim);
  }
  .footer-inner {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 12px;
  }
  .footer-blurb { letter-spacing: 0.02em; }
  .footer-blurb .muted { color: var(--fg-muted); }
  .footer-links { display: inline-flex; gap: 10px; align-items: baseline; }
  .footer-links a { color: var(--fg-muted); transition: color 0.15s ease; }
  .footer-links a:hover { color: var(--fg); }
  .footer-sep { color: var(--fg-dim); }
</style>
