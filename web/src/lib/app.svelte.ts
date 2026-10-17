import { defaultBasemap, type BasemapId } from './basemaps'
import type { Dataset, Selectable } from './icons'
import { theme } from './theme.svelte'
import { parseUrl, serializeUrl, type UrlState } from './urlstate'
import type { CollegePointsFile, DistrictIndexItem, PointsFile, PrivatePointsFile, PublicSchool, StateMeta, YearsMeta, YearSummary } from './types'

export type Sheet = 'peek' | 'half' | 'full'
export type Drawer = 'layers' | 'filters' | 'basemap' | 'about'

export const app = $state({
  ready: false,
  error: '' as string,
  state: null as StateMeta | null,
  years: null as YearsMeta | null,
  points: null as PointsFile | null,
  college: null as CollegePointsFile | null,
  private: null as PrivatePointsFile | null,
  summary: null as YearSummary | null,
  districtIndex: [] as DistrictIndexItem[],
  year: 0,
  selected: null as { dataset: Selectable; id: string } | null,
  showDistricts: false,
  compare: [] as { dataset: Selectable; id: string }[],
  showCompare: false,
  showTable: false,
  districts: null as GeoJSON.FeatureCollection | null,
  /** explicit user choice; null = follow the theme default */
  basemapChoice: null as BasemapId | null,
  layers: { public: true, private: true, college: true } as Record<Dataset, boolean>,
  sizeByEnroll: true,
  /** colour public school markers by an attribute (the shape stays the same) */
  colorBy: 'dataset' as 'dataset' | 'charter' | 'locale' | 'level',
  includeClosed: false,
  charter: 'all' as 'all' | 'yes' | 'no',
  levels: [] as string[],
  /** college control codes to show (1 public, 2 private not-for-profit, 3 for-profit); empty = all */
  collegeControls: [] as number[],
  /** private school affiliation codes (RELIG: 1 Catholic, 2 other religious, 3 nonsectarian); empty = all */
  privateAffil: [] as number[],
  view: null as { center: [number, number]; zoom: number } | null,
  playing: false,
  /** which left drawer is open (the rail on the left switches between them) */
  drawer: (typeof matchMedia === 'function' && matchMedia('(max-width: 720px)').matches ? null : 'layers') as Drawer | null,
  /** inspector expanded to the wide workspace */
  inspectorWide: false,
  /** phone bottom-sheet snap point for the inspector */
  sheet: 'half' as Sheet,
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

/** Slider range: every year any dataset has (PSS surveys are biennial, so they add no new years). */
export function allYears(): number[] {
  const set = new Set<number>([...(app.points?.years ?? []), ...(app.college?.years ?? [])])
  return [...set].sort((a, b) => a - b)
}

/** The PSS survey shown for a slider year: the latest survey that began in or before it (surveys are biennial). */
export function surveyYearFor(year: number): number | null {
  const ys = (app.private?.years ?? []).filter((y) => y <= year)
  return ys.length ? ys[ys.length - 1] : null
}

export function applyUrl(u: UrlState) {
  if (u.year) app.year = u.year
  if (u.selected) app.selected = u.selected
  if (u.basemap) app.basemapChoice = u.basemap
  if (u.layers) app.layers = { ...app.layers, ...u.layers }
  if (u.theme) theme.pref = u.theme
  if (u.sizeByEnroll === false) app.sizeByEnroll = false
  if (u.colorBy) app.colorBy = u.colorBy
  if (u.includeClosed) app.includeClosed = true
  if (u.charter) app.charter = u.charter
  if (u.levels) app.levels = u.levels
  if (u.collegeControls) app.collegeControls = u.collegeControls
  if (u.privateAffil) app.privateAffil = u.privateAffil
  if (u.districts) app.showDistricts = true
  if (u.compare) app.compare = u.compare
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
    colorBy: app.colorBy,
    includeClosed: app.includeClosed,
    charter: app.charter,
    levels: app.levels,
    collegeControls: app.collegeControls,
    privateAffil: app.privateAffil,
    districts: app.showDistricts,
    compare: app.compare,
    view: app.view ?? undefined,
  }
}

export const readUrl = () => parseUrl(location.search)
export const urlFor = (defaultYear: number) => serializeUrl(currentUrlState(), { year: defaultYear })
