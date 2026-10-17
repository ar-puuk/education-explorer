<script lang="ts">
  import { onMount } from 'svelte'
  import { allYears, app, applyUrl, readUrl, urlFor } from './lib/app.svelte'
  import { loadCollegePoints, loadPrivatePoints, loadPublicPoints, loadState, loadYears, setAvailable } from './lib/data'
  import { warmUp } from './lib/db'
  import CompareView from './components/CompareView.svelte'
  import DetailPanel from './components/DetailPanel.svelte'
  import MapView from './components/MapView.svelte'
  import Sidebar from './components/Sidebar.svelte'
  import TableView from './components/TableView.svelte'
  import TopBar from './components/TopBar.svelte'
  import YearSlider from './components/YearSlider.svelte'

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

<div class="shell">
  <TopBar onPick={pick} />
  <main>
    {#if app.error}
      <div class="fail" role="alert">
        <h2>Could not load the data</h2>
        <p>{app.error}</p>
      </div>
    {:else if app.ready}
      <MapView bind:this={map} />
      <Sidebar />
      <DetailPanel onSelectSchool={(id, lon, lat) => pick('public', id, lon, lat)} />
      <YearSlider />
      <TableView />
      <CompareView />
    {:else}
      <p class="loading">Loading…</p>
    {/if}
  </main>
  <footer>
    Data: U.S. Dept. of Education, NCES Common Core of Data (public schools); U.S. Census Bureau (geocoding &amp;
    boundaries). Basemap: OpenFreeMap, OpenMapTiles &copy; OpenStreetMap contributors. Statistical use only; this
    site does not rank or evaluate schools.
    <a href="./methodology.html">Sources, versions and caveats</a>
  </footer>
</div>

<style>
  .shell {
    display: grid;
    grid-template-rows: auto 1fr auto;
    height: 100%;
  }
  main {
    position: relative;
    min-height: 0;
  }
  footer {
    padding: 4px 14px;
    font-size: 11.5px;
    color: var(--muted);
    background: var(--surface);
    border-top: 1px solid var(--border);
  }
  footer a {
    color: var(--accent);
  }
  .loading,
  .fail {
    padding: 24px;
  }
</style>
