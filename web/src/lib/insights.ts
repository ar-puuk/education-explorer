// Pure helpers that turn table rows into chart series. No DOM, no network, so they are unit-tested.
import type { Row } from './db'
import type { TrendPoint } from './types'

/** Number from a parquet cell. IPEDS derived tables store many numbers as text, with "." or flag letters for missing. */
export function n(v: unknown): number | null {
  if (v == null) return null
  if (typeof v === 'number') return Number.isFinite(v) ? v : null
  if (typeof v === 'bigint') return Number(v)
  const t = String(v).trim().replace(/,/g, '')
  if (!t || t === '.' || !/^-?\d*\.?\d+$/.test(t)) return null
  return Number(t)
}

const sortYear = (a: TrendPoint, b: TrendPoint) => a.year - b.year

/** One point per (year, column) from rows that carry a `year`; missing values are dropped. */
export function columns(rows: Row[], cols: [string, string][], scale = 1): TrendPoint[] {
  const out: TrendPoint[] = []
  for (const r of rows) {
    for (const [col, key] of cols) {
      const v = n(r[col])
      if (v != null) out.push({ year: r.year as number, key, value: scale === 1 ? v : Math.round(v * scale * 100) / 100 })
    }
  }
  return out.sort(sortYear)
}

/** Sum of several columns per row (null when none is present). */
export function summed(rows: Row[], cols: string[], key: string): TrendPoint[] {
  const out: TrendPoint[] = []
  for (const r of rows) {
    const vs = cols.map((c) => n(r[c])).filter((x): x is number => x != null)
    if (vs.length) out.push({ year: r.year as number, key, value: vs.reduce((a, b) => a + b, 0) })
  }
  return out.sort(sortYear)
}

/** The points of the year closest to `year` (that year, else the latest earlier one, else the first year). */
export function atYear(points: TrendPoint[], year: number): { year: number; items: TrendPoint[] } | null {
  const ys = [...new Set(points.filter((p) => p.value != null).map((p) => p.year))].sort((a, b) => a - b)
  if (!ys.length) return null
  const y = ys.includes(year) ? year : ([...ys].reverse().find((v) => v < year) ?? ys[0])
  return { year: y, items: points.filter((p) => p.year === y && p.value != null) }
}

/** Fall enrollment by how much of it is online (IPEDS distance-education counts). */
export const MODE_LABELS = { none: 'In person only', som: 'Mix of in person and online', exc: 'Online only' } as const
export function learningMode(rows: Row[], levelCol: string, level: number, cols: { none: string; som: string; exc: string }): TrendPoint[] {
  const out: TrendPoint[] = []
  for (const r of rows) {
    if (r[levelCol] !== level) continue
    const vals = { none: n(r[cols.none]), som: n(r[cols.som]), exc: n(r[cols.exc]) }
    if (vals.none == null && vals.som == null && vals.exc == null) continue
    for (const k of ['none', 'som', 'exc'] as const) out.push({ year: r.year as number, key: MODE_LABELS[k], value: vals[k] ?? 0 })
  }
  return out.sort(sortYear)
}

/** Share (0-100) of the total held by one key, per year. */
export function shareOf(points: TrendPoint[], key: string): { year: number; value: number }[] {
  const byYear = new Map<number, { tot: number; mine: number }>()
  for (const p of points) {
    if (p.value == null) continue
    const e = byYear.get(p.year) ?? { tot: 0, mine: 0 }
    e.tot += p.value
    if (p.key === key) e.mine += p.value
    byYear.set(p.year, e)
  }
  return [...byYear].filter(([, e]) => e.tot > 0).map(([year, e]) => ({ year, value: Math.round((e.mine / e.tot) * 1000) / 10 })).sort((a, b) => a.year - b.year)
}

/** Published tuition + required fees (dollars), when both parts are present. */
export function tuition(rows: Row[]): TrendPoint[] {
  const out: TrendPoint[] = []
  for (const r of rows) {
    for (const [t, f, key] of [
      ['tuition2', 'fee2', 'In-state undergraduate'],
      ['tuition3', 'fee3', 'Out-of-state undergraduate'],
    ] as const) {
      const tu = n(r[t])
      if (tu == null) continue
      out.push({ year: r.year as number, key, value: tu + (n(r[f]) ?? 0) })
    }
  }
  return out.sort(sortYear)
}

export const INCOME_BANDS = ['$0–30,000', '$30,001–48,000', '$48,001–75,000', '$75,001–110,000', 'Over $110,000']
/** Average net price by family income for one financial-aid row (public columns npis4x2, private npt4x2). */
export function netPriceByIncome(r: Row | undefined): { label: string; value: number }[] {
  if (!r) return []
  const out: { label: string; value: number }[] = []
  INCOME_BANDS.forEach((label, i) => {
    const v = n(r[`npis4${i + 1}2`]) ?? n(r[`npt4${i + 1}2`])
    if (v != null) out.push({ label, value: v })
  })
  return out
}

/** Pick the finance form (1 public/GASB, 2 private nonprofit/FASB, 3 for-profit) a row actually reports. */
export function financeForm(r: Row): 1 | 2 | 3 | null {
  for (const f of [1, 2, 3] as const) if (n(r[`f${f}correv`]) != null || n(r[`f${f}corexp`]) != null) return f
  return null
}
export function financeSeries(rows: Row[], parts: [string, string][], per: 'ft' | 'pc'): TrendPoint[] {
  const out: TrendPoint[] = []
  for (const r of rows) {
    const f = financeForm(r)
    if (!f) continue
    for (const [stem, key] of parts) {
      const v = n(r[`f${f}${stem}${per}`])
      if (v != null) out.push({ year: r.year as number, key, value: v })
    }
  }
  return out.sort(sortYear)
}
export const REVENUE_PARTS: [string, string][] = [
  ['tufe', 'Tuition and fees'], ['stap', 'State appropriations'], ['lcap', 'Local appropriations'], ['gvgc', 'Government grants and contracts'],
  ['pggc', 'Private gifts, grants and contracts'], ['invr', 'Investment return'], ['otrv', 'Other'],
]
export const EXPENSE_PARTS: [string, string][] = [
  ['inst', 'Instruction'], ['rsrc', 'Research'], ['pbsv', 'Public service'], ['acsp', 'Academic support'], ['stsv', 'Student services'],
  ['insu', 'Institutional support'], ['otex', 'All other'],
]

/** Group raw rows into composition counts: one point per (year, key), summing duplicates. */
export function tally<T extends { year: number }>(rows: T[], keyOf: (r: T) => string | null, valOf: (r: T) => number | null): TrendPoint[] {
  const m = new Map<string, { year: number; key: string; value: number | null }>()
  for (const r of rows) {
    const key = keyOf(r)
    if (key == null) continue
    const id = `${r.year}|${key}`
    const v = valOf(r)
    const e = m.get(id)
    if (!e) m.set(id, { year: r.year, key, value: v })
    else if (v != null) e.value = (e.value ?? 0) + v
  }
  return [...m.values()].sort(sortYear)
}

/** Rows grouped by `rowKey` (e.g. grade) with the amount in each `segKey` (e.g. race), for the year nearest `year`. */
export function withinGroups<T extends { year: number }>(
  rows: T[], year: number, rowKey: (r: T) => string, segKey: (r: T) => string, valOf: (r: T) => number | null,
): { year: number; groups: { group: string; total: number; segs: { key: string; value: number }[] }[] } | null {
  const ys = [...new Set(rows.filter((r) => valOf(r) != null).map((r) => r.year))].sort((a, b) => a - b)
  if (!ys.length) return null
  const y = ys.includes(year) ? year : ([...ys].reverse().find((v) => v < year) ?? ys[0])
  const m = new Map<string, Map<string, number>>()
  for (const r of rows) {
    if (r.year !== y) continue
    const v = valOf(r)
    if (v == null) continue
    const g = rowKey(r)
    const e = m.get(g) ?? new Map<string, number>()
    e.set(segKey(r), (e.get(segKey(r)) ?? 0) + v)
    m.set(g, e)
  }
  const groups = [...m]
    .map(([group, segs]) => ({ group, total: [...segs.values()].reduce((a, b) => a + b, 0), segs: [...segs].map(([key, value]) => ({ key, value })) }))
    .filter((g) => g.total > 0)
  return groups.length ? { year: y, groups } : null
}

/** Round a percentage for display. */
export const pct1 = (v: number) => `${Math.round(v * 10) / 10}%`
