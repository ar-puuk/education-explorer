<script lang="ts">
  // A ranked-looking list is avoided on purpose: bars show one year's breakdown, in the order the source defines.
  import { tooltip } from '../lib/tooltip'
  export interface BarItem {
    label: string
    value: number
    /** text shown at the right; defaults to the plain value */
    text?: string
  }
  let { items, max, label }: { items: BarItem[]; max?: number; label: string } = $props()
  const top = $derived(max ?? Math.max(1, ...items.map((i) => i.value)))
</script>

<ul class="bars" aria-label={label}>
  {#each items as it}
    <li use:tooltip={`${it.label}: ${it.text ?? it.value.toLocaleString()}`}>
      <span class="lab">{it.label}</span>
      <span class="track" aria-hidden="true"><i style:width="{Math.max(1, Math.min(100, (it.value / top) * 100))}%"></i></span>
      <span class="val">{it.text ?? it.value.toLocaleString()}</span>
    </li>
  {/each}
</ul>

<style>
  .bars {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: 7px;
  }
  li {
    display: grid;
    grid-template-columns: minmax(0, 9.5rem) minmax(0, 1fr) auto;
    align-items: center;
    gap: 10px;
    font-size: 12px;
  }
  .lab {
    color: var(--text);
    overflow-wrap: anywhere;
  }
  .track {
    height: 9px;
    border-radius: 5px;
    background: var(--surface-2, var(--border));
    overflow: hidden;
  }
  i {
    display: block;
    height: 100%;
    border-radius: 5px;
    background: var(--chart-1);
  }
  .val {
    font-family: var(--f-data);
    font-variant-numeric: tabular-nums;
    color: var(--muted);
    min-width: 3.2rem;
    text-align: right;
  }
</style>
