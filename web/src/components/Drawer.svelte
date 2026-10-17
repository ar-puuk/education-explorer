<script lang="ts">
  import type { Snippet } from 'svelte'
  import { app, type Drawer } from '../lib/app.svelte'
  import Icon from './Icon.svelte'

  let { id, title, children }: { id: Drawer; title: string; children: Snippet } = $props()
</script>

<aside class="panel drawer" hidden={app.drawer !== id} aria-label={title}>
  <header>
    <h2>{title}</h2>
    <button class="iconbtn" onclick={() => (app.drawer = null)} aria-label={`Close ${title.toLowerCase()}`}><Icon name="x" /></button>
  </header>
  <div class="scroll">{@render children()}</div>
</aside>

<style>
  .drawer {
    position: absolute;
    z-index: 5;
    top: 12px;
    left: 68px;
    width: 304px;
    max-height: calc(100% - 24px);
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  .drawer[hidden] {
    display: none;
  }
  header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 10px 8px 16px;
  }
  h2 {
    font: 700 16px var(--f-display);
    letter-spacing: -0.01em;
    margin: 0;
  }
  .scroll {
    overflow: auto;
    flex: 1;
  }
  @media (max-width: 720px) {
    .drawer {
      left: 8px;
      right: 8px;
      top: auto;
      bottom: calc(8px + var(--tray-h, 0px));
      width: auto;
      max-height: 58%;
      z-index: 15;
    }
  }
</style>
