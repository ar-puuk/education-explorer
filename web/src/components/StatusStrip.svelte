<script lang="ts">
  // A yes/no/category history: one row per attribute, one cell per year. The table is real markup so screen readers get every value.
  export interface StripRow {
    label: string
    /** year -> value text (missing years are blank) */
    values: Record<number, string | null | undefined>
    /** values that mean "not applicable / none" are drawn in a quiet colour */
    quiet?: string[]
  }
  let { rows, years, current, label }: { rows: StripRow[]; years: number[]; current: number; label: string } = $props()

  const QUIET = /^(no|not|none|n\/a|not applicable|no virtual|not a|neither)/i
  const palette = [1, 2, 3, 4, 5, 6]
  function tone(row: StripRow, v: string | null | undefined): string {
    if (!v) return 'gap'
    if (row.quiet?.includes(v) || QUIET.test(v)) return 'quiet'
    const seen = [...new Set(Object.values(row.values).filter((x): x is string => !!x && !(row.quiet?.includes(x) || QUIET.test(x))))]
    return `c${palette[seen.indexOf(v) % palette.length]}`
  }
  function now(row: StripRow): string {
    const ys = years.filter((y) => row.values[y] && y <= current)
    return (row.values[current] ?? (ys.length ? row.values[ys[ys.length - 1]] : '')) || '—'
  }
</script>

<div class="wrap" role="region" aria-label="{label} (scrollable)" tabindex="0">
  <table aria-label={label}>
    <thead>
      <tr>
        <th scope="col" class="r">Attribute</th>
        {#each years as y}<th scope="col" class="y" class:cur={y === current}><span>{String(y).slice(2)}</span></th>{/each}
        <th scope="col" class="now">Selected year</th>
      </tr>
    </thead>
    <tbody>
      {#each rows as row}
        <tr>
          <th scope="row" class="r">{row.label}</th>
          {#each years as y}
            <td class={tone(row, row.values[y])} class:cur={y === current} title="{row.label}, {y}: {row.values[y] ?? 'no record'}">
              <span class="sr">{row.values[y] ?? 'no record'}</span>
            </td>
          {/each}
          <td class="nowv">{now(row)}</td>
        </tr>
      {/each}
    </tbody>
  </table>
</div>

<style>
  .wrap {
    overflow-x: auto;
  }
  table {
    border-collapse: separate;
    border-spacing: 2px;
    width: 100%;
    font-size: 11px;
  }
  th,
  td {
    padding: 0;
    font-weight: 400;
    text-align: left;
  }
  .r {
    white-space: nowrap;
    padding-right: 8px;
    color: var(--text);
  }
  .y {
    text-align: center;
    color: var(--muted);
    font-family: var(--f-data);
    font-size: 9.5px;
  }
  .y span {
    display: inline-block;
    min-width: 12px;
  }
  td:not(.nowv) {
    height: 18px;
    min-width: 12px;
    border-radius: 3px;
  }
  .gap {
    background: transparent;
    outline: 1px dashed var(--border);
    outline-offset: -1px;
  }
  .quiet {
    background: var(--border);
  }
  .c1 { background: var(--chart-1); }
  .c2 { background: var(--chart-2); }
  .c3 { background: var(--chart-3); }
  .c4 { background: var(--chart-4); }
  .c5 { background: var(--chart-5); }
  .c6 { background: var(--chart-6); }
  .cur {
    box-shadow: 0 0 0 1.5px var(--text);
  }
  .y.cur {
    color: var(--text);
    box-shadow: none;
    font-weight: 600;
  }
  .now,
  .nowv {
    min-width: 6.5rem;
    font-size: 11px;
    padding-left: 8px;
    white-space: normal;
    color: var(--muted);
  }
  .nowv {
    min-width: 6.5rem;
    font-size: 11px;
    color: var(--text);
  }
  .sr {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip: rect(0 0 0 0);
    white-space: nowrap;
  }
  td {
    position: relative;
  }
</style>
