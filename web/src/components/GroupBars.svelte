<script lang="ts">
  // One 100% bar per group (for example race within each grade) for a single year. Plain markup, so every share is also readable text.
  import { paletteFor } from '../lib/palette'
  export interface Group {
    group: string
    total: number
    segs: { key: string; value: number }[]
  }
  let { groups, keys, label, totalLabel = 'students' }: { groups: Group[]; keys: string[]; label: string; totalLabel?: string } = $props()

  const colors = $derived(paletteFor(keys, (v) => (v.startsWith('--') ? `var(${v})` : v)))
  const color = (i: number) => colors[i]
  const pct = (v: number, t: number) => Math.round((v / t) * 1000) / 10
</script>

<div class="gb" role="group" aria-label={label}>
  <ul class="legend" aria-hidden="true">
    {#each keys as k, i}<li><i style:background={color(i)}></i>{k}</li>{/each}
  </ul>
  <ul class="rows">
    {#each groups as g}
      <li>
        <span class="g">{g.group}</span>
        <span class="bar" aria-hidden="true">
          {#each keys as k, i}
            {@const v = g.segs.find((s) => s.key === k)?.value ?? 0}
            {#if v > 0}<i style:width="{(v / g.total) * 100}%" style:background={color(i)} title="{g.group}: {k}, {pct(v, g.total)}% ({v.toLocaleString()})"></i>{/if}
          {/each}
        </span>
        <span class="t">{g.total.toLocaleString()}</span>
        <span class="sr">{g.group}, {g.total.toLocaleString()} {totalLabel}: {keys.filter((k) => g.segs.find((s) => s.key === k && s.value > 0)).map((k) => `${k} ${pct(g.segs.find((s) => s.key === k)!.value, g.total)}%`).join(', ')}</span>
      </li>
    {/each}
  </ul>
</div>

<style>
  ul {
    list-style: none;
    margin: 0;
    padding: 0;
  }
  .legend {
    display: flex;
    flex-wrap: wrap;
    gap: 4px 12px;
    font-size: 11px;
    color: var(--text);
    margin-bottom: 10px;
  }
  .legend li {
    display: flex;
    align-items: center;
    gap: 5px;
  }
  .legend i {
    width: 10px;
    height: 10px;
    border-radius: 2px;
    display: inline-block;
  }
  .rows {
    display: grid;
    gap: 6px;
  }
  .rows li {
    display: grid;
    grid-template-columns: minmax(0, 7.5rem) minmax(0, 1fr) 3.4rem;
    align-items: center;
    gap: 10px;
    font-size: 12px;
    position: relative;
  }
  .g {
    overflow-wrap: anywhere;
  }
  .bar {
    display: flex;
    height: 14px;
    border-radius: 4px;
    overflow: hidden;
    background: var(--surface-2);
  }
  .bar i {
    display: block;
    height: 100%;
  }
  .t {
    font-family: var(--f-data);
    font-variant-numeric: tabular-nums;
    color: var(--muted);
    text-align: right;
  }
  .sr {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip: rect(0 0 0 0);
    white-space: nowrap;
  }
</style>
