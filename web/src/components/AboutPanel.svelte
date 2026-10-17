<script lang="ts">
  import Drawer from './Drawer.svelte'
</script>

<Drawer id="about" title="About the data">
  <div class="body">
    <p>
      Public schools and districts come from the U.S. Dept. of Education, NCES Common Core of Data. Private schools come
      from the Private School Universe Survey. Colleges come from IPEDS. Geocoding and district boundaries are from the
      U.S. Census Bureau.
    </p>
    <p class="strong">This site does not rank or evaluate schools. Figures are for statistical use only.</p>
    <p><a href="./methodology.html">Sources, versions and caveats</a></p>
    <h3>Keyboard</h3>
    <dl>
      <dt><kbd>Ctrl</kbd> <kbd>K</kbd></dt><dd>Search</dd>
      <dt><kbd>←</kbd> <kbd>→</kbd></dt><dd>Step the year when the timeline has focus</dd>
      <dt><kbd>Esc</kbd></dt><dd>Close the open panel</dd>
    </dl>
    <p class="small">Basemap: OpenFreeMap, OpenMapTiles &copy; OpenStreetMap contributors.</p>
  </div>
</Drawer>

<style>
  .body {
    padding: 0 16px 16px;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  p {
    margin: 0;
  }
  .strong {
    font-weight: 600;
  }
  .small {
    color: var(--muted);
    font-size: 12px;
  }
  h3 {
    font: 600 13px var(--f-body);
    margin: 4px 0 0;
  }
  dl {
    display: grid;
    grid-template-columns: max-content 1fr;
    gap: 6px 12px;
    margin: 0;
  }
  dd {
    margin: 0;
    color: var(--muted);
  }
  kbd {
    font: 11px var(--f-data);
    border: 1px solid var(--border);
    border-bottom-width: 2px;
    border-radius: 4px;
    padding: 0 5px;
    background: var(--surface-2);
  }
</style>
