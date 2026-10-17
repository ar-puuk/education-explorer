<script lang="ts">
  import { onMount } from 'svelte'
  import { allYears, app, applyUrl, readUrl, urlFor } from './lib/app.svelte'
  import { loadCollegePoints, loadPrivatePoints, loadPublicPoints, loadState, loadYears, setAvailable } from './lib/data'
  import { warmUp } from './lib/db'
  import CompareView from './components/CompareView.svelte'
  import DetailPanel from './components/DetailPanel.svelte'
  import MapView from './components/MapView.svelte'
  import AboutPanel from './components/AboutPanel.svelte'
  import BasemapPanel from './components/BasemapPanel.svelte'
  import CompareTray from './components/CompareTray.svelte'
  import FiltersPanel from './components/FiltersPanel.svelte'
  import LayersPanel from './components/LayersPanel.svelte'
  import Rail from './components/Rail.svelte'
  import TableView from './components/TableView.svelte'
  import Timeline from './components/Timeline.svelte'
  import TopBar from './components/TopBar.svelte'

  let map = $state<MapView>()
  let defaultYear = 0

  onMount(async () => {
    try {
      const [state, years, points, college, priv] = await Promise.all([loadState(), loadYears(), loadPublicPoints(), loadCollegePoints(), loadPrivatePoints()])
      app.state = state
      app.years = years
      setAvailable(years)
      app.points = points
      app.college = college
      app.private = priv
      defaultYear = points.years[points.years.length - 1]
      // Default to the latest year that is not just a preliminary directory (membership exists).
      const withMembership = years.ccd?.membership?.years ?? points.years
      defaultYear = withMembership[withMembership.length - 1] ?? defaultYear
      app.year = defaultYear
      applyUrl(readUrl())
      if (!allYears().includes(app.year)) app.year = defaultYear
      document.title = state.site_title
      app.ready = true
      // Load the query engine after first paint.
      setTimeout(() => warmUp().catch(() => {}), 300)
    } catch (e) {
      app.error = String((e as Error).message ?? e)
    }
  })

  // keep the URL in sync with the app state (shareable links)
  $effect(() => {
    if (!app.ready) return
    const qs = urlFor(defaultYear)
    const url = location.pathname + qs + location.hash
    if (url !== location.pathname + location.search + location.hash) history.replaceState(null, '', url)
  })

  const phone = typeof matchMedia === 'function' ? matchMedia('(max-width: 720px)') : null
  $effect(() => {
    if (app.selected && phone?.matches) app.drawer = null
  })
  // the left panels and the inspector push the map controls aside (see app.css)
  const drawerW = $derived(phone?.matches ? 0 : app.drawer ? 68 + 304 + 8 : 68)
  const trayH = $derived(phone?.matches && app.compare.length ? 46 : 0)
  const inspW = $derived(phone?.matches || !app.selected ? 0 : 444 + 12)

  function pick(dataset: 'public' | 'private' | 'college' | 'district', id: string, lon: number, lat: number) {
    app.selected = { dataset, id }
    if (dataset === 'district') {
      app.showDistricts = true
      map?.fitDistrict(id)
      return
    }
    map?.flyTo(lon, lat)
    // make sure the place is visible in the current year
    const years = dataset === 'public'
      ? app.points?.schools.find((x) => x.id === id)?.years
      : dataset === 'private'
        ? app.private?.schools.find((x) => x.id === id)?.years
        : app.college?.institutions.find((x) => x.id === id)?.years
    // PSS years are biennial survey years: any slider year at or after the first survey shows that school
    if (years && dataset === 'private') {
      if (app.year < years[0]) app.year = years[0]
    } else if (years && !years.includes(app.year)) app.year = years[years.length - 1]
    app.layers[dataset] = true
  }
</script>

<svelte:window
  onkeydown={(e) => {
    if (e.key !== 'Escape') return
    if (app.showTable || app.showCompare) {
      app.showTable = false
      app.showCompare = false
    } else if (app.selected && !(e.target instanceof HTMLInputElement)) app.selected = null
    else if (app.drawer && !(e.target instanceof HTMLInputElement)) app.drawer = null
  }}
/>

<div class="shell">
  <TopBar onPick={pick} />
  <main style:--drawer-w={`${drawerW}px`} style:--insp-w={`${inspW}px`} style:--tray-h={`${trayH}px`}>
    {#if app.error}
      <div class="fail" role="alert">
        <h2>Could not load the data</h2>
        <p>{app.error}</p>
      </div>
    {:else if app.ready}
      <MapView bind:this={map} />
      <Rail />
      <LayersPanel />
      <FiltersPanel />
      <BasemapPanel />
      <AboutPanel />
      <DetailPanel onSelectSchool={(id, lon, lat) => pick('public', id, lon, lat)} />
      <CompareTray />
      <TableView />
      <CompareView />
    {:else}
      <p class="loading">Loading…</p>
    {/if}
  </main>
  {#if app.ready}<Timeline />{/if}
</div>

<style>
  .shell {
    display: grid;
    grid-template-rows: auto 1fr auto;
    grid-template-columns: minmax(0, 1fr);
    height: 100%;
  }
  main {
    position: relative;
    min-height: 0;
  }
  .loading,
  .fail {
    padding: 24px;
  }
</style>
