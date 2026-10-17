<script lang="ts">
  import { onMount } from 'svelte'
  import { MapController, type PointFeature } from '../lib/map'
  import { app, basemap } from '../lib/app.svelte'
  import { visibleColleges, visiblePrivate, visiblePublic } from '../lib/filters'
  import { loadDistricts } from '../lib/data'
  import { theme } from '../lib/theme.svelte'

  let el: HTMLDivElement
  let ctl = $state.raw<MapController | undefined>()

  const features = $derived.by((): PointFeature[] =>
    visiblePublic().map(({ s, i, status, operating }) => ({
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [s.lon, s.lat] },
      properties: { id: s.id, name: s.name, enroll: s.enroll[i], status, icon: operating ? 'public' : 'public-closed' },
    })),
  )

  const collegeFeatures = $derived.by((): PointFeature[] =>
    visibleColleges().map(({ s, i, operating }) => ({
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [s.lon, s.lat] },
      properties: { id: s.id, name: s.name, enroll: s.enroll[i], icon: !operating ? 'college-closed' : s.approx ? 'college-approx' : 'college' },
    })),
  )

  const privateFeatures = $derived.by((): PointFeature[] =>
    visiblePrivate().map(({ s, i }) => ({
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [s.lon, s.lat] },
      properties: { id: s.id, name: s.name, enroll: s.enroll[i], icon: s.approx ? 'private-approx' : 'private' },
    })),
  )

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
  $effect(() => ctl?.setDistrictsVisible(app.showDistricts))
  $effect(() => {
    const y = app.year
    if (!y) return
    let cancelled = false
    loadDistricts(y).then((fc) => {
      if (cancelled || !fc) return
      app.districts = fc
      ctl?.setDistricts(fc)
    })
    return () => {
      cancelled = true
    }
  })
  $effect(() => ctl?.setSelected(app.selected?.dataset ?? null, app.selected?.id ?? null))

  /** Used by the search box and the detail panel. */
  export function flyTo(lon: number, lat: number) {
    ctl?.flyTo(lon, lat)
  }

  export function fitDistrict(leaid: string) {
    ctl?.fitDistrict(leaid)
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
