import { defaultBasemap, type BasemapId } from './basemaps'
import type { Dataset } from './icons'
import { theme } from './theme.svelte'
import { parseUrl, serializeUrl, type UrlState } from './urlstate'
import type { PointsFile, PublicSchool, StateMeta, YearsMeta } from './types'

export const app = $state({
  ready: false,
  error: '' as string,
  state: null as StateMeta | null,
  years: null as YearsMeta | null,
  points: null as PointsFile | null,
  year: 0,
  selected: null as { dataset: Dataset; id: string } | null,
  /** explicit user choice; null = follow the theme default */
  basemapChoice: null as BasemapId | null,
  layers: { public: true, private: true, college: true } as Record<Dataset, boolean>,
  sizeByEnroll: true,
  includeClosed: false,
  charter: 'all' as 'all' | 'yes' | 'no',
  levels: [] as string[],
  view: null as { center: [number, number]; zoom: number } | null,
  playing: false,
  panelOpen: true,
})

export const basemap = {
  get id(): BasemapId {
    return app.basemapChoice ?? defaultBasemap(theme.effective)
  },
}

export const NON_OPERATING = new Set(['Closed', 'Future', 'Future School'])
export const isOperating = (status: string | undefined | null) => !NON_OPERATING.has(status ?? '')

export function schoolIndexForYear(s: PublicSchool, year: number): number {
  return s.years.indexOf(year)
}

export function statusAt(s: PublicSchool, year: number, statuses: string[]): string | null {
  const i = schoolIndexForYear(s, year)
  return i < 0 ? null : (statuses[s.status[i]] ?? null)
}

/** Years available for the public dataset, from years.json (directory table). */
export function publicYears(): number[] {
  return app.points?.years ?? []
}

export function applyUrl(u: UrlState) {
  if (u.year) app.year = u.year
  if (u.selected) app.selected = u.selected
  if (u.basemap) app.basemapChoice = u.basemap
  if (u.layers) app.layers = { ...app.layers, ...u.layers }
  if (u.theme) theme.pref = u.theme
  if (u.sizeByEnroll === false) app.sizeByEnroll = false
  if (u.includeClosed) app.includeClosed = true
  if (u.charter) app.charter = u.charter
  if (u.levels) app.levels = u.levels
  if (u.view) app.view = u.view
}

export function currentUrlState(): UrlState {
  return {
    year: app.year,
    selected: app.selected ?? undefined,
    basemap: app.basemapChoice ?? undefined,
    layers: app.layers,
    theme: theme.pref,
    sizeByEnroll: app.sizeByEnroll,
    includeClosed: app.includeClosed,
    charter: app.charter,
    levels: app.levels,
    view: app.view ?? undefined,
  }
}

export const readUrl = () => parseUrl(location.search)
export const urlFor = (defaultYear: number) => serializeUrl(currentUrlState(), { year: defaultYear })
