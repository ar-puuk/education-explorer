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
  const views = [
    { id: 'overview', label: 'Overview' },
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
        <section class="card span">
          <h3>School details {#if row}<small>{schoolYearLabel(Number(row.year))} survey</small>{/if}</h3>
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
