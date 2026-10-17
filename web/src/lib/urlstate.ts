import { basemapById, type BasemapId } from './basemaps'
import type { Dataset } from './icons'

export interface UrlState {
  year?: number
  selected?: { dataset: Dataset; id: string }
  basemap?: BasemapId
  layers?: Partial<Record<Dataset, boolean>>
  theme?: 'system' | 'light' | 'dark'
  sizeByEnroll?: boolean
  includeClosed?: boolean
  charter?: 'all' | 'yes' | 'no'
  levels?: string[]
  view?: { center: [number, number]; zoom: number }
}

const DATASETS: Dataset[] = ['public', 'private', 'college']

export function parseUrl(search: string): UrlState {
  const q = new URLSearchParams(search)
  const out: UrlState = {}
  const y = Number(q.get('year'))
  if (Number.isInteger(y) && y > 1900 && y < 2200) out.year = y
  const sel = q.get('sel')
  if (sel) {
    const [ds, ...rest] = sel.split(':')
    if (DATASETS.includes(ds as Dataset) && rest.length) out.selected = { dataset: ds as Dataset, id: rest.join(':') }
  }
  const b = q.get('base')
  if (b && basemapById(b)) out.basemap = b as BasemapId
  const l = q.get('layers')
  if (l !== null) {
    const on = new Set(l.split(',').filter(Boolean))
    out.layers = Object.fromEntries(DATASETS.map((d) => [d, on.has(d)])) as Record<Dataset, boolean>
  }
  const t = q.get('theme')
  if (t === 'system' || t === 'light' || t === 'dark') out.theme = t
  if (q.get('size') === '0') out.sizeByEnroll = false
  if (q.get('closed') === '1') out.includeClosed = true
  const c = q.get('charter')
  if (c === 'yes' || c === 'no') out.charter = c
  const lv = q.get('level')
  if (lv) out.levels = lv.split('|').filter(Boolean)
  const v = q.get('v')
  if (v) {
    const [lon, lat, z] = v.split(',').map(Number)
    if ([lon, lat, z].every(Number.isFinite)) out.view = { center: [lon, lat], zoom: z }
  }
  return out
}

export function serializeUrl(s: UrlState, defaults: { year: number }): string {
  const q = new URLSearchParams()
  if (s.year !== undefined && s.year !== defaults.year) q.set('year', String(s.year))
  if (s.selected) q.set('sel', `${s.selected.dataset}:${s.selected.id}`)
  if (s.basemap) q.set('base', s.basemap)
  if (s.layers) {
    const on = DATASETS.filter((d) => s.layers![d] !== false)
    if (on.length !== DATASETS.length) q.set('layers', on.join(','))
  }
  if (s.theme && s.theme !== 'system') q.set('theme', s.theme)
  if (s.sizeByEnroll === false) q.set('size', '0')
  if (s.includeClosed) q.set('closed', '1')
  if (s.charter && s.charter !== 'all') q.set('charter', s.charter)
  if (s.levels?.length) q.set('level', s.levels.join('|'))
  if (s.view) q.set('v', `${s.view.center[0].toFixed(4)},${s.view.center[1].toFixed(4)},${s.view.zoom.toFixed(2)}`)
  const str = q.toString()
  return str ? `?${str}` : ''
}
