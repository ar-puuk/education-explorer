<script lang="ts">
  import { untrack } from 'svelte'
  import { app } from '../lib/app.svelte'
  import { ipedsRows, loadDictionary, loadValueLabels } from '../lib/data'
  import type { Row } from '../lib/db'
  import {
    columns, EXPENSE_PARTS, financeSeries, learningMode, MODE_LABELS, n, netPriceByIncome, pct1, REVENUE_PARTS, shareOf, summed, tuition,
  } from '../lib/insights'
  import { fmtInt, schoolYearLabel } from '../lib/labels'
  import type { CollegeInstitution, DictEntry, TrendPoint } from '../lib/types'
  import BarList from './BarList.svelte'
  import CompareButton from './CompareButton.svelte'
  import Inspector from './Inspector.svelte'
  import Kpis from './Kpis.svelte'
  import TableExplorer from './TableExplorer.svelte'
  import TrendChart from './TrendChart.svelte'

  type Tab = 'total' | 'level' | 'attend' | 'gender' | 'race'
  type Mode = 'all' | 'ug' | 'grad'
  let tab = $state<Tab>('total')
  let mode = $state<Mode>('all')
  let modeShare = $state(true)
  let view = $state('overview')
  let loading = $state(false)
  let error = $state('')
  let rows = $state<Record<string, Row[]>>({})
  let dict = $state<Map<string, DictEntry>>(new Map())
  let labels = $state<Map<string, string>>(new Map())

  // Each tab reads only the IPEDS tables it draws, the first time it is opened (every table is one file per year).
  const BASE = ['hd', 'efa', 'effy', 'ca', 'efadist']
  const NEEDS: Record<string, string[]> = {
    overview: [],
    students: ['adm', 'drvef', 'efd', 'drvhr'],
    outcomes: ['efd', 'drvgr', 'om'],
    costs: ['icay', 'drvic', 'drvcost', 'sfa', 'drvf'],
  }

  const inst = $derived<CollegeInstitution | undefined>(
    app.selected?.dataset === 'college' ? app.college?.institutions.find((s) => s.id === app.selected!.id) : undefined,
  )

  let pending = 0
  $effect(() => {
    const c = inst
    if (!c) return
    let cancelled = false
    loading = true
    error = ''
    Promise.all([loadDictionary(), loadValueLabels()])
      .then(([dc, lb]) => {
        if (!cancelled) {
          dict = dc
          labels = lb
        }
      })
      .catch(() => {})
    // $effect tracks `view` below through load(); each table is requested once per institution
    const requested = new Set<string>()
    untrack(() => (rows = {}))
    const load = (tables: string[]) => {
      const want = tables.filter((t) => !requested.has(t))
      want.forEach((t) => requested.add(t))
      if (!want.length) return
      pending++
      loading = true
      Promise.all(want.map((t) => ipedsRows(t, c.id).catch(() => [] as Row[])))
        .then((all) => {
          if (!cancelled) rows = { ...rows, ...Object.fromEntries(want.map((t, i) => [t, all[i]])) }
        })
        .catch((e) => {
          if (!cancelled) error = String(e?.message ?? e)
        })
        .finally(() => {
          pending--
          if (!cancelled && pending === 0) loading = false
        })
    }
    loaders.set(c.id, load)
    load(BASE)
    load(NEEDS[untrack(() => view)] ?? [])
    return () => {
      cancelled = true
      loaders.delete(c.id)
    }
  })
  const loaders = new Map<string, (t: string[]) => void>()
  // opening a tab asks the current institution's loader for that tab's tables
  $effect(() => {
    const need = NEEDS[view] ?? []
    if (inst && need.length) loaders.get(inst.id)?.(need)
  })

  const R = (t: string) => rows[t] ?? []
  const pickYear = (rs: Row[]) => rs.find((r) => r.year === app.year) ?? [...rs].reverse().find((r) => (r.year as number) < app.year) ?? rs[0]
  const row = $derived(pickYear(R('hd')))
  const lab = (col: string, v: unknown) => (v == null ? '' : (labels.get(`ipeds.hd.${col}|${String(v)}`) ?? String(v)))
  const num = (v: unknown) => n(v)
  const inYear = $derived(inst ? inst.years.includes(app.year) : false)
  const idx = $derived(inst ? inst.years.indexOf(app.year) : -1)
  const active = $derived(idx >= 0 ? inst!.active[idx] === 1 : false)
  const enrollNow = $derived(idx >= 0 ? inst!.enroll[idx] : null)
  const has = (s: TrendPoint[]) => s.some((d) => d.value != null)

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
    for (const r of R('efa')) {
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
  const raceSeries = $derived.by((): TrendPoint[] => {
    const out: TrendPoint[] = []
    for (const r of R('efa')) if (r.efalevel === 1 && (r.year as number) >= 2010) for (const [c, l] of RACE) out.push({ year: r.year as number, key: l, value: num(r[c]) })
    return out.sort((a, b) => a.year - b.year)
  })

  // ------------------------------------------------------------------ learning mode (distance education)
  const LEVEL_CODE: Record<Mode, number> = { all: 1, ug: 2, grad: 12 }
  const fallMode = $derived(learningMode(R('efadist'), 'efdelev', LEVEL_CODE[mode], { none: 'efdenon', som: 'efdesom', exc: 'efdeexc' }))
  const yearMode = $derived(learningMode(R('effydist'), 'effydlev', LEVEL_CODE[mode], { none: 'efydenon', som: 'efydesom', exc: 'efydeexc' }))
  const onlineOnlyShare = $derived(shareOf(learningMode(R('efadist'), 'efdelev', 1, { none: 'efdenon', som: 'efdesom', exc: 'efdeexc' }), MODE_LABELS.exc))
  const onlineNow = $derived(onlineOnlyShare.find((d) => d.year === app.year)?.value ?? null)

  const effySeries = $derived(
    R('effy').filter((r) => r.effylev === 1 || r.effylev === 2 || r.effylev === 4).map((r): TrendPoint => ({
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
    for (const r of R('ca')) {
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
    R('adm').flatMap((r): TrendPoint[] => [
      { year: r.year as number, key: 'Applicants', value: num(r.applcn) },
      { year: r.year as number, key: 'Admitted', value: num(r.admssn) },
      { year: r.year as number, key: 'Enrolled', value: num(r.enrlt) },
    ]),
  )
  const admitRate = $derived(
    R('adm').flatMap((r): TrendPoint[] => {
      const a = num(r.applcn)
      const d = num(r.admssn)
      return a && d != null ? [{ year: r.year as number, key: 'Admitted (% of applicants)', value: Math.round((d / a) * 1000) / 10 }] : []
    }),
  )

  // ------------------------------------------------------------------ students
  const residence = $derived(
    columns(R('drvef'), [['rminsttp', 'In-state'], ['rmousttp', 'Out-of-state'], ['rmfrgncp', 'Foreign countries'], ['rmunknwp', 'Residence unknown']]),
  )
  const stuFac = $derived(columns(R('efd'), [['stufacr', 'Students per faculty member']]))

  // ------------------------------------------------------------------ outcomes
  const retention = $derived(columns(R('efd'), [['ret_pcf', 'Full-time students'], ['ret_pcp', 'Part-time students']]))
  const gradRates = $derived(
    columns(R('drvgr'), [['grrttot', 'Completed within 150% of normal time (all)'], ['gba4rtt', "Bachelor's in 4 years"], ['gba5rtt', "Bachelor's in 5 years"], ['gba6rtt', "Bachelor's in 6 years"]]),
  )
  const COHORT: Record<number, string> = {
    1: 'Full-time, first-time', 2: 'Part-time, first-time', 3: 'Full-time, not first-time', 4: 'Part-time, not first-time',
  }
  const outcome8 = $derived.by((): TrendPoint[] => {
    const out: TrendPoint[] = []
    for (const r of R('om')) {
      const v = num(r.omawdp8)
      const k = COHORT[r.omchrt as number]
      if (k && v != null) out.push({ year: r.year as number, key: k, value: v })
    }
    return out.sort((a, b) => a.year - b.year)
  })

  // ------------------------------------------------------------------ cost and aid
  const tuitionSeries = $derived(tuition(R('icay')))
  const totalPrice = $derived.by((): TrendPoint[] => {
    const seen = new Set<number>()
    const out: TrendPoint[] = []
    for (const t of ['drvic', 'drvcost']) {
      for (const p of columns(R(t), [['cinson', 'In-state, living on campus'], ['cotson', 'Out-of-state, living on campus']])) {
        if (seen.has(p.year) && t === 'drvcost') continue
        out.push(p)
      }
      for (const r of R(t)) seen.add(r.year as number)
    }
    return out.sort((a, b) => a.year - b.year)
  })
  const netPrice = $derived(columns(R('sfa'), [['npist2', 'Average net price (students awarded aid)']]))
  const sfaNow = $derived(pickYear(R('sfa').filter((r) => netPriceByIncome(r).length)))
  const incomeBars = $derived(netPriceByIncome(sfaNow).map((d) => ({ label: d.label, value: d.value, text: `$${Math.round(d.value).toLocaleString()}` })))
  const aidShare = $derived(
    columns(R('sfa'), [['anyaidp', 'Any financial aid'], ['pgrnt_p', 'Pell grants'], ['fgrnt_p', 'Federal grants'], ['sgrnt_p', 'State or local grants'], ['igrnt_p', 'Institutional grants'], ['loan_p', 'Student loans']]),
  )
  const aidAmount = $derived(
    columns(R('sfa'), [['pgrnt_a', 'Pell grant'], ['igrnt_a', 'Institutional grant'], ['sgrnt_a', 'State or local grant'], ['loan_a', 'Student loan']]),
  )

  // ------------------------------------------------------------------ money and staff
  const revenuePct = $derived(financeSeries(R('drvf'), REVENUE_PARTS, 'pc'))
  const expensePerFte = $derived(financeSeries(R('drvf'), EXPENSE_PARTS, 'ft'))
  const STAFF: [string, string[]][] = [
    ['Instruction', ['sfteinst']],
    ['Research and public service', ['sftersrc', 'sftepbsv']],
    ['Student and academic affairs, libraries', ['sfteotis', 'sftelca']],
    ['Management and business operations', ['sftemngm', 'sftebfo']],
    ['Healthcare', ['sftehlth']],
    ['Service, maintenance and trades', ['sftesrvc', 'sftenrcm', 'sfteptmm']],
    ['Office and administrative support', ['sfteofas']],
    ['Technology, community, arts and sales', ['sfteces', 'sfteclam', 'sftesale']],
  ]
  const staffSeries = $derived(STAFF.flatMap(([label, cols]) => summed(R('drvhr'), cols, label)).filter((d) => (d.value ?? 0) > 0).sort((x, y) => x.year - y.year))

  const tabs: { id: Tab; label: string }[] = [
    { id: 'total', label: 'Total' }, { id: 'level', label: 'Level' }, { id: 'attend', label: 'Full/part-time' },
    { id: 'gender', label: 'Gender' }, { id: 'race', label: 'Race/ethnicity' },
  ]
  const caveat = (t: string, col = 'unitid') => dict.get(`ipeds.${t}.${col}`)?.caveat ?? ''
  const web = $derived(row?.webaddr ? String(row.webaddr) : (inst?.web ?? ''))

  const effyNow = $derived(effySeries.find((d) => d.year === app.year && d.key === 'All students')?.value ?? null)
  const awardsNow = $derived.by(() => {
    const rs = awardSeries.filter((d) => d.year === app.year)
    return rs.length ? rs.reduce((t, d) => t + (d.value ?? 0), 0) : null
  })
  const kpis = $derived([
    { label: 'Fall enrollment', value: enrollNow != null ? fmtInt(enrollNow) : null, sub: schoolYearLabel(app.year) },
    { label: '12-month headcount', value: effyNow != null ? fmtInt(effyNow) : null, sub: 'unduplicated' },
    { label: 'Awards conferred', value: awardsNow != null ? fmtInt(awardsNow) : null, sub: 'first majors' },
    { label: 'Online only', value: onlineNow != null ? pct1(onlineNow) : null, sub: 'of fall students', title: 'Share of fall students enrolled exclusively in distance education courses' },
  ])
  const views = [
    { id: 'overview', label: 'Overview' },
    { id: 'students', label: 'Students' },
    { id: 'outcomes', label: 'Outcomes' },
    { id: 'costs', label: 'Costs' },
    { id: 'details', label: 'Details' },
    { id: 'data', label: 'Data' },
  ]
  const tags = $derived(
    [row ? lab('control', row.control) : '', row ? lab('iclevel', row.iclevel) : '', row?.hbcu === 1 ? 'HBCU' : '', inst?.approx ? 'Approximate location' : '']
      .filter(Boolean)
      .map(String),
  )
  const modeTabs: { id: Mode; label: string }[] = [{ id: 'all', label: 'All students' }, { id: 'ug', label: 'Undergraduate' }, { id: 'grad', label: 'Graduate' }]
</script>

{#snippet empty(msg: string)}
  {#if !loading}<p class="muted">{msg}</p>{:else}<p class="muted">Loading…</p>{/if}
{/snippet}

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
        <section class="card span">
          <h3>How students take their courses <small>fall enrollment</small></h3>
          <div class="subtabs" role="group" aria-label="Student level">
            {#each modeTabs as t}
              <button class:on={mode === t.id} aria-pressed={mode === t.id} onclick={() => (mode = t.id)}>{t.label}</button>
            {/each}
            <button class:on={modeShare} aria-pressed={modeShare} onclick={() => (modeShare = !modeShare)}>% of students</button>
          </div>
          {#if has(fallMode)}
            <TrendChart mode="stack" percent={modeShare} data={fallMode} yLabel={modeShare ? '% of students' : 'Students'} currentYear={app.year} height={230} alt={`Fall students by online course load at ${inst.name}`} />
            <p class="note">
              “Online only” means enrolled exclusively in distance-education courses; “mix” means at least one, but not all. NCES does not report hybrid or in-person-only courses separately. Fall 2020 reflects emergency remote instruction.
              {#if app.year === 2020}<strong>Selected year: 2020.</strong>{/if}
            </p>
          {:else}
            {@render empty('No distance-education data for this view (reported from fall 2012).')}
          {/if}
        </section>
      {:else if view === 'students'}
        <section class="card span">
          <h3>Who enrolls <small>race and ethnicity, share of fall students</small></h3>
          {#if has(raceSeries)}
            <TrendChart mode="stack" percent data={raceSeries} yLabel="% of students" currentYear={app.year} height={240} alt={`Race and ethnicity share of fall enrollment at ${inst.name}`} />
            <p class="note">Categories were redefined in 2010, so earlier years are not shown. Descriptive only.</p>
          {:else}
            {@render empty('No race/ethnicity data.')}
          {/if}
        </section>
        <section class="card span">
          <h3>Admissions <small>first-time undergraduates</small></h3>
          {#if has(admSeries)}
            <TrendChart data={admSeries} yLabel="Students" currentYear={app.year} alt={`Applicants, admitted and enrolled at ${inst.name}`} height={210} />
            {#if has(admitRate)}<TrendChart data={admitRate} unit="%" yLabel="% of applicants" currentYear={app.year} alt={`Share of applicants admitted at ${inst.name}`} height={150} />{/if}
            <p class="note">{caveat('adm')} A share admitted describes who applies as much as the institution; it is not a quality measure.</p>
          {:else}
            {@render empty('No admissions data (open-admission institutions do not report it).')}
          {/if}
        </section>
        <section class="card span">
          <h3>Where first-time students live <small>% of first-time undergraduates</small></h3>
          {#if has(residence)}
            <TrendChart mode="stack" percent data={residence} yLabel="% of students" currentYear={app.year} height={190} alt={`Residence of first-time undergraduates at ${inst.name}`} />
          {:else}
            {@render empty('No residence data (reported in alternate years).')}
          {/if}
        </section>
        <section class="card">
          <h3>12-month headcount <small>students</small></h3>
          {#if effySeries.length}
            <TrendChart data={effySeries} currentYear={app.year} alt={`12-month enrollment at ${inst.name}`} height={200} />
          {:else}
            {@render empty('No 12-month enrollment data.')}
          {/if}
        </section>
        <section class="card">
          <h3>Students per faculty member <small>ratio</small></h3>
          {#if has(stuFac)}
            <TrendChart data={stuFac} yLabel="Students per faculty" currentYear={app.year} height={200} alt={`Student-to-faculty ratio at ${inst.name}`} />
            <p class="note">Full-time-equivalent students per full-time-equivalent instructional staff. A descriptive ratio, not a quality measure.</p>
          {:else}
            {@render empty('No ratio reported.')}
          {/if}
        </section>
        <section class="card span">
          <h3>Who works here <small>full-time-equivalent staff</small></h3>
          {#if has(staffSeries)}
            <TrendChart mode="stack" data={staffSeries} yLabel="FTE staff" currentYear={app.year} height={240} alt={`Staff by occupation at ${inst.name}`} />
          {:else}
            {@render empty('No staff data (reported from 2021).')}
          {/if}
        </section>
      {:else if view === 'outcomes'}
        <section class="card span">
          <h3>Staying enrolled <small>retention, % returning the next fall</small></h3>
          {#if has(retention)}
            <TrendChart data={retention} unit="%" yLabel="% retained" currentYear={app.year} height={210} alt={`Retention rates at ${inst.name}`} />
            <p class="note">Share of the prior fall’s first-time cohort who were enrolled again the following fall (or had completed).</p>
          {:else}
            {@render empty('No retention data.')}
          {/if}
        </section>
        <section class="card span">
          <h3>Completing a degree <small>graduation rates, first-time full-time students</small></h3>
          {#if has(gradRates)}
            <TrendChart data={gradRates} unit="%" yLabel="% of cohort" currentYear={app.year} height={230} alt={`Graduation rates at ${inst.name}`} />
            <p class="note">Covers only first-time, full-time students who start in the fall, so it can leave out many part-time and transfer students. Derived rates are available from 2021.</p>
          {:else}
            {@render empty('No graduation-rate data.')}
          {/if}
        </section>
        <section class="card span">
          <h3>Awards within 8 years <small>Outcome Measures, % of each entering group</small></h3>
          {#if has(outcome8)}
            <TrendChart data={outcome8} unit="%" yLabel="% earning an award" currentYear={app.year} height={230} alt={`Share receiving an award within 8 years at ${inst.name}`} />
            <p class="note">Outcome Measures include part-time and transfer-in students too. Groups differ widely in size and are reported separately; compare like with like.</p>
          {:else}
            {@render empty('No Outcome Measures data (reported from 2015).')}
          {/if}
        </section>
        <section class="card span">
          <h3>Awards conferred <small>completions</small></h3>
          {#if awardSeries.length}
            <TrendChart mode="stack" data={awardSeries} yLabel="Awards" currentYear={app.year} alt={`Awards conferred at ${inst.name}`} height={220} />
            <p class="note">First majors only; 2008 onward in this chart (older years are in the data tables).</p>
          {:else}
            {@render empty('No completions data.')}
          {/if}
        </section>
      {:else if view === 'costs'}
        <section class="card span">
          <h3>Published tuition and fees <small>per academic year, dollars</small></h3>
          {#if has(tuitionSeries)}
            <TrendChart data={tuitionSeries} unit="$" yLabel="Dollars" currentYear={app.year} height={220} alt={`Published tuition and fees at ${inst.name}`} />
            <p class="note">Sticker prices for full-time undergraduates, before any aid. Not what most students pay.</p>
          {:else}
            {@render empty('No tuition data.')}
          {/if}
        </section>
        <section class="card span">
          <h3>Total price for a year on campus <small>tuition, fees, housing, books, other costs</small></h3>
          {#if has(totalPrice)}
            <TrendChart data={totalPrice} unit="$" yLabel="Dollars" currentYear={app.year} height={210} alt={`Total price of attendance at ${inst.name}`} />
          {:else}
            {@render empty('No total-price data (reported from 2021).')}
          {/if}
        </section>
        <section class="card span">
          <h3>What students pay after aid <small>average net price</small></h3>
          {#if has(netPrice)}
            <TrendChart data={netPrice} unit="$" yLabel="Dollars" currentYear={app.year} height={190} alt={`Average net price at ${inst.name}`} />
          {/if}
          {#if incomeBars.length}
            <p class="barhead">By family income, {sfaNow ? schoolYearLabel(Number(sfaNow.year)) : ''} <small>students awarded federal aid</small></p>
            <BarList items={incomeBars} label={`Average net price by family income at ${inst.name}`} />
          {/if}
          {#if !has(netPrice) && !incomeBars.length}
            {@render empty('No net price data reported (not every institution reports it).')}
          {:else}
            <p class="note">Net price is cost of attendance minus grants and scholarships, for first-time, full-time undergraduates paying in-state or in-district rates.</p>
          {/if}
        </section>
        <section class="card span">
          <h3>Who receives aid <small>% of first-time, full-time undergraduates</small></h3>
          {#if has(aidShare)}
            <TrendChart data={aidShare} unit="%" yLabel="% awarded" currentYear={app.year} height={240} alt={`Share of first-time students receiving financial aid at ${inst.name}`} />
          {:else}
            {@render empty('No financial aid data.')}
          {/if}
        </section>
        <section class="card span">
          <h3>Average aid amounts <small>dollars per recipient</small></h3>
          {#if has(aidAmount)}
            <TrendChart data={aidAmount} unit="$" yLabel="Dollars" currentYear={app.year} height={220} alt={`Average aid amounts at ${inst.name}`} />
          {:else}
            {@render empty('No aid amount data.')}
          {/if}
        </section>
        <section class="card span">
          <h3>Where the money comes from <small>% of core revenues</small></h3>
          {#if has(revenuePct)}
            <TrendChart mode="stack" percent data={revenuePct} yLabel="% of revenue" currentYear={app.year} height={230} alt={`Sources of core revenue at ${inst.name}`} />
          {:else}
            {@render empty('No finance data (reported from 2021).')}
          {/if}
        </section>
        <section class="card span">
          <h3>Where it is spent <small>core expenses per full-time-equivalent student</small></h3>
          {#if has(expensePerFte)}
            <TrendChart mode="stack" unit="$" data={expensePerFte} yLabel="Dollars per FTE" currentYear={app.year} height={230} alt={`Core expenses per FTE student at ${inst.name}`} />
            <p class="note">Public, private nonprofit and for-profit institutions follow different accounting standards, so compare across types with care.</p>
          {:else}
            {@render empty('No expense data.')}
          {/if}
        </section>
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

<style>
  .barhead {
    margin: 12px 0 8px;
    font-size: 12px;
    color: var(--text);
  }
  .barhead small {
    color: var(--muted);
  }
</style>
