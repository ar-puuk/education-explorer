<script lang="ts">
  import { app } from '../lib/app.svelte'
  import { DATASET_LABEL, legendSvg, type Dataset } from '../lib/icons'
  import { CATEGORIES } from '../lib/colorby'
  import Drawer from './Drawer.svelte'
  import Section from './Section.svelte'

  const datasets: Dataset[] = ['public', 'private', 'college']
  const colorModes: { id: typeof app.colorBy; label: string }[] = [
    { id: 'dataset', label: 'One colour' },
    { id: 'level', label: 'Level' },
    { id: 'charter', label: 'Charter' },
    { id: 'locale', label: 'Locale' },
  ]
  const on = $derived(datasets.filter((d) => app.layers[d]).length)
</script>

<Drawer id="layers" title="Layers">
  <Section title="Datasets" meta={`${on} of 3 on`} open>
    {#each datasets as d}
      <label class="row">
        <!-- eslint-disable-next-line svelte/no-at-html-tags -->
        <span class="shape">{@html legendSvg(d)}</span>
        <span class="grow">{DATASET_LABEL[d]}</span>
        <input class="switch" type="checkbox" role="switch" bind:checked={app.layers[d]} />
      </label>
    {/each}
    <p class="hint">Each layer has its own shape as well as colour. Dashed, faded markers were not operating that year.</p>
  </Section>

  <Section title="Public school markers" meta={colorModes.find((m) => m.id === app.colorBy)?.label} open>
    <div class="pills" role="group" aria-label="Colour public schools by">
      {#each colorModes as m}
        <button class:on={app.colorBy === m.id} aria-pressed={app.colorBy === m.id} onclick={() => (app.colorBy = m.id)}>{m.label}</button>
      {/each}
    </div>
    {#if app.colorBy !== 'dataset'}
      <ul class="legend" aria-label="Marker colours for public schools">
        {#each CATEGORIES[app.colorBy] as c, i}
          <li><span class="sw" style={`background: var(--chart-${i + 1})`}></span>{c.label}</li>
        {/each}
      </ul>
    {/if}
    <label class="row"><span class="grow">Size markers by enrollment</span><input class="switch" type="checkbox" role="switch" bind:checked={app.sizeByEnroll} /></label>
    <label class="row"><span class="grow">Include closed or not yet open</span><input class="switch" type="checkbox" role="switch" bind:checked={app.includeClosed} /></label>
  </Section>

  <Section title="Boundaries" meta={app.showDistricts ? 'on' : 'off'}>
    <label class="row"><span class="grow">School districts</span><input class="switch" type="checkbox" role="switch" bind:checked={app.showDistricts} /></label>
    <p class="hint">Census TIGER/Line boundaries for the selected school year. Click a district for its enrollment, staff, finance and schools.</p>
  </Section>
</Drawer>

<style>
  .row {
    display: flex;
    align-items: center;
    gap: 10px;
    min-height: 28px;
  }
  .grow {
    flex: 1;
  }
  .shape {
    display: inline-flex;
    width: 18px;
  }
  .hint {
    color: var(--muted);
    font-size: 12px;
    margin: 0;
  }
  .pills {
    display: flex;
    flex-wrap: wrap;
    gap: 5px;
  }
  .pills button {
    padding: 3px 10px;
    border-radius: 99px;
    border: 1px solid var(--border);
    background: var(--surface);
    color: var(--muted);
    font-size: 12.5px;
  }
  .pills button.on {
    background: var(--accent);
    color: var(--accent-text);
    border-color: var(--accent);
  }
  .legend {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 3px 10px;
    font-size: 12.5px;
  }
  .legend li {
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .sw {
    width: 11px;
    height: 11px;
    border-radius: 50%;
    border: 1px solid var(--ring);
    flex: none;
  }
  .switch {
    appearance: none;
    width: 32px;
    height: 19px;
    border-radius: 99px;
    background: var(--border);
    position: relative;
    margin: 0;
    flex: none;
    cursor: pointer;
    transition: background 0.15s;
  }
  .switch::after {
    content: '';
    position: absolute;
    top: 2px;
    left: 2px;
    width: 15px;
    height: 15px;
    border-radius: 50%;
    background: var(--surface);
    box-shadow: 0 1px 2px rgb(0 0 0 / 30%);
    transition: left 0.15s;
  }
  .switch:checked {
    background: var(--accent);
  }
  .switch:checked::after {
    left: 15px;
    background: var(--accent-text);
  }
</style>
