import type { Row } from './db'
import type { DictEntry } from './types'

export interface ExploreContext {
  dataset: string
  table: string
  dict: Map<string, DictEntry>
  labels: Map<string, string>
}

/** Numeric columns that are identifiers/codes, shown without thousands separators. */
const CODELIKE = /tele|phone|zip|fips|opeid|^ein$|ueis|cbsa|csa|county|^cd$|necta|sector|control|level|code|^year$|id$|^unitid/i

export const HIDDEN_COLUMNS = new Set(['year', 'data_version', 'source_file', 'unitid'])

export const isFlag = (c: string) => c.endsWith('_flag')

export const colLabel = (ctx: ExploreContext, c: string) => ctx.dict.get(`${ctx.dataset}.${ctx.table}.${c}`)?.label ?? c
export const colDesc = (ctx: ExploreContext, c: string) => ctx.dict.get(`${ctx.dataset}.${ctx.table}.${c}`)?.description ?? ''

/** Display text for a value: code columns show their label when the dictionary has one. */
export function cellText(ctx: ExploreContext, col: string, v: unknown): string {
  if (v == null || v === '') return ''
  const lab = ctx.labels.get(`${ctx.dataset}.${ctx.table}.${col}|${String(v)}`)
  if (lab) return lab
  if (typeof v === 'number' && CODELIKE.test(col)) return String(v)
  if (typeof v === 'number') return Number.isInteger(v) ? v.toLocaleString('en-US') : v.toLocaleString('en-US', { maximumFractionDigits: 4 })
  if (v instanceof Date) return v.toISOString().slice(0, 10)
  return String(v)
}

export function dataColumns(rows: Row[]): string[] {
  const seen = new Set<string>()
  const out: string[] = []
  for (const r of rows) {
    for (const [k, v] of Object.entries(r)) {
      if (HIDDEN_COLUMNS.has(k) || isFlag(k) || seen.has(k) || v == null || v === '') continue
      seen.add(k)
      out.push(k)
    }
  }
  return out
}

/** True when any year has more than one row for the institution (needs a table view, not a pivot). */
export function isMultiRow(rows: Row[]): boolean {
  const n = new Map<unknown, number>()
  for (const r of rows) n.set(r.year, (n.get(r.year) ?? 0) + 1)
  return [...n.values()].some((c) => c > 1)
}

export interface PivotRow {
  column: string
  label: string
  cells: { year: number; text: string; raw: unknown; flag: string }[]
}

export function pivot(ctx: ExploreContext, rows: Row[], filter = ''): { years: number[]; rows: PivotRow[] } {
  const years = [...new Set(rows.map((r) => r.year as number))].sort((a, b) => a - b)
  const cols = dataColumns(rows)
  const f = filter.trim().toLowerCase()
  const out: PivotRow[] = []
  for (const c of cols) {
    const label = colLabel(ctx, c)
    if (f && !label.toLowerCase().includes(f) && !c.includes(f)) continue
    out.push({
      column: c,
      label,
      cells: years.map((y) => {
        const r = rows.find((x) => x.year === y)
        return { year: y, text: r ? cellText(ctx, c, r[c]) : '', raw: r?.[c] ?? null, flag: r ? String(r[`${c}_flag`] ?? '') : '' }
      }),
    })
  }
  return { years, rows: out }
}

export function toCsv(header: string[], lines: (string | number | null)[][]): string {
  const esc = (v: string | number | null) => {
    const s = v == null ? '' : String(v)
    return /[",\n\r]/.test(s) ? `"${s.replaceAll('"', '""')}"` : s
  }
  return [header, ...lines].map((r) => r.map(esc).join(',')).join('\r\n') + '\r\n'
}

export function download(name: string, text: string) {
  const url = URL.createObjectURL(new Blob([text], { type: 'text/csv;charset=utf-8' }))
  const a = document.createElement('a')
  a.href = url
  a.download = name
  a.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
