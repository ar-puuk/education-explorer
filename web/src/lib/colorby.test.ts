import { describe, expect, it } from 'vitest'
import { categoryIndex, CATEGORIES } from './colorby'
import { parseUrl, serializeUrl } from './urlstate'

const s = (o: Partial<{ charter: string | null; locale: string | null; level: string | null }>) => ({ charter: null, locale: null, level: null, ...o })

describe('colour by', () => {
  it('maps charter status', () => {
    expect(categoryIndex('charter', s({ charter: 'Yes' }))).toBe(1)
    expect(categoryIndex('charter', s({ charter: 'No' }))).toBe(0)
    expect(categoryIndex('charter', s({ charter: 'Not applicable' }))).toBe(2)
  })
  it('groups locale codes (both code schemes)', () => {
    expect(categoryIndex('locale', s({ locale: '12' }))).toBe(0)
    expect(categoryIndex('locale', s({ locale: '21' }))).toBe(1)
    expect(categoryIndex('locale', s({ locale: '33' }))).toBe(2)
    expect(categoryIndex('locale', s({ locale: '43' }))).toBe(3)
    expect(categoryIndex('locale', s({ locale: '7' }))).toBe(3) // pre-2006 rural
    expect(categoryIndex('locale', s({ locale: null }))).toBe(CATEGORIES.locale.length - 1)
  })
  it('groups levels and merges "not reported" spellings', () => {
    expect(categoryIndex('level', s({ level: 'High' }))).toBe(2)
    expect(categoryIndex('level', s({ level: 'N' }))).toBe(3)
    expect(categoryIndex('level', s({ level: 'Prekindergarten' }))).toBe(3)
  })
  it('round-trips through the URL', () => {
    const q = serializeUrl({ colorBy: 'locale', year: 2020 }, { year: 2024 })
    expect(parseUrl(q).colorBy).toBe('locale')
    expect(serializeUrl({ colorBy: 'dataset', year: 2024 }, { year: 2024 })).toBe('')
  })
})
