export type BasemapId = 'liberty' | 'liberty3d' | 'bright' | 'positron' | 'dark' | 'fiord'

export interface Basemap {
  id: BasemapId
  label: string
  /** OpenFreeMap style name (liberty3d reuses liberty and adds camera pitch). */
  style: string
  note?: string
}

const BASE = 'https://tiles.openfreemap.org/styles/'

export const BASEMAPS: Basemap[] = [
  { id: 'positron', label: 'Positron', style: 'positron' },
  { id: 'dark', label: 'Dark', style: 'dark', note: 'Less complete labelling than the other styles.' },
  { id: 'liberty', label: 'Liberty', style: 'liberty' },
  { id: 'liberty3d', label: 'Liberty 3D', style: 'liberty', note: 'Liberty with tilted camera and 3D buildings.' },
  { id: 'bright', label: 'Bright', style: 'bright' },
  { id: 'fiord', label: 'Fiord', style: 'fiord', note: 'Less complete labelling than the other styles.' },
]

export const styleUrl = (b: Basemap) => BASE + b.style

export function defaultBasemap(theme: 'light' | 'dark'): BasemapId {
  return theme === 'dark' ? 'dark' : 'positron'
}

export const basemapById = (id: string | null | undefined): Basemap | undefined => BASEMAPS.find((b) => b.id === id)
