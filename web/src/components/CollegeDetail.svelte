<script lang="ts">
  import { app } from '../lib/app.svelte'
  import { ipedsRows, loadDictionary, loadValueLabels } from '../lib/data'
  import type { Row } from '../lib/db'
  import { fmtInt, schoolYearLabel } from '../lib/labels'
  import type { CollegeInstitution, DictEntry, TrendPoint } from '../lib/types'
  import TableExplorer from './TableExplorer.svelte'
  import CompareButton from './CompareButton.svelte'
  import Inspector from './Inspector.svelte'
  import Kpis from './Kpis.svelte'
  import TrendChart from './TrendChart.svelte'

  type Tab = 'total' | 'level' | 'attend' | 'gender' | 'race'
  let tab = $state<Tab>('total')
  let view = $state('overview')
  let loading = $state(false)
  let error = $state('')
  let hd = $state<Row[]>([])
  let efa = $state<Row[]>([])
  let effy = $state<Row[]>([])
  let ca = $state<Row[]>([])
  let adm = $state<Row[]>([])
  let dict = $state<Map<string, DictEntry>>(new Map())
  let labels = $state<Map<string, string>>(new Map())

  const inst = $derived<CollegeInstitution | undefined>(
    app.selected?.dataset === 'college' ? app.college?.institutions.find((s) => s.id === app.selected!.id) : undefined,
  )

  $effect(() => {
    const c = inst
    if (!c) return
    let cancelled = false
    loading = true
    error = ''
    Promise.all([
      ipedsRows('hd', c.id), ipedsRows('efa', c.id), ipedsRows('effy', c.id), ipedsRows('ca', c.id), ipedsRows('adm', c.id),
      loadDictionary(), loadValueLabels(),
    ])
      .then(([a, b, d, e, f, dc, lb]) => {
        if (cancelled) return
        hd = a; efa = b; effy = d; ca = e; adm = f; dict = dc; labels = lb
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

  const pickYear = (rows: Row[]) => rows.find((r) => r.year === app.year) ?? [...rows].reverse().find((r) => (r.year as number) < app.year) ?? rows[0]
  const row = $derived(pickYear(hd))
  const lab = (col: string, v: unknown) => (v == null ? '' : (labels.get(`ipeds.hd.${col}|${String(v)}`) ?? String(v)))
  const num = (v: unknown) => (typeof v === 'number' ? v : null)
  const inYear = $derived(inst ? inst.years.includes(app.year) : false)
  const idx = $derived(inst ? inst.years.indexOf(app.year) : -1)
  const active = $derived(idx >= 0 ? inst!.active[idx] === 1 : false)
  const enrollNow = $derived(idx >= 0 ? inst!.enroll[idx] : null)

  // ------------------------------------------------------------------ fall enrollment series
  const LEVELS: Record<number, string> = { 2: 'Undergraduate', 12: 'Graduate' }
  const ATTEND: Record<number, string> = { 21: 'Full-time', 41: 'Part-time' }
  const RACE: [string, string][] = [
    ['efaiant', 'American Indian or Alaska Native'], ['efasiat', 'Asian'], ['efbkaat', 'Black or African American'],
    ['efhispt', 'Hispanic/Latino'], ['efnhpit', 'Native Hawaiian or Pacific Islander'], ['efwhitt', 'White'],
    ['ef2mort', 'Two or more races'], ['efunknt', 'Race/ethnicity unknown'], ['efnralt', 'U.S. nonresident'],
  ]

  const enrollSeries = $derived.by((): TrendPoint[] => {
    const out: TrendPoint[] = []
    for (const r of efa) {
      const y = r.year as number
      const lv = r.efalevel as number
      if (tab === 'total' && lv === 1) out.push({ year: y, key: 'All students', value: num(r.eftotlt) })
      if (tab === 'level' && LEVELS[lv]) out.push({ year: y, key: LEVELS[lv], value: num(r.eftotlt) })
      if (tab === 'attend' && ATTEND[lv]) out.push({ year: y, key: ATTEND[lv], value: num(r.eftotlt) })
      if (tab === 'gender' && lv === 1) {
        out.push({ year: y, key: 'Men', value: num(r.eftotlm) }, { year: y, key: 'Women', value: num(r.eftotlw) })
      }
      if (tab === 'race' && lv === 1 && y >= 2010) for (const [c, l] of RACE) out.push({ year: y, key: l, value: num(r[c]) })
    }
    return out.sort((a, b) => a.year - b.year)
  })

  const effySeries = $derived(
    effy.filter((r) => r.effylev === 1 || r.effylev === 2 || r.effylev === 4).map((r): TrendPoint => ({
      year: r.year as number,
      key: r.effylev === 1 ? 'All students' : r.effylev === 2 ? 'Undergraduate' : 'Graduate',
      value: num(r.efytotlt),
    })),
  )

  const AWARD: Record<string, string> = {
    '3': "Associate's degrees", '5': "Bachelor's degrees", '7': "Master's degrees", '17': 'Doctoral degrees (research)',
    '18': 'Doctoral degrees (professional practice)', '19': 'Doctoral degrees (other)',
  }
  const awardSeries = $derived.by((): TrendPoint[] => {
    const m = new Map<string, number>()
    for (const r of ca) {
      if (r.majornum !== 1 && r.majornum != null) continue
      if (num(r.ctotalt) == null) continue
      const lv = String(r.awlevel)
      const key = AWARD[lv] ?? (['2', '4', '20', '21', '1a', '1b'].includes(lv) ? 'Certificates (below bachelor\'s)' : ['6', '8'].includes(lv) ? 'Post-baccalaureate / post-master\'s certificates' : `Award level ${lv}`)
      const k = `${r.year}|${key}`
      m.set(k, (m.get(k) ?? 0) + (r.ctotalt as number))
    }
    return [...m].map(([k, value]) => {
      const [y, key] = k.split('|')
      return { year: Number(y), key, value }
    }).sort((a, b) => a.year - b.year)
  })

  const admSeries = $derived(
    adm.flatMap((r): TrendPoint[] => [
      { year: r.year as number, key: 'Applicants', value: num(r.applcn) },
      { year: r.year as number, key: 'Admitted', value: num(r.admssn) },
      { year: r.year as number, key: 'Enrolled', value: num(r.enrlt) },
    ]),
  )

  const tabs: { id: Tab; label: string }[] = [
    { id: 'total', label: 'Total' }, { id: 'level', label: 'Level' }, { id: 'attend', label: 'Full/part-time' },
    { id: 'gender', label: 'Gender' }, { id: 'race', label: 'Race/ethnicity' },
  ]
  const caveat = (t: string) => dict.get(`ipeds.${t}.unitid`)?.caveat ?? ''
  const web = $derived(row?.webaddr ? String(row.webaddr) : (inst?.web ?? ''))

  const effyNow = $derived(effySeries.find((d) => d.year === app.year && d.key === 'All students')?.value ?? null)
  const awardsNow = $derived.by(() => {
    const rows = awardSeries.filter((d) => d.year === app.year)
    return rows.length ? rows.reduce((t, d) => t + (d.value ?? 0), 0) : null
  })
  const kpis = $derived([
    { label: 'Fall enrollment', value: enrollNow != null ? fmtInt(enrollNow) : null, sub: schoolYearLabel(app.year) },
    { label: '12-month headcount', value: effyNow != null ? fmtInt(effyNow) : null, sub: 'unduplicated' },
    { label: 'Awards conferred', value: awardsNow != null ? fmtInt(awardsNow) : null, sub: 'first majors' },
    { label: 'Status', value: inYear ? (active ? 'Active' : 'Not active') : null },
  ])
  const views = [
    { id: 'overview', label: 'Overview' },
    { id: 'trends', label: 'Trends' },
    { id: 'details', label: 'Details' },
    { id: 'data', label: 'Data' },
  ]
  const tags = $derived(
    [row ? lab('control', row.control) : '', row ? lab('iclevel', row.iclevel) : '', row?.hbcu === 1 ? 'HBCU' : '', inst?.approx ? 'Approximate location' : '']
      .filter(Boolean)
      .map(String),
  )
</script>

{#if inst}
  <Inspector label="College details" kind="College" dataset="college" title={inst.name} bind:tab={view} tabs={views} {tags}>
    {#snippet sub()}{[inst.city, lab('sector', inst.sector)].filter(Boolean).join(' · ')}{/snippet}
    {#snippet actions()}<CompareButton dataset="college" id={inst.id} />{/snippet}

    {#if error}<p class="err" role="alert">Could not load details: {error}</p>{/if}
    {#if loading && !row}<p class="muted">Loading…</p>{/if}

    <p class="yearline">
      <strong>{schoolYearLabel(app.year)}</strong>
      {#if !inYear}<span class="warn">Not in the IPEDS directory for this year; showing the closest year.</span>{/if}
    </p>
    {#if inst.approx}
      <p class="note">Approximate location: geocoded from the street address by the U.S. Census Geocoder (non-exact match). NCES provides no coordinates for this institution.</p>
    {:else if inst.coordSource === 'geocode'}
      <p class="note">Location geocoded from the street address by the U.S. Census Geocoder (exact match); NCES provides no coordinates for this institution.</p>
    {/if}

    <div class="tabbody">
      {#if view === 'overview'}
        <div class="span"><Kpis items={kpis} /></div>
        <section class="card span">
          <h3>Fall enrollment <small>students</small></h3>
          <div class="subtabs" role="group" aria-label="Enrollment breakdown">
            {#each tabs as t}
              <button class:on={tab === t.id} aria-pressed={tab === t.id} onclick={() => (tab = t.id)}>{t.label}</button>
            {/each}
          </div>
          {#if enrollSeries.length}
            <TrendChart data={enrollSeries} currentYear={app.year} height={240} alt={`Fall enrollment at ${inst.name}, ${tab}`} />
            {#if tab === 'race'}<p class="note">Race/ethnicity categories before 2010 are not comparable; the chart starts in 2010.</p>{/if}
          {:else if !loading}
            <p class="muted">No fall enrollment data for this view.</p>
          {/if}
          {#if caveat('efa')}<details class="cav"><summary>About these counts</summary><p>{caveat('efa')}</p></details>{/if}
        </section>
      {:else if view === 'trends'}
        <section class="card">
          <h3>12-month unduplicated headcount <small>students</small></h3>
          {#if effySeries.length}
            <TrendChart data={effySeries} currentYear={app.year} alt={`12-month enrollment at ${inst.name}`} height={200} />
          {:else if !loading}
            <p class="muted">No 12-month enrollment data.</p>
          {/if}
        </section>
        <section class="card">
          <h3>Awards conferred <small>completions</small></h3>
          {#if awardSeries.length}
            <TrendChart data={awardSeries} yLabel="Awards" currentYear={app.year} alt={`Awards conferred at ${inst.name}`} height={200} />
            <p class="note">First majors only; 2008 onward in this chart (older years are in the data tables).</p>
          {:else if !loading}
            <p class="muted">No completions data.</p>
          {/if}
        </section>
        {#if admSeries.some((d) => d.value != null)}
          <section class="card span">
            <h3>Admissions <small>first-time undergraduates</small></h3>
            <TrendChart data={admSeries} yLabel="Students" currentYear={app.year} alt={`Applicants, admitted and enrolled at ${inst.name}`} height={210} />
            <p class="note">{caveat('adm')}</p>
          </section>
        {/if}
      {:else if view === 'details'}
        <section class="card span">
          <h3>Institution details {#if row}<small>{schoolYearLabel(Number(row.year))}</small>{/if}</h3>
          {#if row}
            <dl class="facts">
              <dt>Control</dt><dd>{lab('control', row.control)}</dd>
              <dt>Level</dt><dd>{lab('iclevel', row.iclevel)}</dd>
              <dt>Sector</dt><dd>{lab('sector', row.sector)}</dd>
              {#if row.locale != null}<dt>Locale</dt><dd>{lab('locale', row.locale)}</dd>{/if}
              {#if row.addr}<dt>Address</dt><dd>{row.addr}, {row.city} {row.stabbr} {row.zip}</dd>{/if}
              {#if row.countynm}<dt>County</dt><dd>{row.countynm}</dd>{/if}
              {#if row.hbcu === 1}<dt>HBCU</dt><dd>Yes</dd>{/if}
              {#if web}<dt>Website</dt><dd><a href={web.startsWith('http') ? web : `https://${web}`} target="_blank" rel="noopener noreferrer">{web}</a></dd>{/if}
            </dl>
          {:else if !loading}
            <p class="muted">No directory record found.</p>
          {/if}
        </section>
      {:else}
        <section class="card span">
          <TableExplorer unitid={inst.id} name={inst.name} />
          <p class="ids">IPEDS unit ID {inst.id}</p>
        </section>
      {/if}
    </div>
  </Inspector>
{/if}
