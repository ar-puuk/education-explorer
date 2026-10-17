import { describe, expect, it } from 'vitest'
import { parseUrl, serializeUrl } from './urlstate'

describe('url state', () => {
  it('round-trips the full state', () => {
    const s = {
      year: 2019,
      selected: { dataset: 'public' as const, id: '490081000459' },
      basemap: 'bright' as const,
      layers: { public: true, private: false, college: true },
      theme: 'dark' as const,
      sizeByEnroll: false,
      includeClosed: true,
      charter: 'yes' as const,
      levels: ['High', 'Middle'],
      view: { center: [-111.65, 39.32] as [number, number], zoom: 7.5 },
    }
    const q = serializeUrl(s, { year: 2024 })
    const back = parseUrl(q)
    expect(back.year).toBe(2019)
    expect(back.selected).toEqual(s.selected)
    expect(back.basemap).toBe('bright')
    expect(back.layers).toEqual({ public: true, private: false, college: true })
    expect(back.theme).toBe('dark')
    expect(back.sizeByEnroll).toBe(false)
    expect(back.includeClosed).toBe(true)
    expect(back.charter).toBe('yes')
    expect(back.levels).toEqual(['High', 'Middle'])
    expect(back.view?.zoom).toBeCloseTo(7.5)
  })

  it('omits defaults', () => {
    expect(serializeUrl({ year: 2024, layers: { public: true, private: true, college: true }, theme: 'system' }, { year: 2024 })).toBe('')
  })

  it('ignores junk', () => {
    const u = parseUrl('?year=abc&sel=nope&base=zzz&theme=pink&v=1,2')
    expect(u).toEqual({})
  })

  it('keeps ids containing colons', () => {
    expect(parseUrl('?sel=public:a:b').selected).toEqual({ dataset: 'public', id: 'a:b' })
  })
})
