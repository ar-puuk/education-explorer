<script lang="ts">
  import { app, isOperating, statusAt } from '../lib/app.svelte'
  import { districtRows, loadDictionary } from '../lib/data'
  import type { Row } from '../lib/db'
  import { download, toCsv } from '../lib/explore'
  import { atYear, n } from '../lib/insights'
  import { fmtInt, GRADE_ORDER, gradeLabel, levelLabel, schoolYearLabel } from '../lib/labels'
  import BarList from './BarList.svelte'
  import type { DictEntry, PublicSchool, TrendPoint } from '../lib/types'
  import CompareButton from './CompareButton.svelte'
  import Inspector from './Inspector.svelte'
  import Kpis from './Kpis.svelte'
  import TableExplorer from './TableExplorer.svelte'
  import TrendChart from './TrendChart.svelte'

  let { onSelectSchool }: { onSelectSchool: (id: string, lon: number, lat: number) => void } = $props()

  type Tab = 'enroll' | 'staff' | 'finance' | 'students'
  let tab = $state<Tab>('staff')
  let view = $state('overview')
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
    { id: 'staff', label: 'Staff' }, { id: 'finance', label: 'Finance' }, { id: 'students', label: 'Students' },
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

  const haveEnroll = $derived(schools.some((x) => x.enroll != null))
  const kpis = $derived([
    { label: 'Students reported', value: reportedNow != null ? fmtInt(reportedNow) : null, sub: schoolYearLabel(app.year) },
    { label: 'Operating schools', value: schools.length ? String(schools.length) : null },
    { label: 'Sum of school enrollment', value: schools.length && haveEnroll ? fmtInt(schoolSum) : null, title: 'Adds up the enrollment of the district schools in the school directory. It can differ from the district-reported total.' },
    { label: 'Grades', value: dirRow?.grade_low ? `${dirRow.grade_low}–${dirRow.grade_high}` : null },
  ])
  // ---------------------------------------------------------------- who the students are
  const sexComp = $derived(sumBy(mem.filter(catA).filter((r) => r.sex !== 'Not Specified'), (r) => String(r.sex)).sort((a, b) => a.year - b.year))
  const gradeNow = $derived.by(() => {
    const g = sumBy(mem.filter(catA), (r) => String(r.grade)).filter((d) => (d.value ?? 0) > 0)
    const at = atYear(g, app.year)
    if (!at) return null
    const items = at.items
      .sort((a, b) => GRADE_ORDER.indexOf(a.key) - GRADE_ORDER.indexOf(b.key))
      .map((d) => ({ label: gradeLabel(d.key), value: d.value as number, text: fmtInt(d.value as number) }))
    return { year: at.year, items }
  })
  /** English learners and students with disabilities as a share of reported enrollment. */
  const needShare = $derived.by((): TrendPoint[] => {
    const tot = new Map(enrollTotal.map((d) => [d.year, d.value]))
    const out: TrendPoint[] = []
    for (const [rs, col, key] of [[el, 'lep_count', 'English learners'], [idea, 'idea_count', 'Students with disabilities (IDEA)']] as const) {
      for (const r of rs) {
        const c = n(r[col])
        const t = tot.get(r.year as number)
        if (c != null && t) out.push({ year: r.year as number, key, value: Math.round((c / t) * 1000) / 10 })
      }
    }
    return out.sort((a, b) => a.year - b.year)
  })
  const hasPts = (s: TrendPoint[]) => s.some((d) => (d.value ?? 0) > 0)

  // ---------------------------------------------------------------- money, per pupil
  const perPupil = (parts: [string, string][]): TrendPoint[] => {
    const out: TrendPoint[] = []
    for (const r of fin) {
      const pupils = n(r.v33)
      if (!pupils || pupils <= 0) continue
      for (const [c, key] of parts) {
        const v = n(r[c])
        if (v != null && v >= 0) out.push({ year: r.year as number, key, value: Math.round(v / pupils) })
      }
    }
    return out.sort((a, b) => a.year - b.year)
  }
  const revenuePP = $derived(perPupil([['tfedrev', 'Federal'], ['tstrev', 'State'], ['tlocrev', 'Local']]))
  const spendPP = $derived(perPupil([['tcurinst', 'Instruction'], ['tcurssvc', 'Support services'], ['tcuroth', 'Other current spending'], ['tnonelse', 'Non-K-12 programs'], ['tcapout', 'Capital outlay']]))

  const views = [
    { id: 'overview', label: 'Overview' },
    { id: 'students', label: 'Students' },
    { id: 'money', label: 'Money' },
    { id: 'trends', label: 'Trends' },
    { id: 'schools', label: 'Schools' },
    { id: 'details', label: 'Details' },
    { id: 'data', label: 'Data' },
  ]
  const tags = $derived([dirRow?.lea_type ? String(dirRow.lea_type) : '', dirRow?.status ? String(dirRow.status) : ''].filter((t) => t && t.length <= 34))
</script>

{#if leaid}
  <Inspector label="District details" kind="School district" dataset="district" title={name} bind:tab={view} tabs={views} {tags}>
    {#snippet sub()}NCES district ID {leaid}{/snippet}
    {#snippet actions()}<CompareButton dataset="district" id={leaid} />{/snippet}

    {#if error}<p class="err" role="alert">Could not load details: {error}</p>{/if}
    {#if loading && !dir.length}<p class="muted">Loading…</p>{/if}

    <p class="yearline">
      <strong>{schoolYearLabel(app.year)}</strong>
      {#if dir.length && !inDir}<span class="warn">Not in the district directory for this year (charter or non-geographic agencies have no boundary); showing the closest year.</span>{/if}
    </p>

    <div class="tabbody">
      {#if view === 'overview'}
        <div class="span"><Kpis items={kpis} /></div>
        <section class="card span">
          <h3>Enrollment over time <small>students</small></h3>
          <div class="subtabs" role="group" aria-label="Enrollment view">
            <button class:on={!raceView} aria-pressed={!raceView} onclick={() => (raceView = false)}>Total</button>
            <button class:on={raceView} aria-pressed={raceView} onclick={() => (raceView = true)}>By race/ethnicity</button>
          </div>
          {#if (raceView ? enrollRace : enrollTotal).some((d) => d.value != null)}
            <TrendChart data={raceView ? enrollRace : enrollTotal} yLabel="Students" currentYear={app.year} height={240} alt={`Enrollment for ${name}`} />
          {:else if !loading}
            <p class="muted">No enrollment data for this district.</p>
          {/if}
          {#if dict.get('ccd.district_membership.student_count')?.caveat}
            <details class="cav"><summary>About these counts</summary><p>{dict.get('ccd.district_membership.student_count')?.caveat}</p></details>
          {/if}
        </section>
      {:else if view === 'students'}
        <section class="card span">
          <h3>Race and ethnicity <small>share of students</small></h3>
          {#if hasPts(enrollRace)}
            <TrendChart mode="stack" percent data={enrollRace} yLabel="% of students" currentYear={app.year} height={250} alt={`Race and ethnicity share of enrollment in ${name}`} />
          {:else}
            <p class="muted">{loading ? 'Loading…' : 'No race/ethnicity data for this district.'}</p>
          {/if}
        </section>
        <section class="card">
          <h3>Grades <small>{gradeNow ? schoolYearLabel(gradeNow.year) : ''}</small></h3>
          {#if gradeNow?.items.length}
            <BarList items={gradeNow.items} label={`Students by grade in ${name}`} />
          {:else}
            <p class="muted">{loading ? 'Loading…' : 'No grade counts.'}</p>
          {/if}
        </section>
        <section class="card">
          <h3>Girls and boys <small>share of students</small></h3>
          {#if hasPts(sexComp)}
            <TrendChart mode="stack" percent data={sexComp} yLabel="% of students" currentYear={app.year} height={210} alt={`Sex of students in ${name}`} />
          {:else}
            <p class="muted">{loading ? 'Loading…' : 'No sex breakdown.'}</p>
          {/if}
        </section>
        <section class="card span">
          <h3>Students with additional needs <small>% of reported enrollment</small></h3>
          {#if hasPts(needShare)}
            <TrendChart data={needShare} unit="%" yLabel="% of enrollment" currentYear={app.year} height={200} alt={`English learners and students with disabilities as a share of enrollment in ${name}`} />
            <p class="note">Counts of English learners (to 2018) and students served under IDEA (to 2019) divided by district enrollment in the same year. Definitions and identification practices differ by state and over time.</p>
          {:else}
            <p class="muted">{loading ? 'Loading…' : 'No English-learner or IDEA counts for this district.'}</p>
          {/if}
        </section>
      {:else if view === 'money'}
        <section class="card span">
          <h3>Revenue per student <small>dollars, by source</small></h3>
          {#if hasPts(revenuePP)}
            <TrendChart mode="stack" unit="$" data={revenuePP} yLabel="Dollars per student" currentYear={app.year} height={240} alt={`Revenue per student by source in ${name}`} />
          {:else}
            <p class="muted">{loading ? 'Loading…' : 'No finance data for this district.'}</p>
          {/if}
        </section>
        <section class="card span">
          <h3>Spending per student <small>dollars, by purpose</small></h3>
          {#if hasPts(spendPP)}
            <TrendChart mode="stack" unit="$" data={spendPP} yLabel="Dollars per student" currentYear={app.year} height={240} alt={`Spending per student by purpose in ${name}`} />
            <p class="note">Total dollars divided by fall membership from the finance survey (F-33). Not adjusted for inflation or local costs, and not a measure of quality.</p>
          {:else}
            <p class="muted">{loading ? 'Loading…' : 'No expenditure data for this district.'}</p>
          {/if}
        </section>
      {:else if view === 'trends'}
        <section class="card span">
          <h3>District trends</h3>
          <div class="subtabs" role="group" aria-label="District data">
            {#each tabs as t}
              <button class:on={tab === t.id} aria-pressed={tab === t.id} onclick={() => (tab = t.id)}>{t.label}</button>
            {/each}
          </div>
          {#if hasData}
            <TrendChart data={current} yLabel={yLabel} currentYear={app.year} height={240} alt={`${tabs.find((t) => t.id === tab)?.label} for ${name}`} />
            <p class="note"><button class="link" onclick={exportCsv}>Download these series as CSV</button></p>
          {:else if !loading}
            <p class="muted">No data for this view (not every table covers every year or district).</p>
          {/if}
          {#if cav2}<details class="cav"><summary>About these data</summary><p>{cav2}</p></details>{/if}
        </section>
      {:else if view === 'schools'}
        <section class="card span">
          <h3>Schools in this district <small>{schoolYearLabel(app.year)}</small></h3>
          {#if schools.length}
            <p class="muted">
              {schools.length} operating schools{#if haveEnroll}; school enrollment adds up to {fmtInt(schoolSum)}{#if reportedNow != null} (district-reported total {fmtInt(reportedNow)}){/if}{:else}; no school enrollment is available for this year{/if}.
            </p>
            <table class="mini">
              <thead><tr><th scope="col">Level</th><th scope="col">Schools</th><th scope="col">Students</th></tr></thead>
              <tbody>{#each byLevel as [lv, v]}<tr><td>{lv}</td><td>{v.n}</td><td>{haveEnroll ? fmtInt(v.enroll) : '—'}</td></tr>{/each}</tbody>
            </table>
            <ul class="schools">
              {#each schools as { s, enroll }}
                <li><button onclick={() => onSelectSchool(s.id, s.lon, s.lat)}>{s.name}<span>{levelLabel(s.level)} · {fmtInt(enroll)}</span></button></li>
              {/each}
            </ul>
          {:else if !loading}
            <p class="muted">No operating schools in the school directory for this district and year.</p>
          {/if}
        </section>
      {:else if view === 'details'}
        <section class="card span">
          <h3>District details</h3>
          {#if dirRow}
            <dl class="facts">
              {#if dirRow.lea_type}<dt>Type</dt><dd>{dirRow.lea_type}</dd>{/if}
              {#if dirRow.grade_low}<dt>Grades</dt><dd>{dirRow.grade_low} to {dirRow.grade_high}</dd>{/if}
              {#if dirRow.street1}<dt>Address</dt><dd>{dirRow.street1}, {dirRow.city} {dirRow.state} {dirRow.zip}</dd>{/if}
              {#if dirRow.phone}<dt>Phone</dt><dd>{dirRow.phone}</dd>{/if}
              {#if dirRow.website}<dt>Website</dt><dd><a href={String(dirRow.website).startsWith('http') ? String(dirRow.website) : `https://${dirRow.website}`} target="_blank" rel="noopener noreferrer">{dirRow.website}</a></dd>{/if}
              {#if dirRow.operational_schools != null}<dt>Operational schools</dt><dd>{dirRow.operational_schools}</dd>{/if}
              {#if dirRow.charter_lea}<dt>Charter agency</dt><dd>{dirRow.charter_lea}</dd>{/if}
            </dl>
          {:else if !loading}
            <p class="muted">No directory record found.</p>
          {/if}
        </section>
      {:else}
        <section class="card span">
          <TableExplorer dataset="ccd" idKind="district" unitid={leaid} name={name} start="district_directory"
            only={['district_directory', 'district_membership', 'district_staff', 'district_finance', 'district_graduates', 'district_dropout', 'district_idea', 'district_el', 'legacy_district']} />
        </section>
      {/if}
    </div>
  </Inspector>
{/if}

<style>
  .mini {
    border-collapse: collapse;
    font: 12.5px var(--f-data);
    width: 100%;
    margin: 8px 0;
  }
  .mini th,
  .mini td {
    text-align: right;
    padding: 4px 8px;
    border-bottom: 1px solid var(--border);
  }
  .mini th {
    font: 500 11.5px var(--f-body);
    color: var(--muted);
  }
  .mini th:first-child,
  .mini td:first-child {
    text-align: left;
  }
  .schools {
    list-style: none;
    margin: 6px 0 0;
    padding: 0;
    max-height: 340px;
    overflow: auto;
    border: 1px solid var(--border);
    border-radius: 8px;
  }
  .schools button {
    width: 100%;
    text-align: left;
    background: none;
    border: 0;
    padding: 6px 10px;
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
</style>
