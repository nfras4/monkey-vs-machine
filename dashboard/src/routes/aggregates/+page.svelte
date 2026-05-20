<script lang="ts">
  let { data } = $props();
</script>

<h2>Monkey percentile bands</h2>
<table>
  <thead><tr><th>Date</th><th>p5</th><th>p25</th><th>median</th><th>p75</th><th>p95</th><th>mean</th></tr></thead>
  <tbody>
    {#each data.aggregates as a}
      <tr>
        <td>{a.date}</td>
        <td>{a.monkey_p5.toFixed(0)}</td>
        <td>{a.monkey_p25.toFixed(0)}</td>
        <td>{a.monkey_median.toFixed(0)}</td>
        <td>{a.monkey_p75.toFixed(0)}</td>
        <td>{a.monkey_p95.toFixed(0)}</td>
        <td>{a.monkey_mean.toFixed(0)}</td>
      </tr>
    {/each}
  </tbody>
</table>

<style>
  table { width: 100%; border-collapse: collapse; font-size: 14px; }
  th, td { padding: 6px 10px; border-bottom: 1px solid #e5e7eb; text-align: right; }
  th:first-child, td:first-child { text-align: left; }
</style>
