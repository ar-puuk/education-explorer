<script lang="ts">
  import type { Snippet } from 'svelte'
  import Icon from './Icon.svelte'

  let { title, meta = '', open = false, children }: { title: string; meta?: string; open?: boolean; children: Snippet } = $props()
</script>

<details class="acc" {open}>
  <summary>
    <span class="t">{title}</span>
    {#if meta}<small>{meta}</small>{/if}
    <span class="ch"><Icon name="chev" size={14} /></span>
  </summary>
  <div class="inner">{@render children()}</div>
</details>

<style>
  .acc {
    border-top: 1px solid var(--border);
  }
  summary {
    list-style: none;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 11px 16px;
    font-weight: 600;
  }
  summary::-webkit-details-marker {
    display: none;
  }
  summary:hover {
    background: var(--surface-2);
  }
  small {
    font: 400 11.5px var(--f-data);
    color: var(--muted);
  }
  .ch {
    margin-left: auto;
    color: var(--muted);
    display: inline-flex;
    transition: transform 0.15s;
  }
  .acc[open] .ch {
    transform: rotate(90deg);
  }
  .inner {
    padding: 0 16px 14px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
</style>
