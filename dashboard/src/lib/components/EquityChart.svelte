<script lang="ts">
  // Chart.js race chart — AI vs SPY vs monkey median (with 5-95 band).
  // Colors are pulled from CSS custom properties so the chart matches the
  // active theme; rebuilds on `mvm:theme` events.
  let {
    dates,
    aiEquity,
    spyEquity,
    monkeyMedian,
    monkeyP5,
    monkeyP95,
    monkeyBest,
    variant = "all",
    height = "440px",
  }: {
    dates: string[];
    aiEquity: (number | null)[];
    spyEquity: (number | null)[];
    monkeyMedian: number[];
    monkeyP5: number[];
    monkeyP95: number[];
    monkeyBest: number[];
    // "all"        — every series (default; preserves pre-split behaviour)
    // "ai-vs-spy"  — only AI + SPY (the head-to-head head-to-bench race)
    // "monkey-band"— only monkey p5/p95 band + median + best (the pack distribution)
    variant?: "all" | "ai-vs-spy" | "monkey-band";
    height?: string;
  } = $props();

  let canvas: HTMLCanvasElement | undefined = $state();
  let chartInstance: { destroy: () => void } | null = null;
  let ChartCtor: any = null;

  function cssVar(name: string): string {
    if (typeof window === "undefined") return "";
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }

  function withAlpha(color: string, alpha: number): string {
    // oklch(L C H) -> oklch(L C H / alpha) using CSS color-mix if needed.
    if (!color) return `rgba(0,0,0,${alpha})`;
    if (color.includes("/")) return color;
    if (color.startsWith("oklch(")) {
      return color.replace(/\)$/, ` / ${alpha})`);
    }
    return `color-mix(in oklch, ${color} ${Math.round(alpha * 100)}%, transparent)`;
  }

  function build() {
    if (!ChartCtor || !canvas) return;
    if (chartInstance) chartInstance.destroy();

    const cAi = cssVar("--c-ai") || "#22c55e";
    const cSpy = cssVar("--c-spy") || "#6b7280";
    const cMonkey = cssVar("--c-monkey") || "#f59e0b";
    const cBest = cssVar("--c-best") || "#ef4444";
    const cFg = cssVar("--fg") || "#1f2937";
    const cFgMuted = cssVar("--fg-muted") || "#6b7280";
    const cFgDim = cssVar("--fg-dim") || "#9ca3af";
    const cBorder = cssVar("--border") || "#e5e7eb";
    const cBgElev = cssVar("--bg-elev") || "#ffffff";

    const monkeyDatasets = [
      {
        label: "Monkey 5-95% band",
        data: monkeyP95,
        fill: "+1",
        backgroundColor: withAlpha(cMonkey, 0.14),
        borderColor: withAlpha(cMonkey, 0.35),
        borderWidth: 1,
        pointRadius: 0,
        tension: 0,
      },
      {
        label: "p5",
        data: monkeyP5,
        fill: false,
        borderColor: withAlpha(cMonkey, 0.35),
        borderWidth: 1,
        pointRadius: 0,
        tension: 0,
      },
      {
        label: "Monkey median",
        data: monkeyMedian,
        borderColor: cMonkey,
        backgroundColor: withAlpha(cMonkey, 0.1),
        borderWidth: 2,
        pointRadius: 0,
        tension: 0.1,
      },
    ];
    // The lucky-monkey-today line is informative but blows out the y-axis on
    // the monkey-band variant (one monkey can be +20% while the median band
    // sits within ±3%). Keep it only on the "all" variant; the KPI card
    // already surfaces the current best-monkey equity.
    const bestDataset = {
      label: "Best monkey today",
      data: monkeyBest,
      borderColor: cBest,
      borderWidth: 1.5,
      borderDash: [4, 3],
      pointRadius: 0,
      tension: 0,
    };
    const aiSpyDatasets = [
      {
        label: "AI trader",
        data: aiEquity,
        borderColor: cAi,
        backgroundColor: withAlpha(cAi, 0.12),
        borderWidth: 3,
        pointRadius: 0,
        tension: 0.1,
      },
      {
        label: "SPY benchmark",
        data: spyEquity,
        borderColor: cSpy,
        borderWidth: 2,
        borderDash: [6, 4],
        pointRadius: 0,
        tension: 0.1,
      },
    ];

    const datasets =
      variant === "ai-vs-spy"
        ? aiSpyDatasets
        : variant === "monkey-band"
          ? monkeyDatasets // intentionally excludes bestDataset — see above
          : [...monkeyDatasets, bestDataset, ...aiSpyDatasets];

    chartInstance = new ChartCtor(canvas!, {
      type: "line",
      data: { labels: dates, datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: cBgElev,
            titleColor: cFg,
            bodyColor: cFgMuted,
            borderColor: cBorder,
            borderWidth: 1,
            padding: 10,
            titleFont: { family: "JetBrains Mono, monospace", size: 11 },
            bodyFont: { family: "JetBrains Mono, monospace", size: 12 },
            callbacks: {
              label: (ctx: any) => {
                const v = ctx.parsed.y;
                if (v == null) return `${ctx.dataset.label}: —`;
                return `${ctx.dataset.label}: $${v.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
              },
            },
            filter: (item: any) => item.dataset.label !== "p5",
          },
        },
        scales: {
          x: {
            grid: { display: false },
            border: { color: cBorder },
            ticks: {
              color: cFgDim,
              maxTicksLimit: 8,
              font: { family: "JetBrains Mono, monospace", size: 10 },
            },
          },
          y: {
            grid: { color: withAlpha(cBorder, 0.5), tickLength: 0 },
            border: { display: false },
            ticks: {
              color: cFgDim,
              font: { family: "JetBrains Mono, monospace", size: 10 },
              callback: (v: any) => `$${Number(v).toLocaleString(undefined, { maximumFractionDigits: 0 })}`,
            },
          },
        },
      },
    });
  }

  $effect(() => {
    if (!canvas) return;
    let cancelled = false;

    (async () => {
      const ChartMod = await import("chart.js/auto");
      if (cancelled) return;
      ChartCtor = (ChartMod as any).default ?? ChartMod.Chart;
      build();
    })();

    const onTheme = () => build();
    window.addEventListener("mvm:theme", onTheme);

    return () => {
      cancelled = true;
      window.removeEventListener("mvm:theme", onTheme);
      if (chartInstance) {
        chartInstance.destroy();
        chartInstance = null;
      }
    };
  });
</script>

<div class="chart-wrap" style="height: {height};">
  <canvas bind:this={canvas} aria-label="Equity curve: AI trader vs SPY benchmark vs monkey median and percentile band"></canvas>
</div>

<style>
  .chart-wrap {
    position: relative;
    width: 100%;
  }
</style>
