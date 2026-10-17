<script lang="ts">
  import { app } from '../lib/app.svelte'
  import type { Selectable } from '../lib/icons'

  let { dataset, id }: { dataset: Selectable; id: string } = $props()

  const inSet = $derived(app.compare.some((c) => c.dataset === dataset && c.id === id))
  const full = $derived(app.compare.length >= 6)

  function toggle() {
    if (inSet) app.compare = app.compare.filter((c) => !(c.dataset === dataset && c.id === id))
    else if (!full) app.compare = [...app.compare, { dataset, id }]
  }
</script>

<button class="cmp" class:on={inSet} onclick={toggle} disabled={!inSet && full} aria-pressed={inSet}
  title={full && !inSet ? 'Compare holds up to six places' : 'Overlay this place with others in the Compare view'}>
  {inSet ? '✓ In compare' : '+ Compare'}
</button>

<style>
  button {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 7px;
    padding: 0 10px;
    min-height: 26px;
    font-size: 12.5px;
    font-weight: 500;
    white-space: nowrap;
  }
  button:hover {
    background: var(--surface-2);
  }
  .on,
  .on:hover {
    background: var(--accent);
    color: var(--accent-text);
    border-color: var(--accent);
  }
</style>
