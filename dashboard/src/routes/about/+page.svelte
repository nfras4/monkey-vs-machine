<script lang="ts">
  // Static about page — explains what this is to first-time visitors.
</script>

<article class="prose">
  <p class="section-num">
    <span class="section-num-num">05</span>
    <span class="section-num-line"></span>
    <span class="section-num-label">about</span>
  </p>

  <h1 class="title">What this is</h1>

  <p class="lede">
    <strong>Monkey vs Machine</strong> is a fully simulated stock-trading
    experiment. Every US trading day, a single AI trader and an army of
    <strong>100,000 random "monkey" traders</strong> each make their next move on real
    historical S&amp;P 500 prices. The dashboard tracks all of them.
  </p>

  <h2>How it works</h2>
  <ul>
    <li>
      Once per US trading day, a "tick" runs on a dedicated Linux box. The tick
      fetches the new daily bar, retrains the AI on every available
      day of price history, and rebalances the AI's portfolio into the top-10
      stocks it predicts will rise over the next 5 days.
    </li>
    <li>
      Each of the 100,000 monkeys advances one day too. Each monkey holds at most
      one stock at a time. On any given day a monkey has a 5% chance of trading;
      when it does, half the time it sells what it holds and half the time it
      buys a uniformly-random ticker from the universe.
    </li>
    <li>
      Both the AI and the monkeys start with the same $10,000 in cash and pay the
      same 5-basis-point cost on every trade. The race is over real bars; there
      is no look-ahead.
    </li>
  </ul>

  <h2>What the AI is</h2>
  <ul>
    <li>
      A scikit-learn HistGradientBoosting classifier trained on engineered price
      features: 1/5/20-day returns, 14-day RSI, MACD signal, 20/60-day return
      volatility, volume z-score, and abnormal return.
    </li>
    <li>
      Walk-forward retrained every tick with a 5-day forward-return target. The
      training window's edge is shifted back by the forecast horizon so the
      label can never peek at the prediction date.
    </li>
    <li>
      Swappable by design. The codebase keeps the AI behind a
      <code>MODELS</code> registry. Adding a LightGBM or stacking ensemble later
      is one entry in a dict. The schema is model-keyed from day one.
    </li>
  </ul>

  <h2>Why monkeys</h2>
  <p>
    Markets are noisy enough that a single "AI beats the market" story is almost
    never falsifiable on a single run. A pack of 100,000 random traders gives a
    real null distribution: if the AI lands at the 50th percentile of the
    monkey pack, it's mostly noise. If it lands above the 95th percentile and
    keeps doing so, that's signal. The dashboard shows both lines so you can
    judge for yourself.
  </p>

  <h2>Caveats</h2>
  <ul>
    <li><strong>Survivorship bias.</strong> The universe is the <em>current</em>
      S&amp;P 500 fallback list. Companies that dropped out are missing.</li>
    <li><strong>No real money.</strong> The AI's picks are not placed on any
      broker. A stub interface exists for a future Alpaca-paper integration.</li>
    <li><strong>Live news is decoration, not training.</strong> Historical news
      isn't available retroactively, so the AI is trained on price-derived
      attention proxies rather than real sentiment.</li>
    <li><strong>Deterministic.</strong> A tick re-run on the same date with the
      same pinned environment produces byte-identical state. See
      <code>DETERMINISM.md</code> in the repo for the contract.</li>
  </ul>

  <h2>How a tick actually runs</h2>
  <p>
    Every weekday afternoon (Brisbane time) my laptop wakes up and the Windows
    Task Scheduler logon trigger fires <code>update.ps1</code>. That script
    walks any missed weekdays via <code>scripts/catchup.py</code>, runs the
    simulation locally, then POSTs the published rows to
    <code>/admin/ingest</code> on this dashboard. Cloudflare D1 stores the
    public mirror; the SvelteKit pages you're looking at read from D1 with a
    60-second edge cache. The 100,000 unnamed monkeys live in a SQLite file
    on the laptop and never get pushed.
  </p>

  <h2>Source</h2>
  <p>
    Code on <a href="https://github.com/nfras4/monkey-vs-machine" target="_blank" rel="noreferrer">GitHub ↗</a>.
    Compute is Python + scikit-learn; the dashboard is Svelte 5 + Chart.js
    deployed on Cloudflare Pages with a D1 read-only mirror.
  </p>
</article>

<style>
  .prose {
    max-width: 720px;
    margin: 0 auto;
  }
  .section-num {
    font-family: var(--font-mono);
    font-size: 11px;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    margin: 0 0 28px;
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

  .title {
    font-family: var(--font-serif);
    font-size: clamp(32px, 4.5vw, 48px);
    letter-spacing: -0.02em;
    font-weight: 500;
    margin: 0 0 32px;
    line-height: 1.1;
    text-wrap: balance;
  }

  .lede {
    font-size: clamp(17px, 2vw, 19px);
    line-height: 1.55;
    color: var(--fg);
    margin: 0 0 40px;
    text-wrap: pretty;
  }

  h2 {
    font-family: var(--font-mono);
    font-size: 11px;
    letter-spacing: 0.18em;
    color: var(--fg-dim);
    text-transform: uppercase;
    margin: 48px 0 16px;
    padding-top: 24px;
    border-top: 1px solid var(--border);
    font-weight: 500;
  }

  p, li {
    font-size: 16px;
    line-height: 1.65;
    color: var(--fg-muted);
    text-wrap: pretty;
  }

  p { margin: 0 0 16px; }
  ul { padding-left: 0; list-style: none; margin: 0 0 16px; }
  li {
    display: flex;
    gap: 14px;
    margin-bottom: 10px;
  }
  li::before {
    content: "→";
    color: var(--accent);
    font-family: var(--font-mono);
    flex-shrink: 0;
  }

  strong { color: var(--fg); font-weight: 500; }
  em { color: var(--fg); font-style: italic; }
  a { color: var(--accent); transition: color 0.15s ease; }
  a:hover { color: var(--fg); }
</style>
