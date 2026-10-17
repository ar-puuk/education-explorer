<script lang="ts">
  import { app } from '../lib/app.svelte'
  import { visibleColleges, visiblePrivate, visiblePublic } from '../lib/filters'
  import { download, toCsv } from '../lib/explore'
  import { fmtInt, levelLabel, localeLabel, schoolYearLabel } from '../lib/labels'
  import type { Selectable } from '../lib/icons'

  type Ds = 'public' | 'private' | 'college'
  interface Col {
    id: string
    label: string
    num?: boolean
    on: boolean
  }
  interface Rec {
    id: string
    lon: number
    lat: number
    v: Record<string, string | number | null>
  }

  let ds = $state<Ds>('public')
  let sortBy = $state('name')
  let desc = $state(false)
  let limit = $state(300)
  let colsOn = $state<Record<string, boolean>>({})

  const COLS: Record<Ds, Col[]> = {
    public: [
      { id: 'name', label: 'School', on: true }, { id: 'district', label: 'District', on: true }, { id: 'level', label: 'Level', on: true },
      { id: 'charter', label: 'Charter', on: true }, { id: 'status', label: 'Status', on: true }, { id: 'enroll', label: 'Enrollment', num: true, on: true },
      { id: 'grades', label: 'Grades', on: false }, { id: 'type', label: 'School type', on: false }, { id: 'locale', label: 'Locale', on: false },
      { id: 'county', label: 'County', on: false }, { id: 'id', label: 'NCES school ID', on: false },
    ],
    private: [
      { id: 'name', label: 'School', on: true }, { id: 'city', label: 'City', on: true }, { id: 'level', label: 'Level', on: true },
      { id: 'typology', label: 'Typology', on: true }, { id: 'enroll', label: 'Enrollment', num: true, on: true }, { id: 'teachers', label: 'Teachers (FTE)', num: true, on: true },
      { id: 'survey', label: 'Survey', on: false }, { id: 'id', label: 'PIN', on: false }, { id: 'address', label: 'Address', on: false },
    ],
    college: [
      { id: 'name', label: 'Institution', on: true }, { id: 'city', label: 'City', on: true }, { id: 'sector', label: 'Sector', on: true },
      { id: 'control', label: 'Control', on: false }, { id: 'level', label: 'Level', on: false }, { id: 'enroll', label: 'Fall enrollment', num: true, on: true },
      { id: 'active', label: 'Active', on: true }, { id: 'id', label: 'IPEDS unit ID', on: false },
    ],
  }
  const cols = $derived(COLS[ds].map((c) => ({ ...c, on: colsOn[`${ds}.${c.id}`] ?? c.on })))
  const shown = $derived(cols.filter((c) => c.on))

  const lab = (field: string, code: unknown, from?: { [c: string]: string }) => (code == null ? '' : (from?.[String(code)] ?? String(code)))

  const rows = $derived.by((): Rec[] => {
    if (ds === 'public') {
      return visiblePublic().map(({ s, i, status }) => ({
        id: s.id, lon: s.lon, lat: s.lat,
        v: { name: s.name, district: s.lea, level: levelLabel(s.level), charter: s.charter ?? '', status, enroll: s.enroll[i],
          grades: `${s.gradeLow ?? ''}-${s.gradeHigh ?? ''}`, type: s.type ?? '', locale: localeLabel(s.locale), county: s.county ?? '', id: s.id },
      }))
    }
    if (ds === 'private') {
      const L = app.private?.labels
      return visiblePrivate().map(({ s, i, survey }) => ({
        id: s.id, lon: s.lon, lat: s.lat,
        v: { name: s.name, city: s.city ?? '', level: lab('level', s.level, L?.level), typology: lab('typology', s.typology, L?.typology),
          enroll: s.enroll[i], teachers: s.teachers[i], survey: schoolYearLabel(survey), id: s.id, address: s.address ?? '' },
      }))
    }
    const L = app.college?.labels
    return visibleColleges().map(({ s, i, operating }) => ({
      id: s.id, lon: s.lon, lat: s.lat,
      v: { name: s.name, city: s.city ?? '', sector: lab('sector', s.sector, L?.sector), control: lab('control', s.control, L?.control),
        level: lab('iclevel', s.level, L?.iclevel), enroll: s.enroll[i], active: operating ? 'Yes' : 'No', id: s.id },
    }))
  })

  const sorted = $derived.by(() => {
    const k = sortBy
    const dir = desc ? -1 : 1
    return [...rows].sort((a, b) => {
      const x = a.v[k], y = b.v[k]
      if (x == null || x === '') return 1
      if (y == null || y === '') return -1
      return (typeof x === 'number' && typeof y === 'number' ? x - y : String(x).localeCompare(String(y))) * dir
    })
  })

  function sort(id: string) {
    if (sortBy === id) desc = !desc
    else {
      sortBy = id
      desc = false
    }
  }
  function open(r: Rec) {
    app.selected = { dataset: ds as Selectable, id: r.id }
    app.showTable = false
  }
  function exportCsv() {
    download(`${ds}-${app.year}.csv`, toCsv(shown.map((c) => c.label), sorted.map((r) => shown.map((c) => r.v[c.id] ?? null))))
  }
  $effect(() => {
    ds
    limit = 300
    sortBy = 'name'
    desc = false
  })
  const NAMES: Record<Ds, string> = { public: 'Public schools', private: 'Private schools', college: 'Colleges' }
</script>

{#if app.showTable}
  <div class="backdrop" role="presentation" onclick={() => (app.showTable = false)}></div>
  <div class="dialog" role="dialog" aria-modal="true" aria-label="Table of places on the map">
    <div class="head">
      <h2>Table view <span class="muted">{schoolYearLabel(app.year)} · current filters</span></h2>
      <button class="close" onclick={() => (app.showTable = false)} aria-label="Close table">×</button>
    </div>
    <div class="tabs" role="tablist">
      {#each ['public', 'private', 'college'] as d}
        <button role="tab" aria-selected={ds === d} class:on={ds === d} onclick={() => (ds = d as Ds)}>{NAMES[d as Ds]}</button>
      {/each}
      <span class="count">{fmtInt(rows.length)} rows</span>
      <button onclick={exportCsv}>Download CSV</button>
    </div>
    <details class="picker">
      <summary>Columns</summary>
      <div class="picks">
        {#each cols as c}
          <label><input type="checkbox" checked={c.on} onchange={(e) => (colsOn[`${ds}.${c.id}`] = (e.currentTarget as HTMLInputElement).checked)} /> {c.label}</label>
        {/each}
      </div>
    </details>
    <div class="scroll">
      <table>
        <thead>
          <tr>
            {#each shown as c}
              <th scope="col" class:num={c.num} aria-sort={sortBy === c.id ? (desc ? 'descending' : 'ascending') : 'none'}>
                <button class="sort" onclick={() => sort(c.id)}>{c.label}{sortBy === c.id ? (desc ? ' ▼' : ' ▲') : ''}</button>
              </th>
            {/each}
          </tr>
        </thead>
        <tbody>
          {#each sorted.slice(0, limit) as r}
            <tr tabindex="0" onclick={() => open(r)} onkeydown={(e) => e.key === 'Enter' && open(r)}>
              {#each shown as c}
                <td class:num={c.num}>{c.num ? fmtInt(r.v[c.id] as number | null) : (r.v[c.id] ?? '')}</td>
              {/each}
            </tr>
          {/each}
        </tbody>
      </table>
      {#if sorted.length > limit}
        <p class="muted"><button onclick={() => (limit += 400)}>Show more</button> Showing {limit} of {fmtInt(sorted.length)}. The CSV includes every row.</p>
      {/if}
    </div>
    <p class="muted">Rows are the places currently shown on the map for this year and filters. Data are as published; nothing here ranks or rates places.</p>
  </div>
{/if}

<style>
  .backdrop {
    position: fixed;
    inset: 0;
    background: rgb(0 0 0 / 40%);
    z-index: 40;
  }
  .dialog {
    position: fixed;
    z-index: 41;
    top: 4vh;
    left: 50%;
    transform: translateX(-50%);
    width: min(1040px, calc(100% - 24px));
    max-height: 92vh;
    display: flex;
    flex-direction: column;
    background: var(--surface);
    color: var(--text);
    border: 1px solid var(--border);
    border-radius: 12px;
    box-shadow: var(--shadow);
    padding: 14px 18px 14px;
  }
  .head {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  h2 {
    font-size: 17px;
    margin: 0;
  }
  .muted {
    color: var(--muted);
    font-size: 12.5px;
    font-weight: 400;
  }
  .close {
    border: 1px solid var(--border);
    background: var(--surface-2);
    border-radius: 50%;
    width: 30px;
    height: 30px;
    font-size: 18px;
    line-height: 1;
  }
  .tabs {
    display: flex;
    gap: 6px;
    align-items: center;
    margin: 8px 0;
    flex-wrap: wrap;
  }
  .tabs button,
  .muted button {
    background: var(--surface-2);
    border: 1px solid var(--border);
    border-radius: 999px;
    padding: 2px 12px;
  }
  .tabs button.on {
    background: var(--accent);
    color: var(--accent-text);
    border-color: var(--accent);
  }
  .count {
    margin-left: auto;
    color: var(--muted);
  }
  .picker summary {
    cursor: pointer;
    color: var(--accent);
  }
  .picks {
    display: flex;
    flex-wrap: wrap;
    gap: 4px 14px;
    padding: 6px 0;
  }
  .scroll {
    overflow: auto;
    border: 1px solid var(--border);
    border-radius: 6px;
    min-height: 120px;
  }
  table {
    border-collapse: collapse;
    width: 100%;
    font-size: 13px;
  }
  th,
  td {
    padding: 4px 10px;
    border-bottom: 1px solid var(--border);
    text-align: left;
    white-space: nowrap;
  }
  .num {
    text-align: right;
  }
  thead th {
    position: sticky;
    top: 0;
    background: var(--surface-2);
  }
  .sort {
    background: none;
    border: 0;
    font-weight: 600;
    padding: 0;
  }
  tbody tr {
    cursor: pointer;
  }
  tbody tr:hover,
  tbody tr:focus {
    background: var(--surface-2);
  }
</style>
