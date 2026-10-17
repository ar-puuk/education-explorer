// College-specific series builders (age, origin, faculty, finance history). Pure functions, unit-tested.
import type { Row } from './db'
import { n } from './insights'
import type { TrendPoint } from './types'

const sortYear = (a: TrendPoint, b: TrendPoint) => a.year - b.year

// ---------------------------------------------------------------------- age and origin
export const AGE_BANDS: [number, string][] = [
  [3, 'Under 18'], [4, '18–19'], [5, '20–21'], [6, '22–24'], [8, '25–29'], [9, '30–34'], [10, '35–39'], [11, '40–49'], [12, '50–64'], [13, '65 and over'],
]

/** Fall enrollment by age band (IPEDS EF-B, grand total of full- and part-time). `lstudy`: 1 all students, 2 undergraduate, 5 graduate. */
export function ageMix(rows: Row[], lstudy: number): TrendPoint[] {
  const out: TrendPoint[] = []
  for (const r of rows) {
    if (r.lstudy !== lstudy || (r.year as number) < 2003) continue
    const band = AGE_BANDS.find(([code]) => code === r.efbage)
    const v = n(r.efage09)
    if (band && v != null) out.push({ year: r.year as number, key: band[1], value: v })
  }
  return out.sort(sortYear)
}

/**
 * Where first-time students came from in one year: the largest origins, then the rest grouped.
 * Lines below 90 are states, 90 foreign countries, 98 not reported, 99 the total.
 */
export function originBars(
  rows: Row[], year: number, nameOf: (line: number) => string, top = 8,
): { year: number; items: { label: string; value: number }[] } | null {
  const usable = rows.filter((r) => n(r.efres01) != null && (r.line as number) !== 99)
  const ys = [...new Set(usable.map((r) => r.year as number))].sort((a, b) => a - b)
  if (!ys.length) return null
  const y = ys.includes(year) ? year : ([...ys].reverse().find((v) => v < year) ?? ys[0])
  const at = usable.filter((r) => r.year === y)
  const states = at.filter((r) => (r.line as number) < 90 && (n(r.efres01) ?? 0) > 0).sort((a, b) => (n(b.efres01) as number) - (n(a.efres01) as number))
  const items = states.slice(0, top).map((r) => ({ label: nameOf(r.line as number), value: n(r.efres01) as number }))
  const rest = states.slice(top).reduce((t, r) => t + (n(r.efres01) as number), 0)
  const territories = at.filter((r) => (r.line as number) === 89).reduce((t, r) => t + (n(r.efres01) as number), 0)
  if (rest + territories > 0) items.push({ label: 'All other states and territories', value: rest + territories })
  for (const [line, label] of [[90, 'Foreign countries'], [98, 'Residence not reported']] as const) {
    const v = at.filter((r) => r.line === line).reduce((t, r) => t + (n(r.efres01) ?? 0), 0)
    if (v > 0) items.push({ label, value: v })
  }
  return items.length ? { year: y, items } : null
}

// ---------------------------------------------------------------------- faculty
export const RANKS: [number, string, string][] = [
  [1, 'Professor', 'salprof'], [2, 'Associate professor', 'salassc'], [3, 'Assistant professor', 'salasst'],
  [4, 'Instructor', 'salinst'], [5, 'Lecturer', 'sallect'], [6, 'No academic rank', 'salnrnk'],
]

/** Instructional staff headcount by academic rank (IPEDS Salaries, 2012 onward). */
export function staffByRank(rows: Row[]): TrendPoint[] {
  const out: TrendPoint[] = []
  for (const r of rows) {
    const rank = RANKS.find(([c]) => c === r.arank)
    const v = n(r.satotlt)
    if (rank && v != null && v > 0) out.push({ year: r.year as number, key: rank[1], value: v })
  }
  return out.sort(sortYear)
}

/**
 * Average salary equated to 9 months, by rank. From 2021 these are NCES's derived values (drvhr). Earlier files that
 * report an average monthly salary give monthly x 9; the 2016-2020 files report only outlays and are left out.
 */
export function salaryByRank(derived: Row[], salaries: Row[]): TrendPoint[] {
  const out: TrendPoint[] = []
  const have = new Set<string>()
  for (const r of derived) {
    for (const [, label, col] of RANKS) {
      const v = n(r[col])
      if (v != null && v > 0) {
        out.push({ year: r.year as number, key: label, value: v })
        have.add(`${r.year}|${label}`)
      }
    }
  }
  for (const r of salaries) {
    const rank = RANKS.find(([c]) => c === r.arank)
    const m = n(r.saavmnt)
    if (rank && m != null && m > 0 && !have.has(`${r.year}|${rank[1]}`)) out.push({ year: r.year as number, key: rank[1], value: Math.round(m * 9) })
  }
  return out.sort(sortYear)
}

// ---------------------------------------------------------------------- finance history (dollars, every reporting year)
const sumCols = (r: Row, cols: string[]): number | null => {
  const vs = cols.map((c) => n(r[c])).filter((x): x is number => x != null)
  return vs.length ? vs.reduce((a, b) => a + b, 0) : null
}
interface Form {
  revenue: [string, string[]][]
  revenueTotal: string
  expense: [string, string[]][]
  expenseTotal: string
}
const FORMS: Record<'public' | 'nonprofit' | 'forprofit', Form> = {
  public: {
    revenue: [
      ['Tuition and fees', ['f1b01']],
      ['Government appropriations, grants and contracts', ['f1b02', 'f1b03', 'f1b10', 'f1b11', 'f1b12', 'f1b13', 'f1b14', 'f1b15']],
      ['Private gifts, grants and contracts', ['f1b04', 'f1b16']],
      ['Investment income', ['f1b17']],
      ['Auxiliary, hospital and other sales', ['f1b05', 'f1b06', 'f1b07', 'f1b26']],
    ],
    revenueTotal: 'f1b25',
    expense: [
      ['Instruction', ['f1c011']],
      ['Research and public service', ['f1c021', 'f1c031']],
      ['Academic, student and institutional support', ['f1c051', 'f1c061', 'f1c071']],
      ['Auxiliary, hospital and independent operations', ['f1c111', 'f1c121', 'f1c131']],
      ['Scholarships and fellowships', ['f1c101']],
    ],
    expenseTotal: 'f1c191',
  },
  nonprofit: {
    revenue: [
      ['Tuition and fees', ['f2d01']],
      ['Government appropriations, grants and contracts', ['f2d02', 'f2d03', 'f2d04', 'f2d05', 'f2d06', 'f2d07']],
      ['Private gifts, grants and contracts', ['f2d08', 'f2d09']],
      ['Investment income', ['f2d10']],
      ['Auxiliary, hospital and other sales', ['f2d11', 'f2d12', 'f2d13', 'f2d14']],
    ],
    revenueTotal: 'f2d16',
    expense: [
      ['Instruction', ['f2e011']],
      ['Research and public service', ['f2e021', 'f2e031']],
      ['Academic, student and institutional support', ['f2e041', 'f2e051', 'f2e061']],
      ['Auxiliary, hospital and independent operations', ['f2e071', 'f2e091', 'f2e101']],
      ['Scholarships and fellowships', ['f2e081']],
    ],
    expenseTotal: 'f2e131',
  },
  forprofit: {
    revenue: [
      ['Tuition and fees', ['f3d01']],
      ['Government appropriations, grants and contracts', ['f3d02', 'f3d03']],
      ['Private gifts, grants and contracts', ['f3d04']],
      ['Investment income', ['f3d05']],
      ['Auxiliary, hospital and other sales', ['f3d06', 'f3d07']],
    ],
    revenueTotal: 'f3d09',
    expense: [
      ['Instruction', ['f3e01']],
      ['Research and public service', ['f3e02']],
      ['Academic, student and institutional support', ['f3e03']],
      ['Auxiliary, hospital and independent operations', ['f3e04']],
      ['Scholarships and fellowships', ['f3e05']],
    ],
    expenseTotal: 'f3e07',
  },
}

/** Revenue by source and expenses by purpose in dollars, from whichever finance form (public, nonprofit, for-profit) was filed each year. */
export function financeHistory(tables: { public: Row[]; nonprofit: Row[]; forprofit: Row[] }): { revenue: TrendPoint[]; expense: TrendPoint[] } {
  const revenue: TrendPoint[] = []
  const expense: TrendPoint[] = []
  for (const kind of ['public', 'nonprofit', 'forprofit'] as const) {
    const f = FORMS[kind]
    for (const r of tables[kind]) {
      const y = r.year as number
      const parts = f.revenue.map(([key, cols]) => [key, sumCols(r, cols)] as const)
      if (parts.some(([, v]) => v != null)) {
        for (const [key, v] of parts) if (v != null && v > 0) revenue.push({ year: y, key, value: v })
        const total = n(r[f.revenueTotal])
        const rest = total != null ? total - parts.reduce((t, [, v]) => t + (v ?? 0), 0) : 0
        if (rest > 0) revenue.push({ year: y, key: 'Other', value: rest })
      }
      const eparts = f.expense.map(([key, cols]) => [key, sumCols(r, cols)] as const)
      if (eparts.some(([, v]) => v != null)) {
        for (const [key, v] of eparts) if (v != null && v > 0) expense.push({ year: y, key, value: v })
        const total = n(r[f.expenseTotal])
        const rest = total != null ? total - eparts.reduce((t, [, v]) => t + (v ?? 0), 0) : 0
        if (rest > 0) expense.push({ year: y, key: 'Other (plant, depreciation, other)', value: rest })
      }
    }
  }
  return { revenue: revenue.sort(sortYear), expense: expense.sort(sortYear) }
}
