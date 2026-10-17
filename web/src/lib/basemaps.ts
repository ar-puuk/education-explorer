export type BasemapId = 'liberty' | 'bright' | 'positron' | 'dark' | 'fiord'

export interface Basemap {
  id: BasemapId
  label: string
  /** OpenFreeMap style name. */
  style: string
  note?: string
}

const BASE = 'https://tiles.openfreemap.org/styles/'

export const BASEMAPS: Basemap[] = [
  { id: 'positron', label: 'Positron', style: 'positron' },
  { id: 'dark', label: 'Dark', style: 'dark', note: 'Less complete labelling than the other styles.' },
  { id: 'liberty', label: 'Liberty', style: 'liberty' },
  { id: 'bright', label: 'Bright', style: 'bright' },
  { id: 'fiord', label: 'Fiord', style: 'fiord', note: 'Less complete labelling than the other styles.' },
]

export const styleUrl = (b: Basemap) => BASE + b.style

export function defaultBasemap(theme: 'light' | 'dark'): BasemapId {
  return theme === 'dark' ? 'dark' : 'positron'
}

export const basemapById = (id: string | null | undefined): Basemap | undefined => BASEMAPS.find((b) => b.id === id)
