<script lang="ts">
  import { app, statusAt } from '../lib/app.svelte'
  import {
    loadDictionary,
    loadStateReference,
    membershipHistory,
    schoolProfile,
    schoolRows,
    schoolCharacteristics,
    schoolDirectoryHistory,
    schoolLocationHistory,
    type MembershipRow,
  } from '../lib/data'
  import type { Row } from '../lib/db'
  import { fmtInt, GRADE_ORDER, gradeLabel, localeLabel, schoolYearLabel } from '../lib/labels'
  import type { DictEntry, ProfileRow, PublicSchool, StateReference, TrendPoint } from '../lib/types'
  import CompareButton from './CompareButton.svelte'
  import Inspector from './Inspector.svelte'
  import Kpis from './Kpis.svelte'
  import TableExplorer from './TableExplorer.svelte'
  import { tooltip } from '../lib/tooltip'
  import BarList from './BarList.svelte'
  import StatusStrip, { type StripRow } from './StatusStrip.svelte'
  import TrendChart from './TrendChart.svelte'
  import { atYear, tally, withinGroups } from '../lib/insights'
  import GroupBars from './GroupBars.svelte'

  type Tab = 'total' | 'race' | 'sex' | 'grade'
  let tab = $state<Tab>('total')
  let view = $state('overview')
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
  let profile = $state<ProfileRow[]>([])
  let reference = $state<StateReference | null>(null)

  const school = $derived<PublicSchool | undefined>(
    app.selected?.dataset === 'public' ? app.points?.schools.find((s) => s.id === app.selected!.id) : undefined,
  )

  // the precomputed profile is one small read, so the headline figures and trends appear before the history tables load
  $effect(() => {
    const s = school
    if (!s) return
    let cancelled = false
    profile = []
    Promise.all([schoolProfile(s.id), loadStateReference()])
      .then(([p, ref]) => {
        if (!cancelled) {
          profile = p
          reference = ref
        }
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  })

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

  // ------------------------------------------------------------------ headline figures (derived/school_profile)
  const prof = (y: number) => profile.find((r) => r.year === y)
  const studentsNow = $derived(prof(app.year)?.enrollment ?? null)
  const teachersNow = $derived(prof(app.year)?.teachers_fte ?? null)
  const ratioNow = $derived(prof(app.year)?.students_per_teacher != null ? prof(app.year)!.students_per_teacher!.toFixed(1) : null)
  const lunchShare = $derived(prof(app.year)?.frl_share != null ? `${Math.round(prof(app.year)!.frl_share! * 100)}%` : null)
  const seriesOf = (col: 'students_per_teacher' | 'teachers_fte' | 'frl_share', key: string, scale = 1): TrendPoint[] =>
    profile.filter((r) => r[col] != null).map((r) => ({ year: r.year, key, value: Math.round((r[col] as number) * scale * 100) / 100 }))
  const ratioSeries = $derived(seriesOf('students_per_teacher', 'Students per teacher (FTE)'))
  const teacherSeries = $derived(seriesOf('teachers_fte', 'Teachers (FTE)'))
  const shareSeries = $derived(seriesOf('frl_share', 'Free or reduced-price lunch eligible (% of enrollment)', 100))

  /** Quartile band and median of a metric across operating public schools, for a dashed reference line. */
  const band = (metric: string, scale = 1) => {
    const ys = reference?.metrics[metric]?.years ?? {}
    return Object.entries(ys).map(([y, v]) => ({ year: Number(y), value: v.median * scale, lo: v.p25 * scale, hi: v.p75 * scale }))
  }
  const refNote = (metric: string) => {
    const v = reference?.metrics[metric]?.years[String(app.year)]
    return v ? `Dashed line: median of operating public schools in the state (${fmtInt(v.n)} schools in ${schoolYearLabel(app.year)}); shaded band: the middle half. For context only.` : ''
  }
  const kpis = $derived([
    { label: 'Students', value: studentsNow != null ? fmtInt(studentsNow) : null, sub: schoolYearLabel(app.year) },
    { label: 'Teachers (FTE)', value: teachersNow != null ? String(Math.round(teachersNow * 10) / 10) : null },
    { label: 'Students per teacher', value: ratioNow, title: 'Enrollment divided by full-time-equivalent teachers. A descriptive ratio, not a quality measure.' },
    { label: 'Free or reduced lunch', value: lunchShare, sub: 'of enrollment', title: lunchCaveat || 'Eligibility counts as reported to NCES' },
  ])
  // ------------------------------------------------------------------ who the students are
  const detailRows = $derived(mem.filter(catA))
  const raceComp = $derived(tally(detailRows, (r) => r.race, (r) => r.student_count))
  const sexComp = $derived(tally(detailRows.filter((r) => r.sex !== 'Not Specified'), (r) => r.sex, (r) => r.student_count))
  const gradeAll = $derived(tally(detailRows, (r) => r.grade, (r) => r.student_count))
  const gradeNow = $derived.by(() => {
    const at = atYear(gradeAll, app.year)
    if (!at) return null
    const items = at.items
      .filter((d) => (d.value ?? 0) > 0)
      .sort((a, b) => GRADE_ORDER.indexOf(a.key) - GRADE_ORDER.indexOf(b.key))
      .map((d) => ({ label: gradeLabel(d.key), value: d.value as number, text: fmtInt(d.value as number) }))
    return { year: at.year, items }
  })
  const raceByGrade = $derived.by(() => {
    const r = withinGroups(detailRows, app.year, (x) => x.grade, (x) => x.race, (x) => x.student_count)
    if (!r) return null
    const groups = r.groups
      .sort((a, b) => GRADE_ORDER.indexOf(a.group) - GRADE_ORDER.indexOf(b.group))
      .map((g) => ({ ...g, group: gradeLabel(g.group) }))
    const keys = [...new Set(r.groups.flatMap((g) => g.segs.map((x) => x.key)))]
    return { year: r.year, groups, keys }
  })
  const lunchStack = $derived(lunchSeries.filter((d) => d.key !== 'Directly certified'))
  const hasPts = (s: TrendPoint[]) => s.some((d) => (d.value ?? 0) > 0)

  // ------------------------------------------------------------------ programs and status history
  const stripYears = $derived([...new Set([...dir, ...chars].map((r) => r.year as number))].sort((a, b) => a - b))
  const strip = (rs: Row[], col: string, label: string): StripRow => ({
    label,
    values: Object.fromEntries(rs.filter((r) => r[col] != null && r[col] !== '').map((r) => [r.year as number, String(r[col])])),
  })
  const stripRows = $derived<StripRow[]>(
    [
      strip(dir, 'status', 'Operating status'),
      {
        label: 'Grades offered',
        values: Object.fromEntries(
          dir.filter((r) => r.grade_low && r.grade_high).map((r) => [r.year as number, gradeLabel(String(r.grade_low)) + '–' + gradeLabel(String(r.grade_high))]),
        ),
      },
      strip(dir, 'level', 'School level'),
      {
        label: 'Locale',
        values: Object.fromEntries(loc.filter((r) => r.locale).map((r) => [r.year as number, localeLabel(String(r.locale))])),
      },
      strip(dir, 'school_type', 'School type'),
      strip(dir, 'charter', 'Charter school'),
      strip(chars, 'virtual', 'Virtual instruction'),
      strip(chars, 'title_i_status', 'Title I status'),
      strip(chars, 'school_wide_title_i_flag', 'Title I school-wide program'),
      strip(chars, 'magnet', 'Magnet school'),
      strip(chars, 'shared_time', 'Shared-time school'),
      strip(chars, 'nslp_status', 'National School Lunch Program'),
    ].filter((r) => Object.keys(r.values).length),
  )

  const views = [
    { id: 'overview', label: 'Overview' },
    { id: 'students', label: 'Students' },
    { id: 'programs', label: 'Programs' },
    { id: 'trends', label: 'Trends' },
    { id: 'details', label: 'Details' },
    { id: 'data', label: 'Data' },
  ]
  const tags = $derived(
    [
      dirRow?.level,
      dirRow?.charter === 'Yes' ? 'Charter' : '',
      locRow?.locale ? localeLabel(String(locRow.locale)) : '',
      charRow?.title_i_status && String(charRow.title_i_status).startsWith('Title I') ? 'Title I' : '',
    ]
      .filter(Boolean)
      .map(String),
  )
</script>

{#if school}
  <Inspector label="School details" kind="Public school" dataset="public" title={school.name} bind:tab={view} tabs={views} {tags}>
    {#snippet sub()}<button class="link" onclick={() => (app.selected = { dataset: 'district', id: school.leaid })}>{school.lea}</button>{/snippet}
    {#snippet actions()}<CompareButton dataset="public" id={school.id} />{/snippet}

    {#if error}<p class="err" role="alert">Could not load details: {error}</p>{/if}
    {#if loading && !dirRow}<p class="muted">Loading…</p>{/if}

    <p class="yearline">
      <strong>{schoolYearLabel(app.year)}</strong>
      {#if !inYear}
        <span class="warn">This school is not in the directory for this year; showing the closest year.</span>
      {:else if status}
        <span class="chip" class:closed={status === 'Closed' || status.startsWith('Future')}>{status}</span>
      {/if}
    </p>

    <div class="tabbody">
      {#if view === 'overview'}
        <div class="span"><Kpis items={kpis} /></div>
        <section class="card span">
          <h3>Enrollment over time <small>students</small></h3>
          <div class="subtabs" role="group" aria-label="Enrollment breakdown">
            {#each tabs as t}
              <button class:on={tab === t.id} aria-pressed={tab === t.id} onclick={() => (tab = t.id)}>{t.label}</button>
            {/each}
          </div>
          {#if mem.length}
            <TrendChart
              data={series}
              currentYear={app.year}
              mode={tab === 'grade' ? 'heat' : 'line'}
              height={240}
              reference={tab === 'total' ? band('enrollment') : undefined}
              alt={`Enrollment by year for ${school.name}, ${tabs.find((t) => t.id === tab)?.label.toLowerCase()}`}
            />
            {#if tab === 'total' && refNote('enrollment')}<p class="note">{refNote('enrollment')}</p>{/if}
            {#if flagged}<p class="note">Some values are missing, suppressed or not reported by the state and are left blank in the chart (never plotted as zero).</p>{/if}
            {#if tab !== 'total'}<p class="note">Detail rows are summed from the race × sex × grade categories reported to NCES.</p>{/if}
          {:else if !loading}
            <p class="muted">No membership data for this school.</p>
          {/if}
          {#if caveat}<details class="cav"><summary>About these counts</summary><p>{caveat}</p></details>{/if}
        </section>
      {:else if view === 'students'}
        <section class="card span">
          <h3>Race and ethnicity <small>share of students</small></h3>
          {#if hasPts(raceComp)}
            <TrendChart mode="stack" percent data={raceComp} yLabel="% of students" currentYear={app.year} height={240} alt={`Race and ethnicity share of enrollment at ${school.name}`} />
            <p class="note">Shares of the students counted in the race × sex × grade categories. Descriptive only.</p>
          {:else}
            <p class="muted">{loading ? 'Loading…' : 'No race/ethnicity data for this school.'}</p>
          {/if}
        </section>
        <section class="card span">
          <h3>Race and ethnicity within each grade <small>{raceByGrade ? schoolYearLabel(raceByGrade.year) : ''}</small></h3>
          {#if raceByGrade}
            <GroupBars groups={raceByGrade.groups} keys={raceByGrade.keys} label={`Race and ethnicity within each grade at ${school.name}`} />
            <p class="note">Each bar is one grade. Small cells are suppressed in the source and left out, so very small grades may not sum to the grade total.</p>
          {:else}
            <p class="muted">{loading ? 'Loading…' : 'No race-by-grade detail.'}</p>
          {/if}
        </section>
        <section class="card">
          <h3>Grades <small>{gradeNow ? schoolYearLabel(gradeNow.year) : ''}</small></h3>
          {#if gradeNow?.items.length}
            <BarList items={gradeNow.items} label={`Students by grade at ${school.name}`} />
          {:else}
            <p class="muted">{loading ? 'Loading…' : 'No grade counts.'}</p>
          {/if}
        </section>
        <section class="card">
          <h3>Girls and boys <small>share of students</small></h3>
          {#if hasPts(sexComp)}
            <TrendChart mode="stack" percent data={sexComp} yLabel="% of students" currentYear={app.year} height={200} alt={`Sex of students at ${school.name}`} />
          {:else}
            <p class="muted">{loading ? 'Loading…' : 'No sex breakdown.'}</p>
          {/if}
        </section>
        <section class="card span">
          <h3>Lunch program eligibility <small>students</small></h3>
          {#if hasPts(lunchStack)}
            <TrendChart mode="stack" data={lunchStack} yLabel="Students" currentYear={app.year} height={200} alt={`Free and reduced-price lunch eligible students at ${school.name}`} />
            <p class="note">{lunchCaveat}</p>
          {:else}
            <p class="muted">{loading ? 'Loading…' : 'No lunch program data for this school.'}</p>
          {/if}
        </section>
      {:else if view === 'programs'}
        <section class="card span">
          <h3>Status and programs by year</h3>
          {#if stripRows.length}
            <StatusStrip rows={stripRows} years={stripYears} current={app.year} label={`Status and programs by year for ${school.name}`} />
            <p class="note">Each square is one school year. Coloured squares are values other than “no”/“not”; dashed squares mean no record. Hover a square for its value. Some fields, such as virtual instruction, were added to the data in later years.</p>
            <p class="note">{desc('school_characteristics', 'title_i_status')}</p>
          {:else}
            <p class="muted">{loading ? 'Loading…' : 'No program data for this school.'}</p>
          {/if}
        </section>
      {:else if view === 'trends'}
        <section class="card">
          <h3>Students per teacher <small>ratio</small></h3>
          {#if ratioSeries.length}
            <TrendChart data={ratioSeries} yLabel="Students per FTE teacher" currentYear={app.year} reference={band('students_per_teacher')} alt={`Students per teacher at ${school.name}`} height={190} />
            <p class="note">Enrollment divided by teachers (FTE). A descriptive ratio, not a quality measure. {refNote('students_per_teacher')}</p>
          {:else}
            <p class="muted">{profile.length ? 'No staffing data for this school.' : 'Loading…'}</p>
          {/if}
        </section>
        <section class="card">
          <h3>Teachers <small>FTE</small></h3>
          {#if teacherSeries.length}
            <TrendChart data={teacherSeries} yLabel="FTE" currentYear={app.year} alt={`Teachers (FTE) at ${school.name}`} height={190} />
          {:else}
            <p class="muted">{profile.length ? 'No teacher counts for this school.' : 'Loading…'}</p>
          {/if}
        </section>
        <section class="card">
          <h3>Free or reduced-price lunch <small>% of enrollment</small></h3>
          {#if shareSeries.length}
            <TrendChart data={shareSeries} yLabel="% of enrollment" currentYear={app.year} reference={band('frl_share', 100)} alt={`Lunch program eligibility share at ${school.name}`} height={190} />
            <p class="note">{lunchCaveat} {refNote('frl_share')}</p>
          {:else}
            <p class="muted">{profile.length ? 'No lunch program data for this school.' : 'Loading…'}</p>
          {/if}
        </section>
        <section class="card">
          <h3>Lunch eligibility counts <small>students</small></h3>
          {#if lunchSeries.some((d) => d.value != null)}
            <TrendChart data={lunchSeries} yLabel="Students" currentYear={app.year} alt={`Lunch program eligibility counts for ${school.name}`} height={190} />
          {:else}
            <p class="muted">No lunch program data for this school.</p>
          {/if}
        </section>
      {:else if view === 'details'}
        <section class="card">
          <h3>School details</h3>
          {#if dirRow}
            <dl class="facts">
              {#each MAIN as k}
                {#if dirRow[k] != null && dirRow[k] !== '' && k !== 'status'}
                  <dt use:tooltip={desc('school_directory', k)}>{MAIN_LABEL[k] ?? label('school_directory', k)}</dt>
                  <dd>{fmt(k, dirRow[k])}</dd>
                {/if}
              {/each}
              {#if locRow?.locale}<dt use:tooltip={desc('school_location', 'locale')}>Locale</dt><dd>{localeLabel(String(locRow.locale))}</dd>{/if}
              {#if locRow?.county_name}<dt>County</dt><dd>{locRow.county_name}</dd>{/if}
              {#if dirRow.street1}<dt>Address</dt><dd>{dirRow.street1}, {dirRow.city} {dirRow.state} {dirRow.zip}</dd>{/if}
              {#if dirRow.phone}<dt>Phone</dt><dd>{dirRow.phone}</dd>{/if}
              {#if dirRow.website}
                <dt>Website</dt>
                <dd><a href={String(dirRow.website).startsWith('http') ? String(dirRow.website) : `https://${dirRow.website}`} target="_blank" rel="noopener noreferrer">{dirRow.website}</a></dd>
              {/if}
              {#if charRow}
                {#each ['title_i_status', 'magnet', 'shared_time', 'nslp_status'] as k}
                  {#if charRow[k] != null && charRow[k] !== ''}
                    <dt use:tooltip={desc('school_characteristics', k)}>{label('school_characteristics', k)}</dt>
                    <dd>{charRow[k]}</dd>
                  {/if}
                {/each}
              {/if}
              {#if locRow?.lat != null}
                <dt use:tooltip={desc('school_location', 'coord_source')}>Location source</dt>
                <dd>{locRow.coord_source === 'edge' ? 'NCES EDGE' : locRow.coord_source === 'edge_prior_year' ? 'NCES EDGE (earlier year)' : locRow.coord_source}</dd>
              {/if}
            </dl>
          {:else if !loading}
            <p class="muted">No directory record found.</p>
          {/if}
        </section>
        {#if otherFields.length}
          <section class="card">
            <details class="more" bind:open={showAll}>
              <summary>All directory fields for {schoolYearLabel(Number(dirRow?.year ?? app.year))} ({otherFields.length})</summary>
              <dl class="facts">
                {#each otherFields as f}
                  <dt use:tooltip={f.d}>{f.label}</dt>
                  <dd>{f.v}</dd>
                {/each}
              </dl>
            </details>
          </section>
        {/if}
      {:else}
        <section class="card span">
          <TableExplorer dataset="ccd" unitid={school.id} name={school.name} start="school_directory"
            only={['school_directory', 'school_characteristics', 'school_location', 'membership', 'lunch', 'staff', 'legacy_school']} />
          <p class="ids">NCES school ID {school.id} · district ID {school.leaid}</p>
        </section>
      {/if}
    </div>
  </Inspector>
{/if}
