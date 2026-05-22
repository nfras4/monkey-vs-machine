<script lang="ts">
  // % monkeys above starting cash over time. Theme-aware via CSS vars,
  // same `mvm:theme` rebuild pattern as EquityChart.
  let {
    dates,
    pct,
    height = "260px",
  }: {
    dates: string[];
    pct: number[]; // 0-100
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
    if (!color) return `rgba(0,0,0,${alpha})`;
    if (color.includes("/")) return color;
    if (color.startsWith("oklch(")) return color.replace(/\)$/, ` / ${alpha})`);
    return `color-mix(in oklch, ${color} ${Math.round(alpha * 100)}%, transparent)`;
  }

  function build() {
    if (!ChartCtor || !canvas) return;
    if (chartInstance) chartInstance.destroy();
    const cMonkey = cssVar("--c-monkey") || "#f59e0b";
    const cFgDim = cssVar("--fg-dim") || "#9ca3af";
    const cFgMuted = cssVar("--fg-muted") || "#6b7280";
    const cFg = cssVar("--fg") || "#1f2937";
    const cBorder = cssVar("--border") || "#e5e7eb";
    const cBgElev = cssVar("--bg-elev") || "#fff";

    chartInstance = new ChartCtor(canvas!, {
      type: "line",
      data: {
        labels: dates,
        datasets: [
          {
            label: "% above starting cash",
            data: pct,
            borderColor: cMonkey,
            backgroundColor: withAlpha(cMonkey, 0.15),
            borderWidth: 2,
            pointRadius: 0,
            tension: 0.15,
            fill: "origin",
          },
        ],
      },
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
              label: (ctx: any) => `${ctx.parsed.y.toFixed(1)}% of monkeys above $10k`,
            },
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
            min: 0,
            max: 100,
            grid: { color: withAlpha(cBorder, 0.5), tickLength: 0 },
            border: { display: false },
            ticks: {
              color: cFgDim,
              stepSize: 25,
              font: { family: "JetBrains Mono, monospace", size: 10 },
              callback: (v: any) => `${v}%`,
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
  <canvas
    bind:this={canvas}
    aria-label="Time series of percentage of monkeys above starting cash"
  ></canvas>
</div>

<style>
  .chart-wrap { position: relative; width: 100%; }
</style>
