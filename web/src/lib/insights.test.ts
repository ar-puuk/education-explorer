import { describe, expect, it } from 'vitest'
import { atYear, columns, financeSeries, learningMode, n, netPriceByIncome, REVENUE_PARTS, shareOf, tally, tuition } from './insights'

describe('n', () => {
  it('reads numbers, numeric text and treats flags as missing', () => {
    expect(n(5)).toBe(5)
    expect(n('87')).toBe(87)
    expect(n('1,234.5')).toBe(1234.5)
    expect(n('.')).toBeNull()
    expect(n('R')).toBeNull()
    expect(n(null)).toBeNull()
    expect(n(7n)).toBe(7)
  })
})

describe('series builders', () => {
  it('drops missing cells instead of plotting zero', () => {
    const pts = columns([{ year: 2021, a: '10', b: '.' }, { year: 2022, a: null, b: 4 }], [['a', 'A'], ['b', 'B']])
    expect(pts).toEqual([{ year: 2021, key: 'A', value: 10 }, { year: 2022, key: 'B', value: 4 }])
  })
  it('maps distance-education counts to three modes and skips empty rows', () => {
    const rows = [{ year: 2020, lev: 1, a: 10, b: 20, c: 70 }, { year: 2021, lev: 1, a: null, b: null, c: null }, { year: 2020, lev: 2, a: 1, b: 1, c: 1 }]
    const pts = learningMode(rows, 'lev', 1, { none: 'a', som: 'b', exc: 'c' })
    expect(pts).toHaveLength(3)
    expect(shareOf(pts, 'Online only')).toEqual([{ year: 2020, value: 70 }])
  })
  it('adds tuition and fees, and needs the tuition part', () => {
    const pts = tuition([{ year: 2023, tuition2: '8175', fee2: '1140', tuition3: null, fee3: '5' }])
    expect(pts).toEqual([{ year: 2023, key: 'In-state undergraduate', value: 9315 }])
  })
  it('reads net price by income from public or private columns', () => {
    expect(netPriceByIncome({ npis412: '10000', npt422: '12000' })).toEqual([
      { label: '$0–30,000', value: 10000 },
      { label: '$30,001–48,000', value: 12000 },
    ])
    expect(netPriceByIncome(undefined)).toEqual([])
  })
  it('picks the finance form the institution reports', () => {
    const pts = financeSeries([{ year: 2024, f1correv: '5', f1tufepc: '14', f1stappc: '15', f2tufepc: '99' }], REVENUE_PARTS, 'pc')
    expect(pts.map((p) => [p.key, p.value])).toEqual([['Tuition and fees', 14], ['State appropriations', 15]])
  })
  it('finds the nearest year at or before the selected one', () => {
    const pts = [{ year: 2019, key: 'x', value: 1 }, { year: 2021, key: 'x', value: 2 }]
    expect(atYear(pts, 2020)?.year).toBe(2019)
    expect(atYear(pts, 2018)?.year).toBe(2019)
    expect(atYear(pts, 2030)?.year).toBe(2021)
  })
  it('sums duplicates when tallying', () => {
    const t = tally([{ year: 1, k: 'a', v: 2 }, { year: 1, k: 'a', v: 3 }, { year: 1, k: 'b', v: null }], (r) => r.k, (r) => r.v)
    expect(t).toEqual([{ year: 1, key: 'a', value: 5 }, { year: 1, key: 'b', value: null }])
  })
})
