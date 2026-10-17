<script lang="ts">
  import { app, basemap } from '../lib/app.svelte'
  import { BASEMAPS, basemapById, defaultBasemap, type BasemapId } from '../lib/basemaps'
  import { theme, type ThemePref } from '../lib/theme.svelte'
  import Drawer from './Drawer.svelte'
  import Icon, { type IconName } from './Icon.svelte'
  import Section from './Section.svelte'

  const themes: { id: ThemePref; label: string; icon: IconName }[] = [
    { id: 'system', label: 'System', icon: 'monitor' },
    { id: 'light', label: 'Light', icon: 'sun' },
    { id: 'dark', label: 'Dark', icon: 'moon' },
  ]
  /** Swatches stand in for each style; they are previews only. */
  const SWATCH: Record<BasemapId, string> = {
    positron: 'linear-gradient(135deg,#f2f2f0 55%,#d6e3ec 55%)',
    dark: 'linear-gradient(135deg,#1c2026 55%,#0f2233 55%)',
    liberty: 'linear-gradient(135deg,#eef3e3 55%,#9cc7e6 55%)',
    bright: 'linear-gradient(135deg,#fbf6e9 55%,#79b8e6 55%)',
    fiord: 'linear-gradient(135deg,#45517a 55%,#2d3659 55%)',
  }
  const autoTarget = $derived(basemapById(defaultBasemap(theme.effective))?.label)
  const current = $derived(basemapById(basemap.id))
</script>

<Drawer id="basemap" title="Basemap & appearance">
  <Section title="Appearance" meta={theme.pref} open>
    <div class="seg" role="radiogroup" aria-label="Colour theme">
      {#each themes as t}
        <button role="radio" aria-checked={theme.pref === t.id} class:on={theme.pref === t.id} onclick={() => (theme.pref = t.id)}>
          <Icon name={t.icon} size={14} />{t.label}
        </button>
      {/each}
    </div>
  </Section>

  <Section title="Basemap" meta={current?.label} open>
    <div class="grid" role="radiogroup" aria-label="Basemap style">
      <button class="card-b" role="radio" aria-checked={app.basemapChoice === null} onclick={() => (app.basemapChoice = null)}>
        <span class="sw auto" aria-hidden="true"></span>
        <span class="nm">Auto</span>
        <span class="sub">Follows theme · {autoTarget}</span>
      </button>
      {#each BASEMAPS as b}
        <button class="card-b" role="radio" aria-checked={app.basemapChoice === b.id} onclick={() => (app.basemapChoice = b.id)} title={b.note}>
          <span class="sw" style:background={SWATCH[b.id]} aria-hidden="true"></span>
          <span class="nm">{b.label}</span>
        </button>
      {/each}
    </div>
    {#if current?.note}<p class="hint">{current.label}: {current.note}</p>{/if}
    <p class="hint">Basemaps are OpenFreeMap vector styles, free and without an API key.</p>
  </Section>
</Drawer>

<style>
  .seg {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    border: 1px solid var(--border);
    border-radius: 9px;
    overflow: hidden;
  }
  .seg button {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    padding: 7px 4px;
    border: 0;
    background: var(--surface);
    color: var(--muted);
  }
  .seg button + button {
    border-left: 1px solid var(--border);
  }
  .seg button.on {
    background: var(--accent);
    color: var(--accent-text);
  }
  .grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
  }
  .card-b {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 2px;
    padding: 6px;
    text-align: left;
    border: 1px solid var(--border);
    border-radius: 10px;
    background: var(--surface);
  }
  .card-b[aria-checked='true'] {
    border-color: var(--accent);
    box-shadow: inset 0 0 0 1px var(--accent);
  }
  .sw {
    width: 100%;
    height: 46px;
    border-radius: 6px;
    border: 1px solid var(--border);
  }
  .sw.auto {
    background: linear-gradient(135deg, #f2f2f0 50%, #1c2026 50%);
  }
  .nm {
    font-weight: 600;
    padding: 2px 2px 0;
  }
  .sub {
    color: var(--muted);
    font-size: 11.5px;
    padding: 0 2px 2px;
  }
  .hint {
    color: var(--muted);
    font-size: 12px;
    margin: 0;
  }
</style>
