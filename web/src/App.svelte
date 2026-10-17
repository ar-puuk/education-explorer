<script lang="ts">
  import { onMount } from 'svelte'
  import { app, applyUrl, currentUrlState, readUrl, urlFor } from './lib/app.svelte'
  import { loadPublicPoints, loadState, loadYears, setAvailable } from './lib/data'
  import { warmUp } from './lib/db'
  import DetailPanel from './components/DetailPanel.svelte'
  import MapView from './components/MapView.svelte'
  import Sidebar from './components/Sidebar.svelte'
  import TopBar from './components/TopBar.svelte'
  import YearSlider from './components/YearSlider.svelte'

  let map = $state<MapView>()
  let defaultYear = 0

  onMount(async () => {
    try {
      const [state, years, points] = await Promise.all([loadState(), loadYears(), loadPublicPoints()])
      app.state = state
      app.years = years
      setAvailable(years)
      app.points = points
      defaultYear = points.years[points.years.length - 1]
      // Default to the latest year that is not just a preliminary directory (membership exists).
      const withMembership = years.ccd?.membership?.years ?? points.years
      defaultYear = withMembership[withMembership.length - 1] ?? defaultYear
      app.year = defaultYear
      applyUrl(readUrl())
      if (!points.years.includes(app.year)) app.year = defaultYear
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

  function pick(id: string, lon: number, lat: number) {
    app.selected = { dataset: 'public', id }
    map?.flyTo(lon, lat)
    // make sure the school is visible in the current year
    const s = app.points?.schools.find((x) => x.id === id)
    if (s && !s.years.includes(app.year)) app.year = s.years[s.years.length - 1]
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
      <DetailPanel />
      <YearSlider />
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
