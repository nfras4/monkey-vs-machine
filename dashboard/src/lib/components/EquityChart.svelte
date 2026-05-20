<script lang="ts">
  // Chart.js race chart — AI vs SPY vs monkey median (with 5-95 band).
  // Lazy-loads chart.js so the bundle doesn't pay for it on tabs that don't need a chart.
  // Uses Svelte 5 `$effect` per Nick's runes-gotcha note (onMount tree-shakes in prod).
  let { dates, aiEquity, spyEquity, monkeyMedian, monkeyP5, monkeyP95, monkeyBest }: {
    dates: string[];
    aiEquity: (number | null)[];
    spyEquity: (number | null)[];
    monkeyMedian: number[];
    monkeyP5: number[];
    monkeyP95: number[];
    monkeyBest: number[];
  } = $props();

  let canvas: HTMLCanvasElement | undefined = $state();
  let chartInstance: { destroy: () => void } | null = null;

  $effect(() => {
    if (!canvas) return;
    let cancelled = false;

    (async () => {
      const ChartMod = await import("chart.js/auto");
      if (cancelled || !canvas) return;
      const Chart = (ChartMod as unknown as { default: typeof ChartMod.Chart }).default ?? ChartMod.Chart;
      if (chartInstance) chartInstance.destroy();

      chartInstance = new Chart(canvas, {
        type: "line",
        data: {
          labels: dates,
          datasets: [
            {
              label: "Monkey 5-95% band",
              data: monkeyP95,
              fill: "+1",
              backgroundColor: "rgba(245, 158, 11, 0.12)",
              borderColor: "rgba(245, 158, 11, 0.4)",
              borderWidth: 1,
              pointRadius: 0,
              tension: 0,
            },
            {
              label: "p5",
              data: monkeyP5,
              fill: false,
              borderColor: "rgba(245, 158, 11, 0.4)",
              borderWidth: 1,
              pointRadius: 0,
              tension: 0,
            },
            {
              label: "Monkey median",
              data: monkeyMedian,
              borderColor: "#f59e0b",
              backgroundColor: "rgba(245, 158, 11, 0.1)",
              borderWidth: 2,
              pointRadius: 0,
              tension: 0.1,
            },
            {
              label: "Best monkey today",
              data: monkeyBest,
              borderColor: "#ef4444",
              borderWidth: 1.5,
              borderDash: [4, 3],
              pointRadius: 0,
              tension: 0,
            },
            {
              label: "AI trader",
              data: aiEquity,
              borderColor: "#22c55e",
              backgroundColor: "rgba(34, 197, 94, 0.1)",
              borderWidth: 3,
              pointRadius: 0,
              tension: 0.1,
            },
            {
              label: "SPY benchmark",
              data: spyEquity,
              borderColor: "#6b7280",
              borderWidth: 2,
              borderDash: [6, 4],
              pointRadius: 0,
              tension: 0.1,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          interaction: { mode: "index", intersect: false },
          plugins: {
            legend: {
              labels: {
                // Hide the auxiliary p5 dataset from the legend (it's just the band's lower edge)
                filter: (item) => item.text !== "p5",
              },
            },
            tooltip: {
              callbacks: {
                label: (ctx) => {
                  const v = ctx.parsed.y;
                  if (v == null) return `${ctx.dataset.label}: —`;
                  return `${ctx.dataset.label}: $${v.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
                },
              },
            },
          },
          scales: {
            x: { grid: { display: false }, ticks: { maxTicksLimit: 10 } },
            y: {
              ticks: {
                callback: (v) => `$${Number(v).toLocaleString(undefined, { maximumFractionDigits: 0 })}`,
              },
            },
          },
        },
      });
    })();

    return () => {
      cancelled = true;
      if (chartInstance) {
        chartInstance.destroy();
        chartInstance = null;
      }
    };
  });
</script>

<div class="chart-wrap">
  <canvas bind:this={canvas} aria-label="Equity curve: AI trader vs SPY benchmark vs monkey median and percentile band"></canvas>
</div>

<style>
  .chart-wrap {
    position: relative;
    height: 420px;
    width: 100%;
  }
</style>
