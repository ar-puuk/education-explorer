<script lang="ts">
  import { app, type Drawer } from '../lib/app.svelte'
  import Icon, { type IconName } from './Icon.svelte'

  const drawers: { id: Drawer; label: string; icon: IconName }[] = [
    { id: 'layers', label: 'Layers', icon: 'layers' },
    { id: 'filters', label: 'Filters', icon: 'filter' },
    { id: 'basemap', label: 'Basemap & appearance', icon: 'map' },
  ]

  function toggle(id: Drawer) {
    app.drawer = app.drawer === id ? null : id
  }
</script>

<nav class="panel rail" aria-label="Tools">
  {#each drawers as d}
    <button class="iconbtn" aria-pressed={app.drawer === d.id} title={d.label} aria-label={d.label} onclick={() => toggle(d.id)}>
      <Icon name={d.icon} size={18} />
    </button>
  {/each}
  <hr />
  <button class="iconbtn" title="Data tables" aria-label="Open data tables" onclick={() => (app.showTable = true)}>
    <Icon name="table" size={18} />
  </button>
  <button class="iconbtn cmp" title="Compare" aria-label={`Open compare${app.compare.length ? `, ${app.compare.length} selected` : ''}`} onclick={() => (app.showCompare = true)}>
    <Icon name="compare" size={18} />
    {#if app.compare.length}<span class="badge">{app.compare.length}</span>{/if}
  </button>
  <hr />
  <button class="iconbtn" aria-pressed={app.drawer === 'about'} title="About the data" aria-label="About the data" onclick={() => toggle('about')}>
    <Icon name="info" size={18} />
  </button>
</nav>

<style>
  .rail {
    position: absolute;
    z-index: 5;
    top: 12px;
    left: 12px;
    width: 46px;
    padding: 6px;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  hr {
    border: 0;
    border-top: 1px solid var(--border);
    margin: 4px 2px;
    width: auto;
  }
  .cmp {
    position: relative;
  }
  .badge {
    position: absolute;
    top: -3px;
    right: -3px;
    min-width: 16px;
    height: 16px;
    padding: 0 4px;
    border-radius: 99px;
    background: var(--c-private);
    color: #fff;
    font: 500 10px/16px var(--f-data);
    text-align: center;
  }
  @media (max-width: 720px) {
    .rail {
      flex-direction: row;
      width: auto;
      left: 8px;
      top: 8px;
    }
    hr {
      border-top: 0;
      border-left: 1px solid var(--border);
      margin: 2px 4px;
      height: auto;
    }
  }
</style>
