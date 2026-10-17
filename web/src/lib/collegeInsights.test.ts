import { describe, expect, it } from 'vitest'
import { ageMix, financeHistory, originBars, salaryByRank, staffByRank } from './collegeInsights'
import { withinGroups } from './insights'

describe('college insights', () => {
  it('builds the age mix from age bands only, from 2003', () => {
    const rows = [
      { year: 2010, lstudy: 1, efbage: 5, efage09: 100 },
      { year: 2010, lstudy: 1, efbage: 2, efage09: 400 }, // "under 25" subtotal must be ignored
      { year: 2010, lstudy: 2, efbage: 5, efage09: 90 },
      { year: 1999, lstudy: 1, efbage: 5, efage09: 5 },
    ]
    expect(ageMix(rows, 1)).toEqual([{ year: 2010, key: '20–21', value: 100 }])
  })
  it('lists the largest origins and groups the rest', () => {
    const rows = [
      { year: 2022, line: 1, efres01: 3 }, { year: 2022, line: 2, efres01: 50 }, { year: 2022, line: 3, efres01: 20 },
      { year: 2022, line: 90, efres01: 7 }, { year: 2022, line: 99, efres01: 80 }, { year: 2022, line: 98, efres01: null },
    ]
    const r = originBars(rows, 2023, (l) => `S${l}`, 1)!
    expect(r.year).toBe(2022)
    expect(r.items).toEqual([{ label: 'S2', value: 50 }, { label: 'All other states and territories', value: 23 }, { label: 'Foreign countries', value: 7 }])
    expect(originBars([], 2022, String)).toBeNull()
  })
  it('prefers NCES derived salaries and falls back to monthly x 9', () => {
    const pts = salaryByRank(
      [{ year: 2021, salprof: '120000', salassc: '.' }],
      [{ year: 2012, arank: 1, saavmnt: 1000 }, { year: 2021, arank: 2, saavmnt: 5000 }, { year: 2021, arank: 1, saavmnt: 9999 }],
    )
    expect(pts.map((p) => [p.year, p.key, p.value])).toEqual([[2012, 'Professor', 9000], [2021, 'Professor', 120000], [2021, 'Associate professor', 45000]])
    expect(staffByRank([{ year: 2024, arank: 7, satotlt: 10 }, { year: 2024, arank: 1, satotlt: 4 }])).toEqual([{ year: 2024, key: 'Professor', value: 4 }])
  })
  it('splits finance into sources and puts the remainder in Other', () => {
    const f = financeHistory({
      public: [{ year: 2010, f1b01: 10, f1b11: 30, f1b17: 5, f1b25: 60, f1c011: 20, f1c191: 50 }],
      nonprofit: [], forprofit: [],
    })
    expect(f.revenue.map((p) => [p.key, p.value])).toEqual([
      ['Tuition and fees', 10], ['Government appropriations, grants and contracts', 30], ['Investment income', 5], ['Other', 15],
    ])
    expect(f.expense.map((p) => [p.key, p.value])).toEqual([['Instruction', 20], ['Other (plant, depreciation, other)', 30]])
  })
  it('groups within a year and ignores suppressed cells', () => {
    const rows = [
      { year: 2023, g: 'K', s: 'a', v: 3 }, { year: 2023, g: 'K', s: 'b', v: 1 }, { year: 2023, g: 'K', s: 'c', v: null }, { year: 2023, g: '1', s: 'a', v: 0 },
    ]
    const r = withinGroups(rows, 2024, (x) => x.g, (x) => x.s, (x) => x.v)!
    expect(r.year).toBe(2023)
    expect(r.groups).toEqual([{ group: 'K', total: 4, segs: [{ key: 'a', value: 3 }, { key: 'b', value: 1 }] }])
  })
})
