<script lang="ts">
  import { app, surveyYearFor } from '../lib/app.svelte'
  import { loadDictionary, loadValueLabels, pssRows } from '../lib/data'
  import type { Row } from '../lib/db'
  import { fmtInt, localeLabel, schoolYearLabel } from '../lib/labels'
  import type { DictEntry, PrivateSchool, TrendPoint } from '../lib/types'
  import TableExplorer from './TableExplorer.svelte'
  import CompareButton from './CompareButton.svelte'
  import Inspector from './Inspector.svelte'
  import Kpis from './Kpis.svelte'
  import BarList from './BarList.svelte'
  import StatusStrip, { type StripRow } from './StatusStrip.svelte'
  import TrendChart from './TrendChart.svelte'

  type Tab = 'total' | 'grade' | 'race' | 'sex'
  let tab = $state<Tab>('total')
  let view = $state('overview')
  let loading = $state(false)
  let error = $state('')
  let schools = $state<Row[]>([])
  let enr = $state<Row[]>([])
  let tch = $state<Row[]>([])
  let dict = $state<Map<string, DictEntry>>(new Map())
  let labels = $state<Map<string, string>>(new Map())

  const school = $derived<PrivateSchool | undefined>(
    app.selected?.dataset === 'private' ? app.private?.schools.find((s) => s.id === app.selected!.id) : undefined,
  )

  $effect(() => {
    const s = school
    if (!s) return
    let cancelled = false
    loading = true
    error = ''
    Promise.all([pssRows('schools', s.id), pssRows('enrollment', s.id), pssRows('teachers', s.id), loadDictionary(), loadValueLabels()])
      .then(([a, b, c, d, l]) => {
        if (cancelled) return
        schools = a; enr = b; tch = c; dict = d; labels = l
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

  const survey = $derived(surveyYearFor(app.year))
  const row = $derived(schools.find((r) => r.year === survey) ?? schools[schools.length - 1])
  const idx = $derived(school && survey != null ? school.years.indexOf(survey) : -1)
  const enrollNow = $derived(idx >= 0 ? school!.enroll[idx] : null)
  const lab = (col: string, v: unknown) => (v == null || v === '' ? '' : (labels.get(`pss.schools.${col}|${String(v)}`) ?? String(v)))
  const num = (v: unknown) => (typeof v === 'number' ? v : null)

  const series = $derived.by((): TrendPoint[] => {
    const out: TrendPoint[] = []
    for (const r of enr) {
      const y = r.year as number
      const dim = r.dimension as string
      const v = num(r.value)
      if (tab === 'total' && dim === 'total' && String(r.category).startsWith('All students') && !String(r.category).includes('derived')) out.push({ year: y, key: 'Total enrollment', value: v })
      if (tab === 'grade' && dim === 'grade') out.push({ year: y, key: String(r.category), value: v })
      if (tab === 'race' && dim === 'race') out.push({ year: y, key: String(r.category), value: v })
      if (tab === 'sex' && dim === 'sex') out.push({ year: y, key: 'Male students', value: v })
    }
    if (tab === 'sex') {
      for (const r of enr) {
        if (r.dimension === 'total' && r.category === 'All students') {
          const male = enr.find((m) => m.year === r.year && m.dimension === 'sex')
          const t = num(r.value)
          const m = male ? num(male.value) : null
          out.push({ year: r.year as number, key: 'Female students (total minus male)', value: t != null && m != null ? t - m : null })
        }
      }
    }
    return out.sort((a, b) => a.year - b.year)
  })

  const hasData = (s: TrendPoint[]) => s.some((d) => d.value != null)
  const teachers = $derived(
    tch.filter((r) => r.category === 'K-12 teachers (FTE)').map((r): TrendPoint => ({ year: r.year as number, key: 'Teachers (FTE)', value: num(r.value) })),
  )
  const tabs: { id: Tab; label: string }[] = [
    { id: 'total', label: 'Total' }, { id: 'grade', label: 'Grade' }, { id: 'race', label: 'Race/ethnicity' }, { id: 'sex', label: 'Sex' },
  ]
  const caveat = $derived(dict.get('pss.schools.row_id')?.caveat ?? '')
  const ratio = $derived(row?.student_teacher_ratio != null ? Number(row.student_teacher_ratio).toFixed(1) : '')

  const kpis = $derived([
    { label: 'Students', value: enrollNow != null ? fmtInt(enrollNow) : null, sub: survey != null ? `${schoolYearLabel(survey)} survey` : undefined },
    { label: 'Teachers (FTE)', value: row?.teachers_fte != null ? String(row.teachers_fte) : null },
    { label: 'Students per teacher', value: ratio || null, title: 'Student-teacher ratio as reported in the survey. A descriptive figure, not a quality measure.' },
    { label: 'Survey years', value: school ? String(school.years.length) : null, sub: 'this school appears in' },
  ])
  // ------------------------------------------------------------------ who the students are
  const isTotal = (r: Row) => r.dimension === 'total' && r.category === 'All students'
  const raceComp = $derived(
    enr.filter((r) => r.dimension === 'race' && num(r.value) != null).map((r): TrendPoint => ({ year: r.year as number, key: String(r.category), value: num(r.value) })),
  )
  const sexComp = $derived.by((): TrendPoint[] => {
    const out: TrendPoint[] = []
    for (const t of enr.filter(isTotal)) {
      const male = enr.find((m) => m.year === t.year && m.dimension === 'sex')
      const total = num(t.value)
      const m = male ? num(male.value) : null
      if (total != null && m != null && total >= m) out.push({ year: t.year as number, key: 'Male', value: m }, { year: t.year as number, key: 'Female (total minus male)', value: total - m })
    }
    return out.sort((a, b) => a.year - b.year)
  })
  const gradeNow = $derived.by(() => {
    const g = enr.filter((r) => r.dimension === 'grade' && (num(r.value) ?? 0) > 0)
    if (!g.length || survey == null) return null
    const y = g.some((r) => r.year === survey) ? survey : Math.max(...g.map((r) => r.year as number))
    const order = ['Nursery/prekindergarten', 'Transitional kindergarten', 'Kindergarten', 'Transitional first grade', ...Array.from({ length: 12 }, (_, i) => `Grade ${i + 1}`), 'Ungraded']
    const items = g
      .filter((r) => r.year === y)
      .sort((a, b) => order.indexOf(String(a.category)) - order.indexOf(String(b.category)))
      .map((r) => ({ label: String(r.category), value: num(r.value) as number, text: fmtInt(num(r.value) as number) }))
    return { year: y, items }
  })
  const ratioSeries = $derived(
    schools.filter((r) => num(r.student_teacher_ratio) != null).map((r): TrendPoint => ({ year: r.year as number, key: 'Students per teacher', value: num(r.student_teacher_ratio) })),
  )
  const hasPts = (s: TrendPoint[]) => s.some((d) => (d.value ?? 0) > 0)
  const preK = $derived(
    schools.flatMap((r): TrendPoint[] => [
      { year: r.year as number, key: 'Prekindergarten students', value: num(r.pkenroll) },
      { year: r.year as number, key: 'Prekindergarten teachers (FTE)', value: num(r.pkteach) },
    ]),
  )

  // the same fields in every survey year, shown as a history strip
  const profileYears = $derived(schools.map((r) => r.year as number))
  const profileRow = (col: string, label: string, fmt?: (v: unknown) => string): StripRow => ({
    label,
    values: Object.fromEntries(
      schools.filter((r) => r[col] != null && r[col] !== '').map((r) => [r.year as number, fmt ? fmt(r[col]) : lab(col, r[col])]),
    ),
  })
  const profileRows = $derived<StripRow[]>(
    [
      profileRow('level', 'Level'),
      profileRow('relig', 'Affiliation'),
      profileRow('orient', 'Religious orientation'),
      profileRow('typology', 'Typology'),
      profileRow('ulocale', 'Locale', (v) => localeLabel(String(v))),
      profileRow('region', 'Census region'),
    ].filter((r) => Object.keys(r.values).length),
  )

  const views = [
    { id: 'overview', label: 'Overview' },
    { id: 'students', label: 'Students' },
    { id: 'trends', label: 'Trends' },
    { id: 'details', label: 'Details' },
    { id: 'data', label: 'Data' },
  ]
  const tags = $derived(
    [row ? lab('level', row.level) : '', row ? lab('relig', row.relig) : '', school?.approx ? 'Approximate location' : '']
      .filter(Boolean)
      .map(String),
  )
</script>

{#if school}
  <Inspector label="Private school details" kind="Private school" dataset="private" title={school.name} bind:tab={view} tabs={views} {tags}>
    {#snippet sub()}{[school.city, lab('typology', school.typology)].filter(Boolean).join(' · ')}{/snippet}
    {#snippet actions()}<CompareButton dataset="private" id={school.id} />{/snippet}

    {#if error}<p class="err" role="alert">Could not load details: {error}</p>{/if}
    {#if loading && !row}<p class="muted">Loading…</p>{/if}

    <p class="yearline">
      {#if survey != null}
        <strong>{schoolYearLabel(survey)} survey</strong>
        {#if survey !== app.year}<span class="chip" title="The Private School Universe Survey is conducted every two years">biennial: nearest earlier survey</span>{/if}
        {#if idx < 0}<span class="warn">Not in the {schoolYearLabel(survey)} survey; showing its latest record.</span>{/if}
      {:else}
        <span class="warn">Private school data start with the {schoolYearLabel(school.years[0])} survey.</span>
      {/if}
    </p>
    {#if school.approx}
      <p class="note">Approximate location: geocoded from the street address by the U.S. Census Geocoder (non-exact match).</p>
    {/if}

    <div class="tabbody">
      {#if view === 'overview'}
        <div class="span"><Kpis items={kpis} /></div>
        <section class="card span">
          <h3>Enrollment by survey year <small>students</small></h3>
          <div class="subtabs" role="group" aria-label="Enrollment breakdown">
            {#each tabs as t}
              <button class:on={tab === t.id} aria-pressed={tab === t.id} onclick={() => (tab = t.id)}>{t.label}</button>
            {/each}
          </div>
          {#if hasData(series)}
            <TrendChart data={series} currentYear={survey ?? undefined} mode={tab === 'grade' ? 'heat' : 'line'} height={240} alt={`Enrollment by survey year for ${school.name}, ${tab}`} />
            <p class="note">Only survey years are shown (the survey is biennial); gaps between surveys are not missing data.</p>
          {:else if !loading}
            <p class="muted">No enrollment data for this view.</p>
          {/if}
          {#if caveat}<details class="cav"><summary>About these data</summary><p>{caveat}</p></details>{/if}
        </section>
      {:else if view === 'students'}
        <section class="card span">
          <h3>Race and ethnicity <small>share of students, by survey year</small></h3>
          {#if hasPts(raceComp)}
            <TrendChart mode="stack" percent data={raceComp} yLabel="% of students" currentYear={survey ?? undefined} height={240} alt={`Race and ethnicity share of enrollment at ${school.name}`} />
            <p class="note">Only survey years are shown (the survey is biennial). Race categories before 2007 were reported differently.</p>
          {:else}
            <p class="muted">{loading ? 'Loading…' : 'No race/ethnicity data for this school.'}</p>
          {/if}
        </section>
        <section class="card">
          <h3>Grades <small>{gradeNow ? `${schoolYearLabel(gradeNow.year)} survey` : ''}</small></h3>
          {#if gradeNow?.items.length}
            <BarList items={gradeNow.items} label={`Students by grade at ${school.name}`} />
          {:else}
            <p class="muted">{loading ? 'Loading…' : 'No grade counts.'}</p>
          {/if}
        </section>
        <section class="card">
          <h3>Girls and boys <small>share of students</small></h3>
          {#if hasPts(sexComp)}
            <TrendChart mode="stack" percent data={sexComp} yLabel="% of students" currentYear={survey ?? undefined} height={200} alt={`Sex of students at ${school.name}`} />
          {:else}
            <p class="muted">{loading ? 'Loading…' : 'No sex breakdown.'}</p>
          {/if}
        </section>
        <section class="card span">
          <h3>Students per teacher <small>as reported</small></h3>
          {#if hasPts(ratioSeries)}
            <TrendChart data={ratioSeries} yLabel="Students per teacher" currentYear={survey ?? undefined} height={190} alt={`Student-teacher ratio at ${school.name}`} />
            <p class="note">A descriptive ratio from the survey, not a quality measure.</p>
          {:else}
            <p class="muted">{loading ? 'Loading…' : 'No ratio reported.'}</p>
          {/if}
        </section>
        {#if hasPts(preK)}
          <section class="card span">
            <h3>Prekindergarten <small>students and teachers</small></h3>
            <TrendChart data={preK} yLabel="Count" currentYear={survey ?? undefined} height={190} alt={`Prekindergarten students and teachers at ${school.name}`} />
          </section>
        {/if}
      {:else if view === 'trends'}
        <section class="card span">
          <h3>Teachers <small>FTE</small></h3>
          {#if hasData(teachers)}
            <TrendChart data={teachers} yLabel="FTE" currentYear={survey ?? undefined} alt={`Teachers (FTE) by survey year for ${school.name}`} height={210} />
          {:else if !loading}
            <p class="muted">No teacher counts for this school.</p>
          {/if}
        </section>
      {:else if view === 'details'}
        {#if profileRows.length > 1}
          <section class="card span">
            <h3>Profile by survey year</h3>
            <StatusStrip rows={profileRows} years={profileYears} current={survey ?? app.year} label={`Profile by survey year for ${school.name}`} />
            <p class="note">One square per biennial survey. Colours show different values within a row; the selected survey is outlined.</p>
          </section>
        {/if}
        <section class="card span">
          <h3>School details{#if row}<small>{schoolYearLabel(Number(row.year))} survey</small>{/if}</h3>
          {#if row}
            <dl class="facts">
              {#if row.address}<dt>Address</dt><dd>{row.address}, {row.city} {row.state_abbrev} {row.zip}</dd>{/if}
              <dt>Level</dt><dd>{lab('level', row.level)}</dd>
              <dt>Typology</dt><dd>{lab('typology', row.typology)}</dd>
              {#if row.relig != null}<dt>Affiliation</dt><dd>{lab('relig', row.relig)}</dd>{/if}
              {#if row.orient != null}<dt>Orientation</dt><dd>{lab('orient', row.orient)}</dd>{/if}
              {#if row.ulocale}<dt>Locale</dt><dd>{localeLabel(String(row.ulocale))}</dd>{/if}
              {#if row.teachers_fte != null}<dt>Teachers (FTE)</dt><dd>{row.teachers_fte}</dd>{/if}
              {#if ratio}<dt>Student-teacher ratio</dt><dd>{ratio}</dd>{/if}
              <dt>Location source</dt><dd>{school.coordSource === 'geocode' ? 'U.S. Census Geocoder (approximate)' : 'NCES (provided in the survey file)'}</dd>
            </dl>
          {:else if !loading}
            <p class="muted">No survey record found.</p>
          {/if}
        </section>
      {:else}
        <section class="card span">
          <TableExplorer dataset="pss" unitid={school.id} name={school.name} start="schools" />
          <p class="ids">NCES private school PIN {school.id}</p>
        </section>
      {/if}
    </div>
  </Inspector>
{/if}
