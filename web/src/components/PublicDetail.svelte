<script lang="ts">
  import { app, statusAt } from '../lib/app.svelte'
  import {
    loadDictionary,
    membershipHistory,
    schoolRows,
    schoolCharacteristics,
    schoolDirectoryHistory,
    schoolLocationHistory,
    type MembershipRow,
  } from '../lib/data'
  import type { Row } from '../lib/db'
  import { fmtInt, GRADE_ORDER, gradeLabel, localeLabel, schoolYearLabel } from '../lib/labels'
  import type { DictEntry, PublicSchool, TrendPoint } from '../lib/types'
  import CompareButton from './CompareButton.svelte'
  import TableExplorer from './TableExplorer.svelte'
  import TrendChart from './TrendChart.svelte'

  type Tab = 'total' | 'race' | 'sex' | 'grade'
  let tab = $state<Tab>('total')
  let loading = $state(false)
  let error = $state('')
  let dir = $state<Row[]>([])
  let loc = $state<Row[]>([])
  let chars = $state<Row[]>([])
  let mem = $state<MembershipRow[]>([])
  let dict = $state<Map<string, DictEntry>>(new Map())
  let showAll = $state(false)
  let lunch = $state<Row[]>([])
  let staffRows = $state<Row[]>([])

  const school = $derived<PublicSchool | undefined>(
    app.selected?.dataset === 'public' ? app.points?.schools.find((s) => s.id === app.selected!.id) : undefined,
  )

  $effect(() => {
    const s = school
    if (!s) return
    const years = s.years
    let cancelled = false
    loading = true
    error = ''
    Promise.all([
      schoolDirectoryHistory(years, s.id),
      schoolLocationHistory(app.points!.years, s.id),
      schoolCharacteristics(years, s.id),
      membershipHistory(years, s.id),
      loadDictionary(),
      schoolRows('lunch', s.id),
      schoolRows('staff', s.id),
    ])
      .then(([d, l, c, m, dc, lu, st]) => {
        if (cancelled) return
        dir = d
        loc = l
        chars = c
        mem = m
        dict = dc
        lunch = lu
        staffRows = st
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

  /** Row for the selected year, or the nearest earlier/later year this school has data. */
  function pick(rows: Row[]): Row | undefined {
    return rows.find((r) => r.year === app.year) ?? [...rows].reverse().find((r) => (r.year as number) < app.year) ?? rows[0]
  }

  const dirRow = $derived(pick(dir))
  const locRow = $derived(pick(loc))
  const charRow = $derived(pick(chars))
  const status = $derived(school ? statusAt(school, app.year, app.points?.statuses ?? []) : null)
  const inYear = $derived(school ? school.years.includes(app.year) : false)

  const label = (table: string, col: string) => dict.get(`ccd.${table}.${col}`)?.label ?? col
  const desc = (table: string, col: string) => {
    const d = dict.get(`ccd.${table}.${col}`)
    return d ? [d.description, d.caveat].filter(Boolean).join('\n\n') : ''
  }

  const HIDE = new Set([
    'year', 'school_year', 'data_version', 'source_file', 'fipst', 'state_abbrev', 'state_name', 'ncessch',
    'leaid', 'schid', 'st_schid', 'st_leaid', 'state_agency_no', 'sea_name', 'union_code', 'mail_street3',
    'street3', 'mail_zip4', 'zip4', 'out_of_state_flag', 'recon_status', 'updated_status_code', 'status_code',
    'school_type_code', 'virtual_code', 'coord_approximate',
  ])
  const MAIN = ['status', 'school_type', 'level', 'charter', 'grade_low', 'grade_high']
  const MAIN_LABEL: Record<string, string> = { grade_low: 'Lowest grade', grade_high: 'Highest grade' }

  function fmt(col: string, v: unknown): string {
    if (v == null || v === '') return ''
    if (col === 'grade_low' || col === 'grade_high') return gradeLabel(String(v))
    if (v instanceof Date) return v.toISOString().slice(0, 10)
    if (typeof v === 'number' && col.startsWith('effective')) return new Date(v).toISOString().slice(0, 10)
    return String(v)
  }

  const otherFields = $derived.by(() => {
    if (!dirRow) return []
    return Object.entries(dirRow)
      .filter(([k, v]) => !HIDE.has(k) && !MAIN.includes(k) && v != null && v !== '' && !k.endsWith('_flag'))
      .map(([k, v]) => ({ k, label: label('school_directory', k), v: fmt(k, v), d: desc('school_directory', k) }))
  })

  // ------------------------------------------------------------------ enrollment series
  const years = $derived(school?.years ?? [])
  const catA = (r: MembershipRow) => r.total_indicator.startsWith('Category Set A')

  function sumBy(rows: MembershipRow[], keyOf: (r: MembershipRow) => string, order?: string[]): TrendPoint[] {
    const m = new Map<string, number | null>()
    for (const r of rows) {
      const k = `${r.year}|${keyOf(r)}`
      const cur = m.get(k)
      if (r.student_count == null) {
        if (!m.has(k)) m.set(k, null)
      } else m.set(k, (cur ?? 0) + r.student_count)
    }
    const out: TrendPoint[] = []
    for (const [k, value] of m) {
      const [y, key] = k.split('|')
      out.push({ year: Number(y), key, value })
    }
    const idx = (key: string) => (order ? (order.indexOf(key) === -1 ? 99 : order.indexOf(key)) : 0)
    return out.sort((a, b) => a.year - b.year || idx(a.key) - idx(b.key) || a.key.localeCompare(b.key))
  }

  const series = $derived.by((): TrendPoint[] => {
    if (!mem.length) return []
    if (tab === 'total') {
      return mem
        .filter((r) => r.total_indicator === 'Education Unit Total')
        .map((r) => ({ year: r.year, key: 'Total enrollment', value: r.student_count }))
    }
    const detail = mem.filter(catA)
    if (tab === 'race') return sumBy(detail, (r) => r.race)
    if (tab === 'sex') return sumBy(detail, (r) => r.sex)
    return sumBy(detail, (r) => r.grade, GRADE_ORDER)
  })

  const num = (v: unknown) => (typeof v === 'number' ? v : null)
  const lunchSeries = $derived.by((): TrendPoint[] => {
    const out: TrendPoint[] = []
    for (const r of lunch) {
      if (r.data_group === 'Free and Reduced-price Lunch Table' && r.total_indicator === 'Category Set A') {
        if (r.lunch_program === 'Free lunch qualified') out.push({ year: r.year as number, key: 'Free lunch qualified', value: num(r.student_count) })
        if (r.lunch_program === 'Reduced-price lunch qualified') out.push({ year: r.year as number, key: 'Reduced-price lunch qualified', value: num(r.student_count) })
      }
      if (r.data_group === 'Direct Certification' && r.total_indicator === 'Education Unit Total') out.push({ year: r.year as number, key: 'Directly certified', value: num(r.student_count) })
    }
    return out.sort((a, b) => a.year - b.year)
  })
  const staffSeries = $derived(
    staffRows.filter((r) => r.total_indicator === 'Education Unit Total').map((r): TrendPoint => ({ year: r.year as number, key: 'Teachers (FTE)', value: num(r.teachers) })),
  )
  const lunchCaveat = $derived(dict.get('ccd.lunch.student_count')?.caveat ?? '')
  const flagged = $derived(mem.some((r) => r.value_flag && ['missing', 'suppressed', 'not_reported', 'not_applicable', 'not_meeting_standards'].includes(r.value_flag)))
  const caveat = $derived(dict.get('ccd.membership.student_count')?.caveat ?? '')
  const tabs: { id: Tab; label: string }[] = [
    { id: 'total', label: 'Total' },
    { id: 'race', label: 'Race/ethnicity' },
    { id: 'sex', label: 'Sex' },
    { id: 'grade', label: 'Grade' },
  ]
  const sel = $derived(series.find((d) => d.year === app.year && d.key === 'Total enrollment')?.value ?? null)
</script>

{#if school}
  <aside class="panel" aria-label="School details">
    <div class="head">
      <div>
        <h2>{school.name}</h2>
        <p class="sub"><button class="link" onclick={() => (app.selected = { dataset: 'district', id: school.leaid })}>{school.lea}</button></p>
      </div>
      <button class="close" onclick={() => (app.selected = null)} aria-label="Close details">×</button>
    </div>

    <p class="cmprow"><CompareButton dataset="public" id={school.id} /></p>
    {#if error}
      <p class="err" role="alert">Could not load details: {error}</p>
    {/if}
    {#if loading && !dirRow}<p class="muted">Loading…</p>{/if}

    <p class="yearline">
      <strong>{schoolYearLabel(app.year)}</strong>
      {#if !inYear}
        <span class="warn">This school is not in the directory for this year; showing the closest year.</span>
      {:else if status}
        <span class="chip" class:closed={status === 'Closed' || status.startsWith('Future')}>{status}</span>
      {/if}
      {#if sel != null}<span class="enr">{fmtInt(sel)} students</span>{/if}
    </p>

    <h3>Enrollment over time</h3>
    <div class="tabs" role="tablist" aria-label="Enrollment breakdown">
      {#each tabs as t}
        <button role="tab" aria-selected={tab === t.id} class:on={tab === t.id} onclick={() => (tab = t.id)}>{t.label}</button>
      {/each}
    </div>
    {#if mem.length}
      <TrendChart
        data={series}
        currentYear={app.year}
        mode={tab === 'grade' ? 'heat' : 'line'}
        alt={`Enrollment by year for ${school.name}, ${tabs.find((t) => t.id === tab)?.label.toLowerCase()}`}
      />
      {#if flagged}
        <p class="note">Some values are missing, suppressed or not reported by the state and are left blank in the chart (never plotted as zero).</p>
      {/if}
      {#if tab !== 'total'}
        <p class="note">Detail rows are summed from the race × sex × grade categories reported to NCES.</p>
      {/if}
    {:else if !loading}
      <p class="muted">No membership data for this school.</p>
    {/if}
    {#if caveat}<details class="cav"><summary>About these counts</summary><p>{caveat}</p></details>{/if}


    <h3>School details</h3>
    {#if dirRow}
      <dl class="facts">
        {#each MAIN as k}
          {#if dirRow[k] != null && dirRow[k] !== '' && k !== 'status'}
            <dt title={desc('school_directory', k)}>{MAIN_LABEL[k] ?? label('school_directory', k)}</dt>
            <dd>{fmt(k, dirRow[k])}</dd>
          {/if}
        {/each}
        {#if locRow?.locale}<dt title={desc('school_location', 'locale')}>Locale</dt><dd>{localeLabel(String(locRow.locale))}</dd>{/if}
        {#if locRow?.county_name}<dt>County</dt><dd>{locRow.county_name}</dd>{/if}
        {#if dirRow.street1}
          <dt>Address</dt>
          <dd>{dirRow.street1}, {dirRow.city} {dirRow.state} {dirRow.zip}</dd>
        {/if}
        {#if dirRow.phone}<dt>Phone</dt><dd>{dirRow.phone}</dd>{/if}
        {#if dirRow.website}
          <dt>Website</dt>
          <dd><a href={String(dirRow.website).startsWith('http') ? String(dirRow.website) : `https://${dirRow.website}`} target="_blank" rel="noopener noreferrer">{dirRow.website}</a></dd>
        {/if}
        {#if charRow}
          {#each ['title_i_status', 'magnet', 'shared_time', 'nslp_status'] as k}
            {#if charRow[k] != null && charRow[k] !== ''}
              <dt title={desc('school_characteristics', k)}>{label('school_characteristics', k)}</dt>
              <dd>{charRow[k]}</dd>
            {/if}
          {/each}
        {/if}
        {#if locRow?.lat != null}
          <dt title={desc('school_location', 'coord_source')}>Location source</dt>
          <dd>{locRow.coord_source === 'edge' ? 'NCES EDGE' : locRow.coord_source === 'edge_prior_year' ? 'NCES EDGE (earlier year)' : locRow.coord_source}</dd>
        {/if}
      </dl>
    {/if}

    {#if lunchSeries.some((d) => d.value != null)}
      <h3>Free and reduced-price lunch eligibility</h3>
      <TrendChart data={lunchSeries} yLabel="Students" currentYear={app.year} alt={`Lunch program eligibility counts for ${school.name}`} height={190} />
      {#if lunchCaveat}<p class="note">{lunchCaveat}</p>{/if}
    {/if}
    {#if staffSeries.some((d) => d.value != null)}
      <h3>Teachers</h3>
      <TrendChart data={staffSeries} yLabel="FTE" currentYear={app.year} alt={`Teachers (FTE) at ${school.name}`} height={170} />
    {/if}

    {#if otherFields.length}
      <details class="more" bind:open={showAll}>
        <summary>All directory fields for {schoolYearLabel(Number(dirRow?.year ?? app.year))} ({otherFields.length})</summary>
        <dl class="facts">
          {#each otherFields as f}
            <dt title={f.d}>{f.label}</dt>
            <dd>{f.v}</dd>
          {/each}
        </dl>
      </details>
    {/if}

    <TableExplorer dataset="ccd" unitid={school.id} name={school.name} start="school_directory"
      only={['school_directory', 'school_characteristics', 'school_location', 'membership', 'lunch', 'staff', 'legacy_school']} />
    <p class="ids">NCES school ID {school.id} · district ID {school.leaid}</p>
  </aside>
{/if}

<style>
  .panel {
    position: absolute;
    z-index: 6;
    top: 12px;
    right: 12px;
    bottom: 100px;
    width: 400px;
    overflow: auto;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    box-shadow: var(--shadow);
    padding: 12px 16px 16px;
  }
  .head {
    display: flex;
    justify-content: space-between;
    gap: 8px;
  }
  h2 {
    font-size: 17px;
    margin: 0;
  }
  h3 {
    font-size: 13px;
    margin: 14px 0 6px;
  }
  .sub {
    margin: 2px 0 0;
    color: var(--muted);
  }
  .link {
    background: none;
    border: 0;
    padding: 0;
    color: var(--accent);
    text-decoration: underline;
    font: inherit;
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
  .yearline {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
    margin: 10px 0;
  }
  .chip {
    border: 1px solid var(--border);
    border-radius: 999px;
    padding: 0 8px;
    font-size: 12px;
  }
  .chip.closed {
    border-style: dashed;
    color: var(--muted);
  }
  .enr {
    margin-left: auto;
    color: var(--muted);
  }
  .warn {
    background: var(--warn-bg);
    color: var(--warn-text);
    padding: 2px 8px;
    border-radius: 6px;
    font-size: 12px;
  }
  .facts {
    display: grid;
    grid-template-columns: max-content 1fr;
    gap: 3px 12px;
    margin: 0;
  }
  dt {
    color: var(--muted);
  }
  dd {
    margin: 0;
    overflow-wrap: anywhere;
  }
  a {
    color: var(--accent);
  }
  .tabs {
    display: flex;
    gap: 4px;
    margin-bottom: 6px;
    flex-wrap: wrap;
  }
  .tabs button {
    background: var(--surface-2);
    border: 1px solid var(--border);
    border-radius: 999px;
    padding: 2px 10px;
  }
  .tabs button.on {
    background: var(--accent);
    color: var(--accent-text);
    border-color: var(--accent);
  }
  .note,
  .muted,
  .cav p,
  .ids {
    color: var(--muted);
    font-size: 12px;
  }
  .err {
    color: #c62828;
  }
  details {
    margin-top: 10px;
  }
  summary {
    cursor: pointer;
    color: var(--accent);
  }
  @media (max-width: 720px) {
    .panel {
      top: auto;
      left: 0;
      right: 0;
      bottom: 0;
      width: auto;
      height: 62%;
      border-radius: 14px 14px 0 0;
      z-index: 20;
    }
  }
</style>
