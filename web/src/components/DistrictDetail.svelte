<script lang="ts">
  import { app, isOperating, statusAt } from '../lib/app.svelte'
  import { districtRows, loadDictionary } from '../lib/data'
  import type { Row } from '../lib/db'
  import { download, toCsv } from '../lib/explore'
  import { fmtInt, levelLabel, schoolYearLabel } from '../lib/labels'
  import type { DictEntry, PublicSchool, TrendPoint } from '../lib/types'
  import CompareButton from './CompareButton.svelte'
  import TrendChart from './TrendChart.svelte'

  let { onSelectSchool }: { onSelectSchool: (id: string, lon: number, lat: number) => void } = $props()

  type Tab = 'enroll' | 'staff' | 'finance' | 'students'
  let tab = $state<Tab>('enroll')
  let loading = $state(false)
  let error = $state('')
  let dir = $state<Row[]>([])
  let mem = $state<Row[]>([])
  let staff = $state<Row[]>([])
  let fin = $state<Row[]>([])
  let idea = $state<Row[]>([])
  let el = $state<Row[]>([])
  let grads = $state<Row[]>([])
  let drops = $state<Row[]>([])
  let dict = $state<Map<string, DictEntry>>(new Map())

  const leaid = $derived(app.selected?.dataset === 'district' ? app.selected.id : '')
  const feature = $derived(app.districts?.features.find((f) => f.properties?.leaid === leaid))
  const name = $derived(String(feature?.properties?.name ?? dir.at(-1)?.lea_name ?? leaid))

  $effect(() => {
    const id = leaid
    if (!id) return
    let cancelled = false
    loading = true
    error = ''
    Promise.all([
      districtRows('district_directory', id), districtRows('district_membership', id), districtRows('district_staff', id),
      districtRows('district_finance', id), districtRows('district_idea', id), districtRows('district_el', id),
      districtRows('district_graduates', id), districtRows('district_dropout', id), loadDictionary(),
    ])
      .then((r) => {
        if (cancelled) return
        ;[dir, mem, staff, fin, idea, el, grads, drops] = r.slice(0, 8) as Row[][]
        dict = r[8] as Map<string, DictEntry>
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

  const num = (v: unknown) => (typeof v === 'number' ? v : null)
  const pick = (rows: Row[]) => rows.find((r) => r.year === app.year) ?? [...rows].reverse().find((r) => (r.year as number) < app.year) ?? rows[0]
  const dirRow = $derived(pick(dir))
  const inDir = $derived(dir.some((r) => r.year === app.year))

  // ---------------------------------------------------------------- schools (rollup)
  const schools = $derived.by(() => {
    const out: { s: PublicSchool; enroll: number | null; status: string }[] = []
    for (const s of app.points?.schools ?? []) {
      if (s.leaid !== leaid) continue
      const i = s.years.indexOf(app.year)
      if (i < 0) continue
      const status = statusAt(s, app.year, app.points!.statuses) ?? ''
      if (!isOperating(status)) continue
      out.push({ s, enroll: s.enroll[i], status })
    }
    return out.sort((a, b) => a.s.name.localeCompare(b.s.name))
  })
  const byLevel = $derived.by(() => {
    const m = new Map<string, { n: number; enroll: number }>()
    for (const { s, enroll } of schools) {
      const k = levelLabel(s.level)
      const e = m.get(k) ?? { n: 0, enroll: 0 }
      e.n++
      e.enroll += enroll ?? 0
      m.set(k, e)
    }
    return [...m].sort((a, b) => b[1].enroll - a[1].enroll)
  })
  const schoolSum = $derived(schools.reduce((t, x) => t + (x.enroll ?? 0), 0))
  const reportedNow = $derived(mem.find((r) => r.year === app.year && r.total_indicator === 'Education Unit Total')?.student_count as number | undefined)

  // ---------------------------------------------------------------- series
  const catA = (r: Row) => String(r.total_indicator).startsWith('Category Set A')
  function sumBy(rows: Row[], keyOf: (r: Row) => string): TrendPoint[] {
    const m = new Map<string, number | null>()
    for (const r of rows) {
      const k = `${r.year}|${keyOf(r)}`
      const v = num(r.student_count)
      if (v == null) {
        if (!m.has(k)) m.set(k, null)
      } else m.set(k, (m.get(k) ?? 0) + v)
    }
    return [...m].map(([k, value]) => ({ year: Number(k.split('|')[0]), key: k.split('|')[1], value }))
  }

  const enrollTotal = $derived(
    mem.filter((r) => r.total_indicator === 'Education Unit Total').map((r): TrendPoint => ({ year: r.year as number, key: 'Total enrollment', value: num(r.student_count) })),
  )
  const enrollRace = $derived(sumBy(mem.filter(catA), (r) => String(r.race)).sort((a, b) => a.year - b.year))
  let raceView = $state(false)

  const STAFF = ['Teachers', 'Paraprofessionals/Instructional Aides', 'School Counselors', 'Guidance Counselors', 'School Psychologists', 'LEA Administrators', 'School administrators']
  const staffSeries = $derived(
    staff.filter((r) => STAFF.includes(String(r.staff_category)) && num(r.staff_count) != null)
      .map((r): TrendPoint => ({ year: r.year as number, key: String(r.staff_category), value: num(r.staff_count) }))
      .sort((a, b) => a.year - b.year),
  )

  const FIN: [string, string][] = [['totalrev', 'Total revenue'], ['totalexp', 'Total expenditures'], ['tfedrev', 'Federal revenue'], ['tstrev', 'State revenue'], ['tlocrev', 'Local revenue']]
  const finSeries = $derived(
    fin.flatMap((r) => FIN.map(([c, label]): TrendPoint => ({ year: r.year as number, key: label, value: num(r[c]) }))),
  )

  const studentSeries = $derived.by((): TrendPoint[] => {
    const out: TrendPoint[] = []
    for (const r of idea) out.push({ year: r.year as number, key: 'Students with disabilities (IDEA)', value: num(r.idea_count) })
    for (const r of el) out.push({ year: r.year as number, key: 'English learners', value: num(r.lep_count) })
    for (const r of grads) {
      if (r.total_indicator === 'Subtotal 1 - By Credential' && r.credential === 'Regular secondary school diploma')
        out.push({ year: r.year as number, key: 'Regular diploma recipients', value: num(r.student_count) })
    }
    for (const r of drops) {
      if (r.total_indicator === 'Education Unit Total') out.push({ year: r.year as number, key: 'Dropouts (grades 9-12)', value: num(r.student_count) })
    }
    return out.sort((a, b) => a.year - b.year)
  })

  const current = $derived.by((): TrendPoint[] =>
    tab === 'enroll' ? (raceView ? enrollRace : enrollTotal) : tab === 'staff' ? staffSeries : tab === 'finance' ? finSeries : studentSeries,
  )
  const hasData = $derived(current.some((d) => d.value != null))
  const tabs: { id: Tab; label: string }[] = [
    { id: 'enroll', label: 'Enrollment' }, { id: 'staff', label: 'Staff' }, { id: 'finance', label: 'Finance' }, { id: 'students', label: 'Students' },
  ]
  const yLabel = $derived(tab === 'finance' ? 'Dollars' : tab === 'staff' ? 'FTE' : 'Count')
  const caveat = $derived(
    tab === 'enroll' ? dict.get('ccd.district_membership.student_count')?.caveat
      : tab === 'staff' ? dict.get('ccd.district_staff.staff_count')?.caveat
        : tab === 'finance' ? dict.get('ccd.district_finance.leaid')?.caveat ?? dict.get('ccd.district_finance.totalrev')?.caveat
          : dict.get('ccd.district_graduates.student_count')?.caveat,
  )
  const cav2 = $derived(tab === 'students' ? [dict.get('ccd.district_graduates.student_count')?.caveat, dict.get('ccd.district_dropout.student_count')?.caveat].filter(Boolean).join(' ') : caveat)

  function exportCsv() {
    download(`${name}-${tab}.csv`.replaceAll(' ', '_'), toCsv(['year', 'series', 'value'], current.map((d) => [d.year, d.key, d.value])))
  }
</script>

{#if leaid}
  <aside class="panel" aria-label="District details">
    <div class="head">
      <div>
        <h2>{name}</h2>
        <p class="sub">School district · NCES district ID {leaid}</p>
      </div>
      <button class="close" onclick={() => (app.selected = null)} aria-label="Close details">×</button>
    </div>
    <p class="cmprow"><CompareButton dataset="district" id={leaid} /></p>
    {#if error}<p class="err" role="alert">Could not load details: {error}</p>{/if}
    {#if loading && !dir.length}<p class="muted">Loading…</p>{/if}

    <p class="yearline">
      <strong>{schoolYearLabel(app.year)}</strong>
      {#if dir.length && !inDir}<span class="warn">Not in the district directory for this year (charter or non-geographic agencies have no boundary); showing the closest year.</span>{/if}
      {#if dirRow?.status}<span class="chip">{dirRow.status}</span>{/if}
      {#if reportedNow != null}<span class="enr">{fmtInt(reportedNow)} students</span>{/if}
    </p>

    <h3>Trends</h3>
    <div class="tabs" role="tablist" aria-label="District data">
      {#each tabs as t}
        <button role="tab" aria-selected={tab === t.id} class:on={tab === t.id} onclick={() => (tab = t.id)}>{t.label}</button>
      {/each}
      {#if tab === 'enroll'}
        <label class="toggle"><input type="checkbox" bind:checked={raceView} /> by race/ethnicity</label>
      {/if}
    </div>
    {#if hasData}
      <TrendChart data={current} yLabel={yLabel} currentYear={app.year} alt={`${tabs.find((t) => t.id === tab)?.label} for ${name}`} />
      <p class="note"><button class="link" onclick={exportCsv}>Download these series as CSV</button></p>
    {:else if !loading}
      <p class="muted">No data for this view (not every table covers every year or district).</p>
    {/if}
    {#if cav2}<details class="cav"><summary>About these data</summary><p>{cav2}</p></details>{/if}

    <h3>Schools in this district, {schoolYearLabel(app.year)}</h3>
    {#if schools.length}
      <p class="muted">
        {schools.length} operating schools; school enrollment adds up to {fmtInt(schoolSum)}{#if reportedNow != null}
          (district-reported total {fmtInt(reportedNow)}){/if}.
      </p>
      <table class="mini">
        <thead><tr><th scope="col">Level</th><th scope="col">Schools</th><th scope="col">Students</th></tr></thead>
        <tbody>{#each byLevel as [lv, v]}<tr><td>{lv}</td><td>{v.n}</td><td>{fmtInt(v.enroll)}</td></tr>{/each}</tbody>
      </table>
      <ul class="schools">
        {#each schools as { s, enroll }}
          <li><button onclick={() => onSelectSchool(s.id, s.lon, s.lat)}>{s.name}<span>{levelLabel(s.level)} · {fmtInt(enroll)}</span></button></li>
        {/each}
      </ul>
    {:else if !loading}
      <p class="muted">No operating schools in the school directory for this district and year.</p>
    {/if}

    {#if dirRow}
      <h3>District details</h3>
      <dl class="facts">
        {#if dirRow.lea_type}<dt>Type</dt><dd>{dirRow.lea_type}</dd>{/if}
        {#if dirRow.grade_low}<dt>Grades</dt><dd>{dirRow.grade_low} to {dirRow.grade_high}</dd>{/if}
        {#if dirRow.street1}<dt>Address</dt><dd>{dirRow.street1}, {dirRow.city} {dirRow.state} {dirRow.zip}</dd>{/if}
        {#if dirRow.phone}<dt>Phone</dt><dd>{dirRow.phone}</dd>{/if}
        {#if dirRow.website}<dt>Website</dt><dd><a href={String(dirRow.website).startsWith('http') ? String(dirRow.website) : `https://${dirRow.website}`} target="_blank" rel="noopener noreferrer">{dirRow.website}</a></dd>{/if}
        {#if dirRow.operational_schools != null}<dt>Operational schools</dt><dd>{dirRow.operational_schools}</dd>{/if}
        {#if dirRow.charter_lea}<dt>Charter agency</dt><dd>{dirRow.charter_lea}</dd>{/if}
      </dl>
    {/if}
  </aside>
{/if}

<style>
  .panel {
    position: absolute;
    z-index: 6;
    top: 12px;
    right: 12px;
    bottom: 100px;
    width: 430px;
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
  a,
  .link {
    color: var(--accent);
  }
  .link {
    background: none;
    border: 0;
    padding: 0;
    text-decoration: underline;
  }
  .tabs {
    display: flex;
    gap: 4px;
    margin-bottom: 6px;
    flex-wrap: wrap;
    align-items: center;
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
  .toggle {
    font-size: 12px;
    margin-left: 6px;
  }
  .note,
  .muted,
  .cav p {
    color: var(--muted);
    font-size: 12px;
  }
  .err {
    color: #c62828;
  }
  details {
    margin-top: 6px;
  }
  summary {
    cursor: pointer;
    color: var(--accent);
  }
  .mini {
    border-collapse: collapse;
    font-size: 12.5px;
    width: 100%;
    margin: 6px 0;
  }
  .mini th,
  .mini td {
    text-align: right;
    padding: 2px 8px;
    border-bottom: 1px solid var(--border);
  }
  .mini th:first-child,
  .mini td:first-child {
    text-align: left;
  }
  .schools {
    list-style: none;
    margin: 6px 0 0;
    padding: 0;
    max-height: 220px;
    overflow: auto;
    border: 1px solid var(--border);
    border-radius: 6px;
  }
  .schools button {
    width: 100%;
    text-align: left;
    background: none;
    border: 0;
    padding: 5px 8px;
    display: flex;
    flex-direction: column;
    border-bottom: 1px solid var(--border);
  }
  .schools button:hover {
    background: var(--surface-2);
  }
  .schools span {
    color: var(--muted);
    font-size: 12px;
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
