<script lang="ts">
  import { app, basemap } from '../lib/app.svelte'
  import { BASEMAPS, basemapById } from '../lib/basemaps'
  import { theme, type ThemePref } from '../lib/theme.svelte'
  import Search from './Search.svelte'

  let { onPick }: { onPick: (dataset: 'public' | 'private' | 'college', id: string, lon: number, lat: number) => void } = $props()

  const themes: { id: ThemePref; label: string }[] = [
    { id: 'system', label: 'System' },
    { id: 'light', label: 'Light' },
    { id: 'dark', label: 'Dark' },
  ]
  const current = $derived(basemapById(basemap.id))
</script>

<header class="bar">
  <h1>{app.state?.site_title ?? 'Education Explorer'}</h1>
  <Search {onPick} />
  <div class="group" role="group" aria-label="Theme">
    {#each themes as t}
      <button class="seg" class:on={theme.pref === t.id} aria-pressed={theme.pref === t.id} onclick={() => (theme.pref = t.id)}>
        {t.label}
      </button>
    {/each}
  </div>
  <label class="bm">
    <span class="sr-only">Basemap</span>
    <select
      value={basemap.id}
      onchange={(e) => (app.basemapChoice = (e.currentTarget as HTMLSelectElement).value as typeof app.basemapChoice)}
      aria-describedby="bm-note"
    >
      {#each BASEMAPS as b}
        <option value={b.id}>{b.label}</option>
      {/each}
    </select>
  </label>
  <span id="bm-note" class="sr-only">{current?.note ?? ''}</span>
  <a class="link" href="./methodology.html">Data &amp; methods</a>
</header>

<style>
  .bar {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 8px 14px;
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    flex-wrap: wrap;
  }
  h1 {
    font-size: 17px;
    margin: 0 8px 0 0;
    white-space: nowrap;
  }
  .group {
    display: inline-flex;
    border: 1px solid var(--border);
    border-radius: 8px;
    overflow: hidden;
  }
  .seg {
    background: var(--surface);
    border: 0;
    padding: 5px 11px;
  }
  .seg + .seg {
    border-left: 1px solid var(--border);
  }
  .seg.on {
    background: var(--accent);
    color: var(--accent-text);
  }
  select {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 5px 8px;
  }
  .link {
    color: var(--accent);
    margin-left: auto;
  }
  @media (max-width: 720px) {
    h1 {
      font-size: 15px;
      flex-basis: 100%;
    }
    .link {
      display: none;
    }
    .bar {
      gap: 8px;
      padding: 6px 10px;
    }
    .seg {
      padding: 4px 8px;
    }
  }
</style>
