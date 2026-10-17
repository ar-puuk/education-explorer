<script lang="ts">
  import { onMount } from 'svelte'
  import { MapController, type PointFeature } from '../lib/map'
  import { app, basemap, isOperating, surveyYearFor } from '../lib/app.svelte'
  import { levelLabel } from '../lib/labels'
  import { theme } from '../lib/theme.svelte'

  let el: HTMLDivElement
  let ctl = $state.raw<MapController | undefined>()

  const features = $derived.by((): PointFeature[] => {
    const p = app.points
    if (!p || !app.year) return []
    const out: PointFeature[] = []
    for (const s of p.schools) {
      const i = s.years.indexOf(app.year)
      if (i < 0) continue
      const status = p.statuses[s.status[i]] ?? ''
      const operating = isOperating(status)
      if (!operating && !app.includeClosed) continue
      if (app.charter === 'yes' && s.charter !== 'Yes') continue
      if (app.charter === 'no' && s.charter === 'Yes') continue
      if (app.levels.length && !app.levels.includes(levelLabel(s.level))) continue
      out.push({
        type: 'Feature',
        geometry: { type: 'Point', coordinates: [s.lon, s.lat] },
        properties: { id: s.id, name: s.name, enroll: s.enroll[i], status, icon: operating ? 'public' : 'public-closed' },
      })
    }
    return out
  })

  const collegeFeatures = $derived.by((): PointFeature[] => {
    const c = app.college
    if (!c || !app.year) return []
    const out: PointFeature[] = []
    for (const s of c.institutions) {
      const i = s.years.indexOf(app.year)
      if (i < 0) continue
      const operating = s.active[i] === 1
      if (!operating && !app.includeClosed) continue
      if (app.collegeControls.length && !app.collegeControls.includes(s.control ?? -9)) continue
      out.push({
        type: 'Feature',
        geometry: { type: 'Point', coordinates: [s.lon, s.lat] },
        properties: { id: s.id, name: s.name, enroll: s.enroll[i], icon: !operating ? 'college-closed' : s.approx ? 'college-approx' : 'college' },
      })
    }
    return out
  })

  const privateFeatures = $derived.by((): PointFeature[] => {
    const p = app.private
    const sy = surveyYearFor(app.year)
    if (!p || sy == null) return []
    const out: PointFeature[] = []
    for (const s of p.schools) {
      const i = s.years.indexOf(sy)
      if (i < 0) continue
      if (app.privateAffil.length && !app.privateAffil.includes(s.relig ?? -9)) continue
      out.push({
        type: 'Feature',
        geometry: { type: 'Point', coordinates: [s.lon, s.lat] },
        properties: { id: s.id, name: s.name, enroll: s.enroll[i], icon: s.approx ? 'private-approx' : 'private' },
      })
    }
    return out
  })

  onMount(() => {
    const st = app.state!
    const c = new MapController({
      container: el,
      basemap: basemap.id,
      center: app.view?.center ?? st.center,
      zoom: app.view?.zoom ?? st.zoom,
      onSelect: (dataset, id) => {
        app.selected = id ? { dataset, id } : null
      },
      onMove: (center, zoom) => {
        app.view = { center, zoom }
      },
    })
    ctl = c
    const ro = new ResizeObserver(() => c.resize())
    ro.observe(el)
    // test hook (used by the browser checks; harmless in production)
    ;(window as unknown as { __ee: unknown }).__ee = { controller: c }
    return () => {
      ro.disconnect()
      c.destroy()
    }
  })

  $effect(() => ctl?.setData('public', features))
  $effect(() => ctl?.setData('college', collegeFeatures))
  $effect(() => ctl?.setData('private', privateFeatures))
  $effect(() => ctl?.setBasemap(basemap.id))
  $effect(() => {
    theme.effective
    ctl?.applyTheme()
  })
  $effect(() => ctl?.setVisible('public', app.layers.public))
  $effect(() => ctl?.setVisible('private', app.layers.private))
  $effect(() => ctl?.setVisible('college', app.layers.college))
  $effect(() => ctl?.setSizeByEnroll(app.sizeByEnroll))
  $effect(() => ctl?.setSelected(app.selected?.dataset ?? null, app.selected?.id ?? null))

  /** Used by the search box and the detail panel. */
  export function flyTo(lon: number, lat: number) {
    ctl?.flyTo(lon, lat)
  }
</script>

<div class="map" bind:this={el} role="application" aria-label="Map of schools"></div>

<style>
  .map {
    position: absolute;
    inset: 0;
  }
  :global(.ee-popup .maplibregl-popup-content) {
    background: var(--surface);
    color: var(--text);
    box-shadow: var(--shadow);
    padding: 6px 10px;
    font-size: 12.5px;
    border-radius: 6px;
    pointer-events: none;
  }
  :global(.ee-popup .maplibregl-popup-tip) {
    border-top-color: var(--surface) !important;
    border-bottom-color: var(--surface) !important;
  }
</style>
