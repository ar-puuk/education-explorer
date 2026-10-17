<script lang="ts">
  import * as Plot from '@observablehq/plot'
  import { paletteFor } from '../lib/palette'
  import { theme } from '../lib/theme.svelte'

  import type { TrendPoint as Point } from '../lib/types'

  let {
    data,
    yLabel = 'Students',
    currentYear,
    height = 220,
    alt,
    mode = 'line',
    reference,
    unit = '',
    percent = false,
  }: {
    data: Point[]
    yLabel?: string
    currentYear?: number
    height?: number
    alt: string
    mode?: 'line' | 'heat' | 'stack'
    /** value prefix/suffix in tooltips and on the axis */
    unit?: '' | '%' | '$'
    /** stack mode: normalise each year to 100% */
    percent?: boolean
    /** state median (dashed line) and middle-half band for context; years need not match the data */
    reference?: { year: number; value: number; lo: number; hi: number }[]
  } = $props()

  let el: HTMLDivElement
  let width = $state(380)

  const fmt = (v: number | null | undefined) =>
    v == null ? '' : unit === '$' ? `$${Math.round(v).toLocaleString()}` : unit === '%' ? `${Math.round(v * 10) / 10}%` : v.toLocaleString()
  const compact = new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 1 })
  /** y-axis tick text: large dollar amounts are abbreviated so they never clip; tooltips keep the full value */
  const axis = (d: number) => (unit === '$' ? `$${Math.abs(d) >= 10000 ? compact.format(d) : d.toLocaleString()}` : unit === '%' ? `${d}%` : Math.abs(d) >= 1e6 ? compact.format(d) : d.toLocaleString())
  const css = (v: string) => getComputedStyle(document.documentElement).getPropertyValue(v).trim()

  $effect(() => {
    theme.effective // re-render on theme change
    const w = width
    const keys = [...new Set(data.map((d) => d.key))]
    const present = data.filter((d) => d.value != null)
    const years = [...new Set(data.map((d) => d.year))]
    // the reference only covers the years the chart shows, so it never stretches the axis
    const ref = reference?.filter((r) => years.length && r.year >= Math.min(...years) && r.year <= Math.max(...years))
    let chart: ReturnType<typeof Plot.plot>
    if (mode === 'heat') {
      const rows = keys.filter((k) => present.some((d) => d.key === k && (d.value ?? 0) > 0))
      const cells = present.filter((d) => rows.includes(d.key))
      chart = Plot.plot({
        width: w,
        height: Math.max(120, rows.length * 20 + 50),
        marginLeft: 92,
        style: { background: 'transparent', color: css('--text'), fontSize: '11px' },
        x: { tickFormat: (d: number) => `’${String(d).slice(2)}`, label: null, domain: years, padding: 0.05, ticks: years.filter((_, i) => i % 2 === 0) },
        y: { domain: rows, label: null, padding: 0.1 },
        color: { type: 'sqrt', scheme: 'viridis', legend: false },
        marks: [
          Plot.cell(cells, { x: 'year', y: 'key', fill: 'value', inset: 0.5 }),
          Plot.tip(cells, Plot.pointer({ x: 'year', y: 'key', fill: css('--surface'), stroke: css('--border'), title: (d: Point) => `${d.key}
${d.year}: ${d.value?.toLocaleString()}` })),
        ],
      })
    } else if (mode === 'stack') {
      const palette = paletteFor(keys, css)
      const yrs = [...new Set(present.map((d) => d.year))].sort((a, b) => a - b)
      const every = Math.max(1, Math.ceil(yrs.length / Math.max(2, Math.floor((w - 60) / 38))))
      const stack = { offset: percent ? ('normalize' as const) : undefined, order: keys }
      const tipText = (d: Point) => `${d.key}\n${d.year}: ${fmt(d.value)}`
      chart = Plot.plot({
        width: w,
        height,
        marginLeft: 48,
        style: { background: 'transparent', color: css('--text'), fontSize: '11px' },
        x: { type: 'band', domain: yrs, label: null, padding: 0.18, tickFormat: (d: number) => (yrs.indexOf(d) % every === 0 ? String(d) : '') },
        y: { grid: true, label: yLabel, nice: true, percent, tickFormat: percent ? undefined : axis },
        color: { domain: keys, range: palette, legend: keys.length > 1 },
        marks: [
          Plot.barY(present, Plot.stackY(stack, { x: 'year', y: 'value', z: 'key', fill: 'key' })),
          Plot.ruleY([0]),
          Plot.tip(present, Plot.pointerX(Plot.stackY(stack, { x: 'year', y: 'value', z: 'key', fill: css('--surface'), stroke: css('--border'), title: tipText }))),
        ],
      })
    } else {
      const palette = paletteFor(keys, css)
      chart = Plot.plot({
        width: w,
        height,
        marginLeft: 48,
        style: { background: 'transparent', color: css('--text'), fontSize: '11px' },
        x: { tickFormat: 'd', label: null, ticks: years.filter((_, i) => i % Math.max(1, Math.ceil(years.length / Math.max(2, Math.floor((w - 60) / 40)))) === 0) },
        y: { grid: true, label: yLabel, nice: true, zero: true, tickFormat: axis },
        color: { domain: keys, range: palette, legend: keys.length > 1 },
        marks: [
          Plot.ruleY([0]),
          ref?.length ? Plot.areaY(ref, { x: 'year', y1: 'lo', y2: 'hi', fill: css('--muted'), fillOpacity: 0.14 }) : null,
          ref?.length ? Plot.lineY(ref, { x: 'year', y: 'value', stroke: css('--muted'), strokeDasharray: '5,4', strokeWidth: 1.5 }) : null,
          currentYear ? Plot.ruleX([currentYear], { stroke: css('--muted'), strokeDasharray: '3,3' }) : null,
          Plot.lineY(present, { x: 'year', y: 'value', stroke: 'key', strokeWidth: 2 }),
          Plot.dot(present, { x: 'year', y: 'value', stroke: 'key', fill: 'key', r: 3 }),
          Plot.tip(present, Plot.pointer({ x: 'year', y: 'value', fill: css('--surface'), stroke: css('--border'), title: (d: Point) => `${d.key}
${d.year}: ${fmt(d.value)}` })),
        ].filter(Boolean) as Plot.Markish[],
      })
    }
    // Plot labels its internal groups; inside an img role those labels are invalid ARIA, so drop them.
    chart.querySelectorAll('svg [aria-label], svg [aria-description]').forEach((el) => {
      el.removeAttribute('aria-label')
      el.removeAttribute('aria-description')
    })
    const svg = chart.tagName.toLowerCase() === 'svg' ? chart : chart.querySelector('svg')
    svg?.setAttribute('role', 'img')
    svg?.setAttribute('aria-label', alt)
    el.replaceChildren(chart)
    return () => chart.remove()
  })
</script>

<div class="chart" bind:this={el} bind:clientWidth={width}></div>

<style>
  .chart {
    width: 100%;
    min-height: 120px;
  }
  .chart :global(figure) {
    margin: 0;
  }
  .chart :global([aria-label='swatches']) {
    font-size: 11px;
  }
</style>
