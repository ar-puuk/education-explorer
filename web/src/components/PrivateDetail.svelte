<script lang="ts">
  import { app, surveyYearFor } from '../lib/app.svelte'
  import { loadDictionary, loadValueLabels, pssRows } from '../lib/data'
  import type { Row } from '../lib/db'
  import { fmtInt, localeLabel, schoolYearLabel } from '../lib/labels'
  import type { DictEntry, PrivateSchool, TrendPoint } from '../lib/types'
  import TableExplorer from './TableExplorer.svelte'
  import CompareButton from './CompareButton.svelte'
  import TrendChart from './TrendChart.svelte'

  type Tab = 'total' | 'grade' | 'race' | 'sex'
  let tab = $state<Tab>('total')
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
</script>

{#if school}
  <aside class="panel" aria-label="Private school details">
    <div class="head">
      <div>
        <h2>{school.name}</h2>
        <p class="sub">{[school.city, lab('typology', school.typology)].filter(Boolean).join(' · ')}</p>
      </div>
      <button class="close" onclick={() => (app.selected = null)} aria-label="Close details">×</button>
    </div>
    <p class="cmprow"><CompareButton dataset="private" id={school.id} /></p>
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
      {#if enrollNow != null}<span class="enr">{fmtInt(enrollNow)} students</span>{/if}
    </p>
    {#if school.approx}
      <p class="note">Approximate location: geocoded from the street address by the U.S. Census Geocoder (non-exact match).</p>
    {/if}

    <h3>Enrollment by survey year</h3>
    <div class="tabs" role="tablist" aria-label="Enrollment breakdown">
      {#each tabs as t}
        <button role="tab" aria-selected={tab === t.id} class:on={tab === t.id} onclick={() => (tab = t.id)}>{t.label}</button>
      {/each}
    </div>
    {#if hasData(series)}
      <TrendChart data={series} currentYear={survey ?? undefined} mode={tab === 'grade' ? 'heat' : 'line'} alt={`Enrollment by survey year for ${school.name}, ${tab}`} />
      <p class="note">Only survey years are shown (the survey is biennial); gaps between surveys are not missing data.</p>
    {:else if !loading}
      <p class="muted">No enrollment data for this view.</p>
    {/if}

    {#if hasData(teachers)}
      <h3>Teachers (full-time equivalent)</h3>
      <TrendChart data={teachers} yLabel="FTE" currentYear={survey ?? undefined} alt={`Teachers (FTE) by survey year for ${school.name}`} height={170} />
    {/if}
    {#if caveat}<details class="cav"><summary>About these data</summary><p>{caveat}</p></details>{/if}

    {#if row}
      <h3>School details ({schoolYearLabel(Number(row.year))} survey)</h3>
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
    {/if}

    <TableExplorer dataset="pss" unitid={school.id} name={school.name} start="schools" />
    <p class="ids">NCES private school PIN {school.id}</p>
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
    border: 1px dashed var(--border);
    border-radius: 999px;
    padding: 0 8px;
    font-size: 12px;
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
    margin-top: 6px;
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
