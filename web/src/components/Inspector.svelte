<script lang="ts">
  import type { Snippet } from 'svelte'
  import { app } from '../lib/app.svelte'
  import type { Dataset } from '../lib/icons'
  import Icon from './Icon.svelte'

  interface Props {
    label: string
    /** shown above the title, e.g. "Public school" */
    kind: string
    dataset: Dataset | 'district'
    title: string
    sub?: Snippet
    tags?: string[]
    tabs: { id: string; label: string }[]
    tab: string
    actions?: Snippet
    children: Snippet
  }
  let { label, kind, dataset, title, sub, tags = [], tabs, tab = $bindable(), actions, children }: Props = $props()

  const color = $derived(dataset === 'district' ? 'var(--muted)' : `var(--c-${dataset})`)

  let body: HTMLDivElement | undefined = $state()
  // reset scroll when the place or the tab changes
  $effect(() => {
    tab
    title
    body?.scrollTo({ top: 0 })
  })

  function key(e: KeyboardEvent) {
    const i = tabs.findIndex((t) => t.id === tab)
    let n = i
    if (e.key === 'ArrowRight') n = (i + 1) % tabs.length
    else if (e.key === 'ArrowLeft') n = (i - 1 + tabs.length) % tabs.length
    else if (e.key === 'Home') n = 0
    else if (e.key === 'End') n = tabs.length - 1
    else return
    e.preventDefault()
    tab = tabs[n].id
    ;(e.currentTarget as HTMLElement).querySelectorAll<HTMLElement>('[role=tab]')[n]?.focus()
  }
</script>

<aside class="panel insp" class:wide={app.inspectorWide} aria-label={label}>
  <header class="ih">
    <div class="hd">
      <span class="kind"><span class="dot" style:background={color}></span>{kind}</span>
      <h2>{title}</h2>
      {#if sub}<p class="sub">{@render sub()}</p>{/if}
      {#if tags.length}
        <div class="tags">{#each tags as t}<span class="tag">{t}</span>{/each}</div>
      {/if}
      {#if actions}<div class="hactions">{@render actions()}</div>{/if}
    </div>
    <div class="acts">
      <button class="iconbtn expand" onclick={() => (app.inspectorWide = !app.inspectorWide)} aria-label={app.inspectorWide ? 'Shrink panel' : 'Expand panel'} aria-pressed={app.inspectorWide} title={app.inspectorWide ? 'Shrink' : 'Expand to workspace'}>
        <Icon name={app.inspectorWide ? 'shrink' : 'expand'} />
      </button>
      <button class="iconbtn" onclick={() => (app.selected = null)} aria-label="Close details"><Icon name="x" /></button>
    </div>
  </header>
  <div class="tabrow">
    <div class="tabs" role="tablist" aria-label={`${label} sections`} tabindex="-1" onkeydown={key}>
      {#each tabs as t}
        <button role="tab" id={`tab-${t.id}`} aria-selected={tab === t.id} aria-controls="insp-panel" tabindex={tab === t.id ? 0 : -1} onclick={() => (tab = t.id)}>{t.label}</button>
      {/each}
    </div>
  </div>
  <div class="body" id="insp-panel" role="tabpanel" aria-labelledby={`tab-${tab}`} bind:this={body} tabindex="0">
    {@render children()}
  </div>
</aside>

<style>
  .insp {
    position: absolute;
    z-index: 6;
    top: 12px;
    right: 12px;
    bottom: 12px;
    width: 444px;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    transition: width 0.18s ease;
  }
  .insp.wide {
    width: min(960px, calc(100% - 24px));
    z-index: 9;
  }
  .ih {
    display: flex;
    justify-content: space-between;
    gap: 10px;
    padding: 14px 10px 6px 18px;
  }
  .hd {
    min-width: 0;
  }
  .kind {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font: 500 11px var(--f-data);
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--muted);
  }
  .dot {
    width: 9px;
    height: 9px;
    border-radius: 50%;
  }
  h2 {
    font: 700 21px/1.15 var(--f-display);
    letter-spacing: -0.015em;
    margin: 4px 0 2px;
    text-wrap: balance;
  }
  .sub {
    margin: 0;
    color: var(--muted);
    font-size: 12.5px;
  }
  .tags {
    display: flex;
    flex-wrap: wrap;
    gap: 5px;
    margin-top: 8px;
  }
  .tag {
    font-size: 11.5px;
    padding: 1px 8px;
    border-radius: 6px;
    background: var(--surface-2);
    border: 1px solid var(--border);
  }
  .acts {
    display: flex;
    gap: 2px;
    flex: none;
  }
  .tabrow {
    display: flex;
    align-items: flex-end;
    gap: 8px;
    padding: 0 10px 0 12px;
    border-bottom: 1px solid var(--border);
    margin-top: 8px;
  }
  .tabs {
    display: flex;
    gap: 2px;
    overflow-x: auto;
    overflow-y: hidden;
    scrollbar-width: none;
    min-width: 0;
  }
  .tabs::-webkit-scrollbar {
    display: none;
  }
  .tabs button {
    background: none;
    border: 0;
    padding: 9px 11px;
    color: var(--muted);
    font-weight: 500;
    border-bottom: 2px solid transparent;
    margin-bottom: -1px;
    white-space: nowrap;
  }
  .tabs button[aria-selected='true'] {
    color: var(--text);
    border-bottom-color: var(--accent);
  }
  .tabs button:hover {
    color: var(--text);
  }
  .hactions {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-top: 10px;
  }
  .body {
    flex: 1;
    overflow: auto;
    padding: 14px 16px 18px;
    display: flex;
    flex-direction: column;
    gap: 14px;
    background: var(--bg);
  }
  .body :global(.tabbody) {
    display: grid;
    grid-template-columns: minmax(0, 1fr);
    gap: 14px;
  }
  .wide .body :global(.tabbody) {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .wide .body :global(.tabbody > .span) {
    grid-column: 1 / -1;
  }
  @media (max-width: 720px) {
    .insp,
    .insp.wide {
      top: auto;
      left: 0;
      right: 0;
      bottom: 0;
      width: auto;
      height: 64%;
      border-radius: 16px 16px 0 0;
      z-index: 20;
    }
    .expand {
      display: none;
    }
    .ih {
      padding-top: 12px;
    }
    h2 {
      font-size: 18px;
    }
  }
</style>
