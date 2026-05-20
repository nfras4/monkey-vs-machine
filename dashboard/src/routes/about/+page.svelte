<script lang="ts">
  // Static about page — explains what this is to first-time visitors.
</script>

<section>
  <h2>About</h2>

  <p>
    <strong>Monkey vs Machine</strong> is a long-running, fully simulated stock-trading
    experiment. Every US trading day, a single AI trader and an army of
    <strong>100,000 random "monkey" traders</strong> each make their next move on real
    historical S&amp;P 500 prices. The dashboard tracks all of them.
  </p>

  <h3>How it works</h3>
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

  <h3>What the AI is</h3>
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
      Designed to be swappable. The codebase keeps the AI behind a
      <code>MODELS</code> registry — adding a LightGBM or stacking ensemble later
      is one entry in a dict. The schema is model-keyed from day one.
    </li>
  </ul>

  <h3>Why monkeys</h3>
  <p>
    Markets are noisy enough that a single "AI beats the market" story is almost
    never falsifiable on a single run. A pack of 100,000 random traders gives a
    real null distribution: if the AI lands at the 50th percentile of the
    monkey pack, it's mostly noise. If it lands above the 95th percentile and
    keeps doing so, that's signal. The dashboard shows both lines so you can
    judge for yourself.
  </p>

  <h3>Caveats</h3>
  <ul>
    <li><strong>Survivorship bias:</strong> the universe is the <em>current</em>
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

  <h3>Source</h3>
  <p>
    Code on GitHub (link to be added). Built in Python + scikit-learn for compute,
    Cloudflare D1 + SvelteKit for the public dashboard, systemd for the daily
    timer.
  </p>
</section>

<style>
  section { max-width: 720px; }
  h2 { font-size: 22px; margin-bottom: 12px; }
  h3 { font-size: 16px; margin-top: 28px; margin-bottom: 8px; color: #1f2937; }
  p, li { font-size: 15px; line-height: 1.6; color: #1f2937; }
  ul { padding-left: 22px; }
  code { background: #f3f4f6; padding: 1px 5px; border-radius: 3px; font-size: 13px; }
</style>
