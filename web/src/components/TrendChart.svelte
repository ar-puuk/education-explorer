<script lang="ts">
  import * as Plot from '@observablehq/plot'
  import { theme } from '../lib/theme.svelte'

  import type { TrendPoint as Point } from '../lib/types'

  let {
    data,
    yLabel = 'Students',
    currentYear,
    height = 220,
    alt,
    mode = 'line',
  }: { data: Point[]; yLabel?: string; currentYear?: number; height?: number; alt: string; mode?: 'line' | 'heat' } = $props()

  let el: HTMLDivElement
  let width = $state(380)

  const css = (v: string) => getComputedStyle(document.documentElement).getPropertyValue(v).trim()

  $effect(() => {
    theme.effective // re-render on theme change
    const w = width
    const keys = [...new Set(data.map((d) => d.key))]
    const present = data.filter((d) => d.value != null)
    const years = [...new Set(data.map((d) => d.year))]
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
    } else {
      const palette = keys.map((_, i) => css(`--chart-${(i % 8) + 1}`))
      chart = Plot.plot({
        width: w,
        height,
        marginLeft: 48,
        style: { background: 'transparent', color: css('--text'), fontSize: '11px' },
        x: { tickFormat: 'd', label: null, ticks: years.filter((_, i) => i % 2 === 0) },
        y: { grid: true, label: yLabel, nice: true, zero: true },
        color: { domain: keys, range: palette, legend: keys.length > 1 },
        marks: [
          Plot.ruleY([0]),
          currentYear ? Plot.ruleX([currentYear], { stroke: css('--muted'), strokeDasharray: '3,3' }) : null,
          Plot.lineY(present, { x: 'year', y: 'value', stroke: 'key', strokeWidth: 2 }),
          Plot.dot(present, { x: 'year', y: 'value', stroke: 'key', fill: 'key', r: 3 }),
          Plot.tip(present, Plot.pointer({ x: 'year', y: 'value', fill: css('--surface'), stroke: css('--border'), title: (d: Point) => `${d.key}
${d.year}: ${d.value?.toLocaleString()}` })),
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
