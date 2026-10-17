<script lang="ts">
  import { app } from '../lib/app.svelte'
  import { levelLabel } from '../lib/labels'
  import Drawer from './Drawer.svelte'
  import Section from './Section.svelte'

  const levels = $derived.by(() => {
    const set = new Set<string>()
    for (const s of app.points?.schools ?? []) set.add(levelLabel(s.level))
    return [...set].sort()
  })
  const controls = $derived.by(() => {
    const labels = app.college?.labels.control ?? {}
    return [1, 2, 3].map((c) => ({ code: c, label: labels[String(c)] ?? String(c) }))
  })
  const affils = $derived.by(() => {
    const labels = app.private?.labels.relig ?? {}
    return [1, 2, 3].map((c) => ({ code: c, label: (labels[String(c)] ?? String(c)).replace(/ *\(.*\)/, '') }))
  })

  function toggle<T>(list: T[], v: T): T[] {
    return list.includes(v) ? list.filter((x) => x !== v) : [...list, v]
  }
  const active = $derived((app.charter !== 'all' ? 1 : 0) + (app.levels.length ? 1 : 0) + (app.privateAffil.length ? 1 : 0) + (app.collegeControls.length ? 1 : 0))
  function reset() {
    app.charter = 'all'
    app.levels = []
    app.privateAffil = []
    app.collegeControls = []
  }
  const charterOpts: { id: typeof app.charter; label: string }[] = [
    { id: 'all', label: 'All' },
    { id: 'yes', label: 'Charter only' },
    { id: 'no', label: 'Non-charter' },
  ]
</script>

<Drawer id="filters" title="Filters">
  <div class="bar">
    <span>{active ? `${active} filter${active > 1 ? 's' : ''} active` : 'No filters active'}</span>
    <button class="link" onclick={reset} disabled={!active}>Reset all</button>
  </div>

  <Section title="Public schools" meta={[app.charter !== 'all' ? 'charter' : '', app.levels.length ? `${app.levels.length} levels` : ''].filter(Boolean).join(' · ') || 'all'} open>
    <div class="pills" role="group" aria-label="Charter status">
      {#each charterOpts as o}
        <button class:on={app.charter === o.id} aria-pressed={app.charter === o.id} onclick={() => (app.charter = o.id)}>{o.label}</button>
      {/each}
    </div>
    <fieldset>
      <legend>School level</legend>
      <div class="checks">
        {#each levels as l}
          <label><input type="checkbox" checked={app.levels.includes(l)} onchange={() => (app.levels = toggle(app.levels, l))} /> {l}</label>
        {/each}
      </div>
    </fieldset>
  </Section>

  <Section title="Private schools" meta={app.privateAffil.length ? `${app.privateAffil.length} selected` : 'all'} open>
    <fieldset>
      <legend>Affiliation</legend>
      <div class="checks">
        {#each affils as c}
          <label><input type="checkbox" checked={app.privateAffil.includes(c.code)} onchange={() => (app.privateAffil = toggle(app.privateAffil, c.code))} /> {c.label}</label>
        {/each}
      </div>
    </fieldset>
    <p class="hint">The Private School Universe Survey runs every two years. Dotted outlines mark approximate (geocoded) locations.</p>
  </Section>

  <Section title="Colleges" meta={app.collegeControls.length ? `${app.collegeControls.length} selected` : 'all'} open>
    <fieldset>
      <legend>Control</legend>
      <div class="checks">
        {#each controls as c}
          <label><input type="checkbox" checked={app.collegeControls.includes(c.code)} onchange={() => (app.collegeControls = toggle(app.collegeControls, c.code))} /> {c.label}</label>
        {/each}
      </div>
    </fieldset>
    <p class="hint">Colleges before 2008 have no map location in the NCES data unless they were still open later.</p>
  </Section>
</Drawer>

<style>
  .bar {
    display: flex;
    justify-content: space-between;
    padding: 0 16px 10px;
    color: var(--muted);
    font-size: 12.5px;
  }
  .link:disabled {
    color: var(--muted);
    text-decoration: none;
    cursor: default;
  }
  .pills {
    display: flex;
    flex-wrap: wrap;
    gap: 5px;
  }
  .pills button {
    padding: 3px 10px;
    border-radius: 99px;
    border: 1px solid var(--border);
    background: var(--surface);
    color: var(--muted);
    font-size: 12.5px;
  }
  .pills button.on {
    background: var(--accent);
    color: var(--accent-text);
    border-color: var(--accent);
  }
  fieldset {
    border: 0;
    padding: 0;
    margin: 0;
  }
  legend {
    padding: 0;
    margin-bottom: 4px;
    color: var(--muted);
    font-size: 12px;
  }
  .checks {
    display: flex;
    flex-direction: column;
    gap: 3px;
  }
  .checks label {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  input[type='checkbox'] {
    accent-color: var(--accent);
    margin: 0;
  }
  .hint {
    color: var(--muted);
    font-size: 12px;
    margin: 0;
  }
</style>
