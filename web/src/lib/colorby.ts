import { levelLabel } from './labels'

export type ColorBy = 'dataset' | 'charter' | 'locale' | 'level'

export interface Category {
  key: string
  label: string
}

/** Colour categories for public school markers; index i uses the theme token --chart-(i+1). */
export const CATEGORIES: Record<Exclude<ColorBy, 'dataset'>, Category[]> = {
  charter: [{ key: 'no', label: 'Not a charter school' }, { key: 'yes', label: 'Charter school' }, { key: 'na', label: 'Unknown' }],
  locale: [{ key: 'city', label: 'City' }, { key: 'suburb', label: 'Suburb' }, { key: 'town', label: 'Town' }, { key: 'rural', label: 'Rural' }, { key: 'na', label: 'Unknown' }],
  level: [{ key: 'Elementary', label: 'Elementary' }, { key: 'Middle', label: 'Middle' }, { key: 'High', label: 'High' }, { key: 'Other', label: 'Other / not reported' }],
}

export function categoryIndex(mode: Exclude<ColorBy, 'dataset'>, s: { charter: string | null; locale: string | null; level: string | null }): number {
  const cats = CATEGORIES[mode]
  let key = 'na'
  if (mode === 'charter') key = s.charter === 'Yes' ? 'yes' : s.charter === 'No' ? 'no' : 'na'
  else if (mode === 'locale') {
    const c = s.locale ?? ''
    key = /^1\d?$/.test(c) && c.length === 2 ? 'city' : /^2\d$/.test(c) ? 'suburb' : /^3\d$/.test(c) ? 'town' : /^4\d$/.test(c) ? 'rural' : 'na'
    // pre-2006 codes: 1-2 city, 3-4 suburb, 5-6 town, 7-8 rural
    if (key === 'na' && /^[1-8]$/.test(c)) key = ['city', 'city', 'suburb', 'suburb', 'town', 'town', 'rural', 'rural'][Number(c) - 1]
  } else {
    const l = levelLabel(s.level)
    key = ['Elementary', 'Middle', 'High'].includes(l) ? l : 'Other'
  }
  const i = cats.findIndex((c) => c.key === key)
  return i < 0 ? cats.length - 1 : i
}
