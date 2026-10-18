<script lang="ts">
  import { app } from '../lib/app.svelte'
  import { DATASET_LABEL, legendSvg, type Dataset } from '../lib/icons'
  import { visibleColleges, visiblePrivate, visiblePublic } from '../lib/filters'
  import { fmtInt } from '../lib/labels'
  import { theme, type ThemePref } from '../lib/theme.svelte'
  import Icon, { type IconName } from './Icon.svelte'
  import Search from './Search.svelte'

  let { onPick }: { onPick: (dataset: 'public' | 'private' | 'college' | 'district', id: string, lon: number, lat: number) => void } = $props()

  const counts = $derived({
    public: visiblePublic().length,
    private: visiblePrivate().length,
    college: visibleColleges().length,
  } satisfies Record<Dataset, number>)

  const chips: { id: Dataset; label: string }[] = [
    { id: 'public', label: 'Public schools' },
    { id: 'private', label: 'Private' },
    { id: 'college', label: 'Colleges' },
  ]
  const themes: { id: ThemePref; label: string; icon: IconName }[] = [
    { id: 'system', label: 'System theme', icon: 'monitor' },
    { id: 'light', label: 'Light theme', icon: 'sun' },
    { id: 'dark', label: 'Dark theme', icon: 'moon' },
  ]
</script>

<header class="bar">
  <div class="brand">
    <span class="mark"><Icon name="cap" size={14} /></span>
    <h1>{app.state?.site_title ?? 'Education Explorer'}</h1>
  </div>
  <Search {onPick} />
  <div class="chips" role="group" aria-label="Datasets on the map">
    {#each chips as c}
      <button class="dchip" aria-pressed={app.layers[c.id]} onclick={() => (app.layers[c.id] = !app.layers[c.id])} title={DATASET_LABEL[c.id]}>
        <!-- eslint-disable-next-line svelte/no-at-html-tags -->
        <span class="shape">{@html legendSvg(c.id, 20)}</span>
        {c.label}
        <b>{fmtInt(counts[c.id])}</b>
      </button>
    {/each}
  </div>
  <div class="themes" role="group" aria-label="Theme">
    {#each themes as t}
      <button class="iconbtn" aria-pressed={theme.pref === t.id} title={t.label} aria-label={t.label} onclick={() => (theme.pref = t.id)}>
        <Icon name={t.icon} size={15} />
      </button>
    {/each}
  </div>
</header>

<style>
  .bar {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 8px 14px;
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    position: relative;
    z-index: 8;
    min-height: 52px;
  }
  .brand {
    display: flex;
    align-items: center;
    gap: 9px;
  }
  .mark {
    width: 24px;
    height: 24px;
    border-radius: 7px;
    background: var(--accent);
    color: var(--accent-text);
    display: grid;
    place-items: center;
  }
  h1 {
    font: 700 17px var(--f-display);
    letter-spacing: -0.015em;
    margin: 0;
    white-space: nowrap;
  }
  .chips {
    display: flex;
    gap: 6px;
    margin-left: auto;
  }
  .dchip {
    display: flex;
    align-items: center;
    gap: 7px;
    height: 32px;
    padding: 0 12px;
    border-radius: 999px;
    border: 1px solid var(--border);
    background: var(--surface);
    font-weight: 500;
    white-space: nowrap;
  }
  .dchip b {
    font: 500 11.5px var(--f-data);
    color: var(--muted);
  }
  .shape {
    display: inline-flex;
  }
  .dchip[aria-pressed='true'] {
    border-color: var(--accent);
    background: var(--surface-2);
  }
  .dchip[aria-pressed='false'] {
    color: var(--muted);
  }
  .dchip[aria-pressed='false'] .shape {
    opacity: 0.4;
  }
  .themes {
    display: flex;
    gap: 2px;
    padding: 2px;
    border: 1px solid var(--border);
    border-radius: 10px;
  }
  .themes .iconbtn {
    width: 28px;
    height: 28px;
  }
  @media (max-width: 900px) {
    .dchip b {
      display: none;
    }
  }
  @media (max-width: 720px) {
    .bar {
      flex-wrap: wrap;
      gap: 8px;
      padding: 6px 10px;
    }
    h1 {
      font-size: 15px;
    }
    .chips {
      order: 3;
      margin-left: 0;
      flex-basis: 100%;
      overflow-x: auto;
    }
    .themes {
      margin-left: auto;
    }
  }
</style>
