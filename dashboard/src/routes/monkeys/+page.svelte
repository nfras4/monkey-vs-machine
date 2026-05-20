<script lang="ts">
  let { data } = $props();
</script>

<h2>Named monkeys</h2>
<table>
  <thead><tr><th>Name</th><th>Category</th><th>Monkey ID</th><th>Equity</th></tr></thead>
  <tbody>
    {#each data.named as m}
      <tr>
        <td><a href={`/monkeys/${m.name}`}>{m.name}</a></td>
        <td>{m.category}</td>
        <td>#{m.monkey_id}</td>
        <td>${m.equity.toFixed(0)}</td>
      </tr>
    {/each}
  </tbody>
</table>

<style>
  table { width: 100%; border-collapse: collapse; font-size: 14px; }
  th, td { padding: 6px 10px; border-bottom: 1px solid #e5e7eb; text-align: right; }
  th:first-child, td:first-child { text-align: left; }
  a { color: #1d4ed8; }
</style>
