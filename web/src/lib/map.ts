import * as maplibregl from 'maplibre-gl'
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url'
import { BASEMAPS, basemapById, styleUrl, type BasemapId } from './basemaps'
import { cssVar, makeIcon, type Dataset } from './icons'

;(maplibregl as unknown as { setWorkerUrl(u: string): void }).setWorkerUrl(workerUrl)

const DATASETS: Dataset[] = ['public', 'private', 'college']
const VARIANTS = ['open', 'closed', 'approx'] as const

export type PointFeature = GeoJSON.Feature<GeoJSON.Point, Record<string, unknown>>

export interface MapOptions {
  container: HTMLElement
  basemap: BasemapId
  center: [number, number]
  zoom: number
  pitch?: number
  onSelect: (dataset: Dataset, id: string | null) => void
  onMove: (center: [number, number], zoom: number) => void
  onStyleReady?: () => void
}

/** Wraps MapLibre. All overlay sources/layers/images are (re)created on every `style.load`
 *  so switching the basemap never loses data. */
export class MapController {
  map: maplibregl.Map
  private data: Record<Dataset, GeoJSON.FeatureCollection> = {
    public: { type: 'FeatureCollection', features: [] },
    private: { type: 'FeatureCollection', features: [] },
    college: { type: 'FeatureCollection', features: [] },
  }
  private visible: Record<Dataset, boolean> = { public: true, private: true, college: true }
  private selected: { dataset: Dataset; id: string } | null = null
  private sizeByEnroll = true
  private wired = new Set<string>()
  private popup = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 16, className: 'ee-popup' })
  private opts: MapOptions
  basemap: BasemapId

  constructor(opts: MapOptions) {
    this.opts = opts
    this.basemap = opts.basemap
    const b = basemapById(opts.basemap) ?? BASEMAPS[0]
    this.map = new maplibregl.Map({
      container: opts.container,
      style: styleUrl(b),
      center: opts.center,
      zoom: opts.zoom,
      pitch: opts.basemap === 'liberty3d' ? 60 : (opts.pitch ?? 0),
      attributionControl: { compact: true },
      canvasContextAttributes: { antialias: true },
    })
    this.map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), 'top-right')
    this.map.addControl(new maplibregl.ScaleControl({ unit: 'imperial' }), 'bottom-left')
    this.map.on('style.load', () => {
      this.install()
      this.opts.onStyleReady?.()
    })
    this.map.on('moveend', () => {
      const c = this.map.getCenter()
      this.opts.onMove([c.lng, c.lat], this.map.getZoom())
    })
  }

  // -------------------------------------------------------------------- install overlays
  private install() {
    const ratio = 2
    for (const ds of DATASETS) {
      const fill = cssVar(`--c-${ds}`)
      const ring = cssVar('--ring')
      for (const v of VARIANTS) {
        const name = v === 'open' ? ds : `${ds}-${v}`
        if (this.map.hasImage(name)) this.map.removeImage(name)
        this.map.addImage(name, makeIcon(ds, { fill, ring, closed: v === 'closed', approx: v === 'approx' }, ratio), { pixelRatio: ratio })
      }
      this.addDataset(ds)
    }
    this.addSelection()
    this.setBasemapExtras()
  }

  private addDataset(ds: Dataset) {
    const m = this.map
    const color = cssVar(`--c-${ds}`)
    if (!m.getSource(ds)) {
      m.addSource(ds, { type: 'geojson', data: this.data[ds], cluster: true, clusterRadius: 38, clusterMaxZoom: 10 })
    }
    const vis = this.visible[ds] ? 'visible' : 'none'
    if (!m.getLayer(`${ds}-clusters`)) {
      m.addLayer({
        id: `${ds}-clusters`,
        type: 'circle',
        source: ds,
        filter: ['has', 'point_count'],
        layout: { visibility: vis },
        paint: {
          'circle-color': color,
          'circle-radius': ['step', ['get', 'point_count'], 14, 10, 18, 50, 23, 200, 29],
          'circle-stroke-width': 2,
          'circle-stroke-color': cssVar('--ring'),
          'circle-opacity': 0.92,
        },
      })
      m.addLayer({
        id: `${ds}-cluster-count`,
        type: 'symbol',
        source: ds,
        filter: ['has', 'point_count'],
        layout: {
          visibility: vis,
          'text-field': ['get', 'point_count_abbreviated'],
          'text-font': ['Noto Sans Bold'],
          'text-size': 12,
          'text-allow-overlap': true,
        },
        paint: { 'text-color': '#ffffff' },
      })
      m.addLayer({
        id: `${ds}-points`,
        type: 'symbol',
        source: ds,
        filter: ['!', ['has', 'point_count']],
        layout: {
          visibility: vis,
          'icon-image': ['get', 'icon'],
          'icon-allow-overlap': true,
          'icon-ignore-placement': true,
          'icon-size': this.iconSize(),
        },
      })
      if (this.wired.has(ds)) return
      this.wired.add(ds)
      m.on('click', `${ds}-clusters`, (e) => {
        const f = e.features?.[0]
        if (!f) return
        const src = m.getSource(ds) as maplibregl.GeoJSONSource
        src.getClusterExpansionZoom(f.properties.cluster_id).then((z) => {
          m.easeTo({ center: (f.geometry as GeoJSON.Point).coordinates as [number, number], zoom: z + 0.3 })
        })
      })
      m.on('click', `${ds}-points`, (e) => {
        const f = e.features?.[0]
        if (f) this.opts.onSelect(ds, String(f.properties.id))
      })
      const hover = (e: maplibregl.MapLayerMouseEvent) => {
        m.getCanvas().style.cursor = 'pointer'
        const f = e.features?.[0]
        if (!f) return
        const p = f.properties
        const enr = p.enroll != null && p.enroll !== 'null' ? ` &middot; ${Number(p.enroll).toLocaleString()} students` : ''
        this.popup
          .setLngLat((f.geometry as GeoJSON.Point).coordinates as [number, number])
          .setHTML(`<strong>${escapeHtml(String(p.name))}</strong>${enr}`)
          .addTo(m)
      }
      for (const l of [`${ds}-points`, `${ds}-clusters`]) {
        m.on('mouseenter', l, () => (m.getCanvas().style.cursor = 'pointer'))
        m.on('mouseleave', l, () => {
          m.getCanvas().style.cursor = ''
          this.popup.remove()
        })
      }
      m.on('mousemove', `${ds}-points`, hover)
    }
  }

  private iconSize(): maplibregl.ExpressionSpecification | number {
    if (!this.sizeByEnroll) return 0.9
    return [
      'interpolate',
      ['linear'],
      ['coalesce', ['to-number', ['get', 'enroll']], 300],
      0, 0.7,
      300, 0.85,
      1000, 1.05,
      2500, 1.35,
    ]
  }

  private addSelection() {
    const m = this.map
    for (const ds of DATASETS) {
      if (m.getLayer(`${ds}-selected`)) continue
      m.addLayer({
        id: `${ds}-selected`,
        type: 'circle',
        source: ds,
        filter: this.selectionFilter(ds),
        paint: {
          'circle-radius': 22,
          'circle-color': 'rgba(0,0,0,0)',
          'circle-stroke-width': 3,
          'circle-stroke-color': cssVar('--accent'),
        },
      })
    }
  }

  private selectionFilter(ds: Dataset): maplibregl.FilterSpecification {
    const id = this.selected?.dataset === ds ? this.selected.id : '__none__'
    return ['all', ['!', ['has', 'point_count']], ['==', ['get', 'id'], id]]
  }

  /** Liberty 3D: tilted camera on top of the Liberty style, which already has a building-3d layer. */
  private setBasemapExtras() {
    const is3d = this.basemap === 'liberty3d'
    if (this.map.getLayer('building-3d')) {
      this.map.setLayoutProperty('building-3d', 'visibility', is3d ? 'visible' : 'none')
    }
  }

  // -------------------------------------------------------------------- public API
  setData(ds: Dataset, features: PointFeature[]) {
    this.data[ds] = { type: 'FeatureCollection', features }
    const src = this.map.getSource(ds) as maplibregl.GeoJSONSource | undefined
    src?.setData(this.data[ds])
  }

  setVisible(ds: Dataset, v: boolean) {
    this.visible[ds] = v
    for (const l of ['clusters', 'cluster-count', 'points']) {
      if (this.map.getLayer(`${ds}-${l}`)) this.map.setLayoutProperty(`${ds}-${l}`, 'visibility', v ? 'visible' : 'none')
    }
  }

  setSizeByEnroll(on: boolean) {
    this.sizeByEnroll = on
    for (const ds of DATASETS) {
      if (this.map.getLayer(`${ds}-points`)) this.map.setLayoutProperty(`${ds}-points`, 'icon-size', this.iconSize())
    }
  }

  setSelected(ds: Dataset | null, id: string | null) {
    this.selected = ds && id ? { dataset: ds, id } : null
    for (const d of DATASETS) {
      if (this.map.getLayer(`${d}-selected`)) this.map.setFilter(`${d}-selected`, this.selectionFilter(d))
    }
  }

  setBasemap(id: BasemapId) {
    const b = basemapById(id)
    if (!b) return
    if (id === this.basemap) return
    const prev = basemapById(this.basemap)
    this.basemap = id
    if (prev && prev.style === b.style) {
      // Liberty <-> Liberty 3D: no style reload, just camera and the building layer
      this.setBasemapExtras()
    } else {
      this.map.setStyle(styleUrl(b)) // overlays are re-added in the style.load handler
    }
    this.map.easeTo({ pitch: id === 'liberty3d' ? 60 : 0, duration: 600 })
  }

  /** Refresh theme-dependent paint (icons, cluster colours) after a light/dark change. */
  applyTheme() {
    if (this.map.isStyleLoaded()) this.install2()
  }

  private install2() {
    const ratio = 2
    for (const ds of DATASETS) {
      for (const v of VARIANTS) {
        const name = v === 'open' ? ds : `${ds}-${v}`
        if (this.map.hasImage(name)) this.map.removeImage(name)
        this.map.addImage(name, makeIcon(ds, { fill: cssVar(`--c-${ds}`), ring: cssVar('--ring'), closed: v === 'closed', approx: v === 'approx' }, ratio), { pixelRatio: ratio })
      }
      if (this.map.getLayer(`${ds}-clusters`)) {
        this.map.setPaintProperty(`${ds}-clusters`, 'circle-color', cssVar(`--c-${ds}`))
        this.map.setPaintProperty(`${ds}-clusters`, 'circle-stroke-color', cssVar('--ring'))
      }
    }
    for (const d of DATASETS) {
      if (this.map.getLayer(`${d}-selected`)) this.map.setPaintProperty(`${d}-selected`, 'circle-stroke-color', cssVar('--accent'))
    }
  }

  flyTo(lon: number, lat: number, zoom = 14) {
    this.map.flyTo({ center: [lon, lat], zoom: Math.max(this.map.getZoom(), zoom), essential: true })
  }

  fitBounds(b: [number, number, number, number]) {
    this.map.fitBounds([[b[0], b[1]], [b[2], b[3]]], { padding: 40, duration: 0 })
  }

  resize() {
    this.map.resize()
  }

  destroy() {
    this.map.remove()
  }
}

function escapeHtml(s: string) {
  return s.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]!)
}
