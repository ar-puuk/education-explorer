<script lang="ts">
  import { tooltip } from '../lib/tooltip'
  export interface Kpi {
    label: string
    value: string | null
    sub?: string
    title?: string
  }
  let { items }: { items: Kpi[] } = $props()
</script>

<dl class="kpis">
  {#each items as k}
    <div class="kpi" use:tooltip={k.title}>
      <dt>{k.label}</dt>
      <dd class:none={k.value == null}>{k.value ?? '—'}</dd>
      {#if k.sub}<dd class="sub">{k.sub}</dd>{/if}
    </div>
  {/each}
</dl>

<style>
  .kpis {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(92px, 1fr));
    margin: 0;
    border: 1px solid var(--border);
    border-radius: 10px;
    overflow: hidden;
    background: var(--surface);
  }
  .kpi {
    padding: 9px 12px;
    display: flex;
    flex-direction: column;
    gap: 1px;
    border-right: 1px solid var(--border);
    border-bottom: 1px solid var(--border);
    margin: 0 -1px -1px 0;
    min-width: 0;
  }
  dt {
    color: var(--muted);
    font-size: 11.5px;
  }
  dd {
    margin: 0;
    font: 500 20px/1.2 var(--f-data);
    letter-spacing: -0.02em;
  }
  dd.none {
    color: var(--muted);
  }
  dd.sub {
    font: 11px var(--f-data);
    letter-spacing: 0;
    color: var(--muted);
  }
</style>
