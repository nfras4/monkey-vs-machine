<script lang="ts">
  // Lightweight inline sparkline — pure SVG, theme-aware via currentColor.
  let { values, width = 600, height = 160, variant = "ai" }: {
    values: number[];
    width?: number;
    height?: number;
    variant?: "ai" | "monkey" | "spy" | "best";
  } = $props();

  const pad = 4;
  let path = $derived.by(() => {
    if (!values || values.length === 0) return "";
    const min = Math.min(...values);
    const max = Math.max(...values);
    const span = max - min || 1;
    return values
      .map((v, i) => {
        const x = pad + (i / Math.max(1, values.length - 1)) * (width - 2 * pad);
        const y = height - pad - ((v - min) / span) * (height - 2 * pad);
        return `${i === 0 ? "M" : "L"}${x.toFixed(2)},${y.toFixed(2)}`;
      })
      .join(" ");
  });
  let area = $derived.by(() => {
    if (!path) return "";
    return `${path} L${width - pad},${height - pad} L${pad},${height - pad} Z`;
  });
  let endPoint = $derived.by(() => {
    if (!values || values.length === 0) return null;
    const min = Math.min(...values);
    const max = Math.max(...values);
    const span = max - min || 1;
    const v = values[values.length - 1];
    return {
      x: width - pad,
      y: height - pad - ((v - min) / span) * (height - 2 * pad),
      label: `$${v.toLocaleString(undefined, { maximumFractionDigits: 0 })}`,
    };
  });
</script>

<svg
  class="sparkline sparkline--{variant}"
  viewBox="0 0 {width} {height}"
  preserveAspectRatio="xMidYMid meet"
  role="img"
  aria-label="sparkline"
>
  <path class="area" d={area} />
  <path class="line" d={path} />
  {#if endPoint}
    <circle class="dot" cx={endPoint.x} cy={endPoint.y} r="3" />
    <text class="end-label" x={endPoint.x - 6} y={endPoint.y - 8} text-anchor="end">
      {endPoint.label}
    </text>
  {/if}
</svg>

<style>
  .sparkline {
    width: 100%;
    height: auto;
    display: block;
    font-family: var(--font-mono);
  }
  .sparkline--ai     { --spark: var(--c-ai); }
  .sparkline--monkey { --spark: var(--c-monkey); }
  .sparkline--spy    { --spark: var(--c-spy); }
  .sparkline--best   { --spark: var(--c-best); }

  .area {
    fill: color-mix(in oklch, var(--spark) 14%, transparent);
    stroke: none;
  }
  .line {
    fill: none;
    stroke: var(--spark);
    stroke-width: 2;
    stroke-linejoin: round;
  }
  .dot { fill: var(--spark); }
  .end-label {
    font-size: 11px;
    fill: var(--fg);
  }
</style>
