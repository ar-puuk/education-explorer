<script lang="ts">
  import { app } from '../lib/app.svelte'
  import { districtRows, ipedsRows, loadDictionary, loadValueLabels, pssRows, schoolRows } from '../lib/data'
  import type { Row } from '../lib/db'
  import {
    cellText, colDesc, colLabel, dataColumns, download, isMultiRow, pivot, toCsv, type ExploreContext,
  } from '../lib/explore'
  import type { DictEntry } from '../lib/types'

  let {
    dataset = 'ipeds',
    unitid,
    name,
    start = 'hd',
    only,
    idKind = 'school',
  }: { dataset?: 'ipeds' | 'pss' | 'ccd'; unitid: string; name: string; start?: string; only?: string[]; idKind?: 'school' | 'district' } = $props()

  const tables = $derived(
    Object.entries(app.years?.[dataset] ?? {})
      .filter(([id]) => !only || only.includes(id))
      .map(([id, t]) => ({ id, title: (t as { title?: string }).title ?? id, survey: (t as { survey?: string }).survey ?? 'Other', years: t.years }))
      .sort((a, b) => a.survey.localeCompare(b.survey) || a.title.localeCompare(b.title)),
  )
  const surveys = $derived([...new Set(tables.map((t) => t.survey))])

  // svelte-ignore state_referenced_locally
  let table = $state(start)
  let rows = $state<Row[]>([])
  let loading = $state(false)
  let error = $state('')
  let filter = $state('')
  let year = $state(0)
  let dict = $state<Map<string, DictEntry>>(new Map())
  let labels = $state<Map<string, string>>(new Map())

  const ctx = $derived<ExploreContext>({ dataset, table, dict, labels })

  const rowsFor = (t: string, id: string) =>
    dataset === 'pss' ? pssRows(t, id) : dataset === 'ccd' ? (idKind === 'district' ? districtRows(t, id) : schoolRows(t, id)) : ipedsRows(t, id)

  $effect(() => {
    const t = table
    const id = unitid
    let cancelled = false
    loading = true
    error = ''
    Promise.all([rowsFor(t, id), loadDictionary(), loadValueLabels()])
      .then(([r, d, l]) => {
        if (cancelled) return
        rows = r
        dict = d
        labels = l
        const ys = [...new Set(r.map((x) => x.year as number))]
        year = ys.includes(app.year) ? app.year : (ys[ys.length - 1] ?? 0)
      })
      .catch((e) => {
        if (!cancelled) error = String(e?.message ?? e)
      })
      .finally(() => {
        if (!cancelled) loading = false
      })
    return () => {
      cancelled = true
    }
  })

  const multi = $derived(isMultiRow(rows))
  const piv = $derived(multi ? null : pivot(ctx, rows, filter))
  const yearsAvail = $derived([...new Set(rows.map((r) => r.year as number))].sort((a, b) => a - b))
  const yearRows = $derived(rows.filter((r) => r.year === year))
  const cols = $derived(dataColumns(yearRows))
  const tableNote = $derived(dict.get(`${dataset}.${table}.${dataset === 'pss' ? 'row_id' : dataset === 'ccd' ? (idKind === 'district' ? 'leaid' : 'ncessch') : 'unitid'}`)?.caveat ?? '')

  function exportCsv() {
    if (piv) {
      download(`${name}-${table}.csv`.replaceAll(' ', '_'), toCsv(['variable', 'label', ...piv.years.map(String)],
        piv.rows.map((r) => [r.column, r.label, ...r.cells.map((c) => (c.raw == null ? '' : String(c.raw)))])))
    } else {
      download(`${name}-${table}-${year}.csv`.replaceAll(' ', '_'), toCsv(cols, yearRows.map((r) => cols.map((c) => (r[c] == null ? null : String(r[c]))))))
    }
  }
</script>

<section class="explorer">
  <h3>All data tables</h3>
  <p class="muted">{dataset === 'ccd' ? 'Every CCD table' : `Every ${dataset === 'pss' ? 'PSS' : 'IPEDS'} table`} published for this {dataset === 'ipeds' ? 'institution' : idKind === 'district' ? 'district' : 'school'}, with NCES variable names and labels.</p>
  <label class="pick">
    <span class="sr-only">Table</span>
    <select bind:value={table}>
      {#each surveys as s}
        <optgroup label={s}>
          {#each tables.filter((t) => t.survey === s) as t}
            <option value={t.id}>{t.title.replace(/\s*\((revised|updated)[^)]*\)\s*$/i, '').slice(0, 90)}</option>
          {/each}
        </optgroup>
      {/each}
    </select>
  </label>
  {#if tableNote}<p class="note">{tableNote}</p>{/if}
  {#if error}<p class="err" role="alert">{error}</p>{/if}
  {#if loading}<p class="muted">Loading…</p>{/if}
  {#if !loading && !rows.length && !error}<p class="muted">This institution has no rows in this table.</p>{/if}

  {#if rows.length}
    <div class="tools">
      {#if multi}
        <label>Year
          <select bind:value={year}>{#each yearsAvail as y}<option value={y}>{y}</option>{/each}</select>
        </label>
      {:else}
        <input type="search" placeholder="Filter variables…" bind:value={filter} aria-label="Filter variables" />
      {/if}
      <button onclick={exportCsv}>Download CSV</button>
    </div>
    <div class="scroll" tabindex="0" role="region" aria-label="Table rows">
      {#if piv}
        <table>
          <thead>
            <tr><th scope="col">Variable</th>{#each piv.years as y}<th scope="col">{y}</th>{/each}</tr>
          </thead>
          <tbody>
            {#each piv.rows as r}
              <tr>
                <th scope="row" title={`${r.column}${colDesc(ctx, r.column) ? '\n\n' + colDesc(ctx, r.column) : ''}`}>{r.label}</th>
                {#each r.cells as c}
                  <td class:flag={c.flag && c.flag !== 'R'} title={c.flag ? `status ${c.flag}` : ''}>{c.text}</td>
                {/each}
              </tr>
            {/each}
          </tbody>
        </table>
      {:else}
        <table>
          <thead><tr>{#each cols as c}<th scope="col" title={`${c}\n${colDesc(ctx, c)}`}>{colLabel(ctx, c)}</th>{/each}</tr></thead>
          <tbody>
            {#each yearRows.slice(0, 500) as r}
              <tr>{#each cols as c}<td title={r[`${c}_flag`] ? `status ${r[`${c}_flag`]}` : ''}>{cellText(ctx, c, r[c])}</td>{/each}</tr>
            {/each}
          </tbody>
        </table>
        {#if yearRows.length > 500}<p class="muted">Showing the first 500 of {yearRows.length} rows. Download the CSV for all rows.</p>{/if}
      {/if}
    </div>
  {/if}
</section>

<style>
  .explorer {
    margin-top: 14px;
  }
  h3 {
    font-size: 13px;
    margin: 0 0 4px;
  }
  .muted,
  .note {
    color: var(--muted);
    font-size: 12px;
    margin: 4px 0;
  }
  .pick select {
    width: 100%;
  }
  select,
  input,
  button {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 4px 8px;
  }
  .tools {
    display: flex;
    gap: 8px;
    align-items: center;
    margin: 8px 0;
    flex-wrap: wrap;
  }
  .tools input {
    flex: 1;
    min-width: 120px;
  }
  .scroll {
    overflow: auto;
    max-height: 340px;
    border: 1px solid var(--border);
    border-radius: 6px;
  }
  table {
    border-collapse: collapse;
    font-size: 12px;
    width: max-content;
    min-width: 100%;
  }
  th,
  td {
    padding: 3px 8px;
    border-bottom: 1px solid var(--border);
    text-align: right;
    white-space: nowrap;
  }
  thead th {
    position: sticky;
    top: 0;
    background: var(--surface-2);
    z-index: 1;
  }
  tbody th {
    position: sticky;
    left: 0;
    background: var(--surface);
    text-align: left;
    white-space: normal;
    min-width: 180px;
    max-width: 240px;
    font-weight: 500;
  }
  td.flag {
    font-style: italic;
    color: var(--muted);
  }
  .err {
    color: #c62828;
  }
</style>
