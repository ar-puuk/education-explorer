<script lang="ts">
  import { app } from '../lib/app.svelte'
  import { DATASET_LABEL, legendSvg, type Dataset } from '../lib/icons'
  import { levelLabel } from '../lib/labels'

  const datasets: { id: Dataset; ready: boolean }[] = [
    { id: 'public', ready: true },
    { id: 'private', ready: false },
    { id: 'college', ready: true },
  ]

  const levels = $derived.by(() => {
    const set = new Set<string>()
    for (const s of app.points?.schools ?? []) set.add(levelLabel(s.level))
    return [...set].sort()
  })

  const controls = $derived.by(() => {
    const labels = app.college?.labels.control ?? {}
    return [1, 2, 3].map((c) => ({ code: c, label: labels[String(c)] ?? String(c) }))
  })

  function toggleControl(c: number) {
    app.collegeControls = app.collegeControls.includes(c) ? app.collegeControls.filter((x) => x !== c) : [...app.collegeControls, c]
  }

  function toggleLevel(l: string) {
    app.levels = app.levels.includes(l) ? app.levels.filter((x) => x !== l) : [...app.levels, l]
  }
</script>

<aside class="side" aria-label="Layers and filters">
  <button class="collapse" onclick={() => (app.panelOpen = !app.panelOpen)} aria-expanded={app.panelOpen}>
    {app.panelOpen ? 'Hide' : 'Layers & filters'}
  </button>
  {#if app.panelOpen}
    <section>
      <h2>Layers</h2>
      {#each datasets as d}
        <label class="row" class:off={!d.ready}>
          <input
            type="checkbox"
            checked={app.layers[d.id]}
            disabled={!d.ready}
            onchange={(e) => (app.layers[d.id] = (e.currentTarget as HTMLInputElement).checked)}
          />
          <!-- eslint-disable-next-line svelte/no-at-html-tags -->
          {@html legendSvg(d.id)}
          <span>{DATASET_LABEL[d.id]}{d.ready ? '' : ' (not loaded yet)'}</span>
        </label>
      {/each}
      <p class="hint">
        Each layer has its own shape as well as colour. Dashed, faded markers are schools that were not operating
        that year.
      </p>
    </section>

    <section>
      <h2>Public schools &amp; shared options</h2>
      <label class="row">
        <input type="checkbox" bind:checked={app.includeClosed} />
        <span>Include closed / inactive / not yet open</span>
      </label>
      <label class="row">
        <input type="checkbox" bind:checked={app.sizeByEnroll} />
        <span>Marker size by enrollment</span>
      </label>
      <label class="field">
        <span>Charter</span>
        <select bind:value={app.charter}>
          <option value="all">All</option>
          <option value="yes">Charter only</option>
          <option value="no">Non-charter only</option>
        </select>
      </label>
      <fieldset>
        <legend>School level</legend>
        {#each levels as l}
          <label class="row">
            <input type="checkbox" checked={app.levels.includes(l)} onchange={() => toggleLevel(l)} />
            <span>{l}</span>
          </label>
        {/each}
        {#if app.levels.length}
          <button class="link" onclick={() => (app.levels = [])}>Clear levels</button>
        {/if}
      </fieldset>
    </section>

    <section>
      <h2>Colleges</h2>
      <fieldset>
        <legend>Control</legend>
        {#each controls as c}
          <label class="row">
            <input type="checkbox" checked={app.collegeControls.includes(c.code)} onchange={() => toggleControl(c.code)} />
            <span>{c.label}</span>
          </label>
        {/each}
        {#if app.collegeControls.length}
          <button class="link" onclick={() => (app.collegeControls = [])}>Show all</button>
        {/if}
      </fieldset>
      <p class="hint">Colleges before 2008 have no map location in the NCES data unless they were still open later.</p>
    </section>
  {/if}
</aside>

<style>
  .side {
    position: absolute;
    z-index: 5;
    top: 12px;
    left: 12px;
    width: 260px;
    max-height: calc(100% - 100px);
    overflow: auto;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    box-shadow: var(--shadow);
    padding: 8px 12px 12px;
  }
  h2 {
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--muted);
    margin: 10px 0 6px;
  }
  .row {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 3px 0;
  }
  .row.off {
    opacity: 0.55;
  }
  .hint {
    color: var(--muted);
    font-size: 12px;
    margin: 6px 0 0;
  }
  .field {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 8px;
    margin: 6px 0;
  }
  select {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 3px 6px;
  }
  fieldset {
    border: 0;
    padding: 0;
    margin: 6px 0 0;
  }
  legend {
    padding: 0;
    margin-bottom: 2px;
  }
  .collapse,
  .link {
    background: none;
    border: 0;
    color: var(--accent);
    padding: 2px 0;
    text-align: left;
  }
  @media (max-width: 720px) {
    .side {
      width: calc(100% - 24px);
      max-height: 45%;
    }
  }
</style>
