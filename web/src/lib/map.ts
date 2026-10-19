import * as maplibregl from 'maplibre-gl'
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url'
import { BASEMAPS, basemapById, styleUrl, type BasemapId } from './basemaps'
import { cssVar, makeIcon, type Dataset, type Selectable } from './icons'

;(maplibregl as unknown as { setWorkerUrl(u: string): void }).setWorkerUrl(workerUrl)

const DATASETS: Dataset[] = ['public', 'private', 'college']
const VARIANTS = ['open', 'closed', 'approx'] as const
/** Marker image ids are prefixed so they can never collide with the basemap sprite (which has its own 'college' and 'school' icons). */
const imageId = (name: string) => `ee-${name}`
const CATEGORY_ICONS = 8

export type PointFeature = GeoJSON.Feature<GeoJSON.Point, Record<string, unknown>>

export interface MapOptions {
  container: HTMLElement
  basemap: BasemapId
  center: [number, number]
  zoom: number
  pitch?: number
  onSelect: (dataset: Selectable, id: string | null) => void
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
  private selected: { dataset: Selectable; id: string } | null = null
  private districts: GeoJSON.FeatureCollection = { type: 'FeatureCollection', features: [] }
  private districtsVisible = false
  private schoolDistrict: string | null = null
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
      pitch: opts.pitch ?? 0,
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
    this.addDistricts()
    const ratio = 2
    for (const ds of DATASETS) {
      const fill = cssVar(`--c-${ds}`)
      const ring = cssVar('--ring')
      for (const v of VARIANTS) {
        const name = imageId(v === 'open' ? ds : `${ds}-${v}`)
        if (this.map.hasImage(name)) this.map.removeImage(name)
        this.map.addImage(name, makeIcon(ds, { fill, ring, closed: v === 'closed', approx: v === 'approx' }, ratio), { pixelRatio: ratio })
      }
      this.addDataset(ds)
    }
    this.addCategoryIcons()
    this.addSelection()
  }

  /** Public school icons in the categorical chart colours (for "colour by"). */
  private addCategoryIcons() {
    for (let i = 0; i < CATEGORY_ICONS; i++) {
      const name = imageId(`public-cat${i}`)
      if (this.map.hasImage(name)) this.map.removeImage(name)
      this.map.addImage(name, makeIcon('public', { fill: cssVar(`--chart-${i + 1}`), ring: cssVar('--ring') }, 2), { pixelRatio: 2 })
    }
  }

  /** School district polygons sit under the point layers. */
  private addDistricts() {
    const m = this.map
    if (!m.getSource('districts')) m.addSource('districts', { type: 'geojson', data: this.districts, promoteId: 'leaid' })
    const vis = this.districtsVisible ? 'visible' : 'none'
    if (!m.getLayer('districts-fill')) {
      m.addLayer({
        id: 'districts-fill',
        type: 'fill',
        source: 'districts',
        layout: { visibility: vis },
        paint: {
          'fill-color': cssVar('--accent'),
          'fill-opacity': ['case', ['boolean', ['feature-state', 'hover'], false], 0.22, 0.07],
        },
      })
      m.addLayer({
        id: 'districts-line',
        type: 'line',
        source: 'districts',
        layout: { visibility: vis },
        paint: { 'line-color': cssVar('--accent'), 'line-width': 1.2, 'line-opacity': 0.75 },
      })
      m.addLayer({
        id: 'districts-label',
        type: 'symbol',
        source: 'districts',
        minzoom: 7,
        layout: {
          visibility: vis,
          'text-field': ['get', 'name'],
          'text-font': ['Noto Sans Regular'],
          'text-size': 11,
          'text-max-width': 8,
        },
        paint: { 'text-color': cssVar('--text'), 'text-halo-color': cssVar('--surface'), 'text-halo-width': 1.5 },
      })
      m.addLayer({
        id: 'districts-selected',
        type: 'line',
        source: 'districts',
        filter: this.districtFilter(),
        layout: { visibility: vis },
        paint: { 'line-color': cssVar('--accent'), 'line-width': 4 },
      })
      // The district of a selected public school: shown even when the Boundaries toggle is off.
      m.addLayer({
        id: 'districts-school-fill',
        type: 'fill',
        source: 'districts',
        filter: this.schoolDistrictFilter(),
        paint: { 'fill-color': cssVar('--accent'), 'fill-opacity': 0.06 },
      })
      m.addLayer({
        id: 'districts-school-line',
        type: 'line',
        source: 'districts',
        filter: this.schoolDistrictFilter(),
        paint: { 'line-color': cssVar('--accent'), 'line-width': 2.5, 'line-opacity': 0.9, 'line-dasharray': [2, 1] },
      })
    }
    if (!this.wired.has('districts')) {
      this.wired.add('districts')
      let hovered: string | number | undefined
      m.on('mousemove', 'districts-fill', (e) => {
        const f = e.features?.[0]
        if (!f || f.id === hovered) return
        if (hovered !== undefined) m.setFeatureState({ source: 'districts', id: hovered }, { hover: false })
        hovered = f.id
        m.setFeatureState({ source: 'districts', id: hovered! }, { hover: true })
      })
      m.on('mouseleave', 'districts-fill', () => {
        if (hovered !== undefined) m.setFeatureState({ source: 'districts', id: hovered }, { hover: false })
        hovered = undefined
      })
      m.on('click', 'districts-fill', (e) => {
        const layers = DATASETS.flatMap((d) => [`${d}-points`, `${d}-clusters`]).filter((l) => m.getLayer(l))
        if (layers.length && m.queryRenderedFeatures(e.point, { layers }).length) return // a school/college was clicked
        const f = e.features?.[0]
        if (f) this.opts.onSelect('district', String(f.properties.leaid))
      })
    }
  }

  private schoolDistrictFilter(): maplibregl.FilterSpecification {
    return ['==', ['get', 'leaid'], this.schoolDistrict ?? '__none__']
  }

  private districtFilter(): maplibregl.FilterSpecification {
    return ['==', ['get', 'leaid'], this.selected?.dataset === 'district' ? this.selected.id : '__none__']
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
          'icon-image': ['concat', 'ee-', ['get', 'icon']],
          'icon-allow-overlap': true,
          'icon-ignore-placement': true,
          'icon-size': this.iconSize(ds),
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

  /** Public and private schools always match. At the default fixed size colleges are a little larger (a diamond reads smaller than a circle or square of the same box); sized by enrollment, every dataset follows the same scale. */
  private iconSize(ds: Dataset): maplibregl.ExpressionSpecification | number {
    if (!this.sizeByEnroll) return ds === 'college' ? 1.1 : 0.9
    // Log scale: each tenfold step in enrollment adds the same amount, so a 30,000-student university
    // reads clearly bigger than a 500-student school without dwarfing it (about 2x across the whole range).
    return [
      'interpolate',
      ['linear'],
      ['log10', ['max', 50, ['coalesce', ['to-number', ['get', 'enroll']], 300]]],
      1.7, 0.75, // 50 students or fewer
      3, 1.1, // 1,000
      4.6, 1.6, // 40,000 and up
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

  private selectionFilterFor(ds: Dataset): maplibregl.FilterSpecification {
    return this.selectionFilter(ds)
  }

  private selectionFilter(ds: Dataset): maplibregl.FilterSpecification {
    const id = this.selected?.dataset === ds ? this.selected.id : '__none__'
    return ['all', ['!', ['has', 'point_count']], ['==', ['get', 'id'], id]]
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
      if (this.map.getLayer(`${ds}-points`)) this.map.setLayoutProperty(`${ds}-points`, 'icon-size', this.iconSize(ds))
    }
  }

  setDistricts(fc: GeoJSON.FeatureCollection) {
    this.districts = fc
    ;(this.map.getSource('districts') as maplibregl.GeoJSONSource | undefined)?.setData(fc)
  }

  setDistrictsVisible(v: boolean) {
    this.districtsVisible = v
    for (const l of ['districts-fill', 'districts-line', 'districts-label', 'districts-selected']) {
      if (this.map.getLayer(l)) this.map.setLayoutProperty(l, 'visibility', v ? 'visible' : 'none')
    }
  }

  /** Outline the district of the selected public school, independent of the Boundaries toggle. */
  setSchoolDistrict(leaid: string | null) {
    this.schoolDistrict = leaid
    for (const l of ['districts-school-fill', 'districts-school-line']) {
      if (this.map.getLayer(l)) this.map.setFilter(l, this.schoolDistrictFilter())
    }
  }

  fitDistrict(leaid: string) {
    const f = this.districts.features.find((x) => x.properties?.leaid === leaid)
    if (!f) return
    let [w, s, e, n] = [180, 90, -180, -90]
    const walk = (c: unknown): void => {
      if (Array.isArray(c) && typeof c[0] === 'number') {
        w = Math.min(w, c[0] as number); e = Math.max(e, c[0] as number)
        s = Math.min(s, c[1] as number); n = Math.max(n, c[1] as number)
      } else if (Array.isArray(c)) c.forEach(walk)
    }
    walk((f.geometry as GeoJSON.Polygon).coordinates)
    this.map.fitBounds([[w, s], [e, n]], { padding: 60, duration: 600 })
  }

  setSelected(ds: Selectable | null, id: string | null) {
    this.selected = ds && id ? { dataset: ds, id } : null
    if (this.map.getLayer('districts-selected')) this.map.setFilter('districts-selected', this.districtFilter())
    for (const d of DATASETS) {
      if (this.map.getLayer(`${d}-selected`)) this.map.setFilter(`${d}-selected`, this.selectionFilter(d))
    }
  }

  setBasemap(id: BasemapId) {
    const b = basemapById(id)
    if (!b) return
    if (id === this.basemap) return
    this.basemap = id
    this.map.setStyle(styleUrl(b)) // overlays are re-added in the style.load handler
  }

  /** Refresh theme-dependent paint (icons, cluster colours) after a light/dark change. */
  applyTheme() {
    if (this.map.isStyleLoaded()) this.install2()
  }

  private install2() {
    const ratio = 2
    for (const ds of DATASETS) {
      for (const v of VARIANTS) {
        const name = imageId(v === 'open' ? ds : `${ds}-${v}`)
        if (this.map.hasImage(name)) this.map.removeImage(name)
        this.map.addImage(name, makeIcon(ds, { fill: cssVar(`--c-${ds}`), ring: cssVar('--ring'), closed: v === 'closed', approx: v === 'approx' }, ratio), { pixelRatio: ratio })
      }
      if (this.map.getLayer(`${ds}-clusters`)) {
        this.map.setPaintProperty(`${ds}-clusters`, 'circle-color', cssVar(`--c-${ds}`))
        this.map.setPaintProperty(`${ds}-clusters`, 'circle-stroke-color', cssVar('--ring'))
      }
      for (const l of ['districts-fill', 'districts-line', 'districts-selected', 'districts-school-fill', 'districts-school-line']) {
        if (this.map.getLayer(l)) this.map.setPaintProperty(l, l.endsWith('-fill') ? 'fill-color' : 'line-color', cssVar('--accent'))
      }
      if (this.map.getLayer('districts-label')) {
        this.map.setPaintProperty('districts-label', 'text-color', cssVar('--text'))
        this.map.setPaintProperty('districts-label', 'text-halo-color', cssVar('--surface'))
      }
    }
    for (const d of DATASETS) {
      if (this.map.getLayer(`${d}-selected`)) this.map.setPaintProperty(`${d}-selected`, 'circle-stroke-color', cssVar('--accent'))
    }
    this.addCategoryIcons()
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
