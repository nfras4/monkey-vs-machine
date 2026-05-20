<script lang="ts">
  // Lightweight inline sparkline — no Chart.js dependency. Pure SVG.
  let { values, width = 600, height = 160, color = "#22c55e", fill = "rgba(34, 197, 94, 0.12)" }: {
    values: number[];
    width?: number;
    height?: number;
    color?: string;
    fill?: string;
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

<svg viewBox="0 0 {width} {height}" preserveAspectRatio="xMidYMid meet" role="img" aria-label="sparkline">
  <path d={area} fill={fill} stroke="none" />
  <path d={path} fill="none" stroke={color} stroke-width="2" stroke-linejoin="round" />
  {#if endPoint}
    <circle cx={endPoint.x} cy={endPoint.y} r="3" fill={color} />
    <text x={endPoint.x - 4} y={endPoint.y - 8} text-anchor="end" font-size="11" fill="#1a1a1a">
      {endPoint.label}
    </text>
  {/if}
</svg>

<style>
  svg { width: 100%; height: auto; display: block; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
</style>
