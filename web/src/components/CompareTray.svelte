<script lang="ts">
  import { app } from '../lib/app.svelte'
  import { DATASET_COLOR, placeName } from '../lib/place'
  import Icon from './Icon.svelte'

  const MAX = 6
  const items = $derived(app.compare.map((c) => ({ ...c, name: placeName(c.dataset, c.id) })))

  function remove(i: number) {
    app.compare = app.compare.filter((_, j) => j !== i)
  }
</script>

{#if items.length}
  <section class="panel tray" aria-label="Places to compare">
    <span class="lbl">Compare <b>{items.length}/{MAX}</b></span>
    <ul>
      {#each items as it, i (it.dataset + it.id)}
        <li>
          <button class="chip" onclick={() => (app.selected = { dataset: it.dataset, id: it.id })} title={`Show ${it.name}`}>
            <span class="dot" style:background={DATASET_COLOR[it.dataset]}></span>{it.name}
          </button>
          <button class="x" onclick={() => remove(i)} aria-label={`Remove ${it.name} from compare`}><Icon name="x" size={12} /></button>
        </li>
      {/each}
    </ul>
    <button class="link" onclick={() => (app.compare = [])}>Clear</button>
    <button class="btn pri" onclick={() => (app.showCompare = true)}>
      <Icon name="compare" size={14} />{items.length > 1 ? 'Compare' : 'Open'}
    </button>
  </section>
{/if}

<style>
  .tray {
    position: absolute;
    z-index: 7;
    left: calc(var(--drawer-w, 68px) + 12px);
    right: calc(var(--insp-w, 0px) + 12px);
    bottom: 46px;
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 6px 8px 6px 14px;
    border-radius: 12px;
    transition:
      left 0.18s ease,
      right 0.18s ease;
  }
  .lbl {
    font-weight: 600;
    white-space: nowrap;
  }
  .lbl b {
    font: 400 11.5px var(--f-data);
    color: var(--muted);
  }
  ul {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    gap: 6px;
    flex: 1;
    min-width: 0;
    overflow-x: auto;
    scrollbar-width: none;
  }
  li {
    display: inline-flex;
    align-items: center;
    flex: none;
    border: 1px solid var(--border);
    border-radius: 999px;
    background: var(--surface-2);
  }
  .chip {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: none;
    border: 0;
    padding: 3px 4px 3px 10px;
    max-width: 220px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: 12.5px;
  }
  .dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex: none;
  }
  .x {
    display: grid;
    place-items: center;
    width: 22px;
    height: 22px;
    margin-right: 2px;
    border: 0;
    border-radius: 50%;
    background: none;
    color: var(--muted);
    padding: 0;
  }
  .x:hover {
    background: var(--border);
    color: var(--text);
  }
  @media (max-width: 720px) {
    .tray {
      left: 0;
      right: 0;
      bottom: 0;
      border-radius: 0;
      border-width: 1px 0 0;
      box-shadow: none;
      padding: 6px 10px;
      z-index: 25;
    }
    .lbl {
      display: none;
    }
  }
</style>
