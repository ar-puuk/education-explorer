<script lang="ts">
  import { app } from '../lib/app.svelte'
  import Icon from './Icon.svelte'

  let { onPick }: { onPick: (dataset: 'public' | 'private' | 'college' | 'district', id: string, lon: number, lat: number) => void } = $props()
  let q = $state('')
  let open = $state(false)
  let active = $state(0)
  let input = $state<HTMLInputElement>()

  type Hit = { dataset: 'public' | 'private' | 'college' | 'district'; id: string; name: string; sub: string; lon: number; lat: number }
  const results = $derived.by((): Hit[] => {
    const term = q.trim().toLowerCase()
    if (term.length < 2) return []
    const out: Hit[] = []
    for (const s of app.points?.schools ?? []) {
      if (s.name.toLowerCase().includes(term) || s.id.startsWith(term) || s.lea.toLowerCase().includes(term)) {
        out.push({ dataset: 'public', id: s.id, name: s.name, sub: `Public school · ${s.lea} · ${s.id}`, lon: s.lon, lat: s.lat })
        if (out.length >= 8) break
      }
    }
    for (const f of app.districts?.features ?? []) {
      const nm = String(f.properties?.name ?? '')
      if (nm.toLowerCase().includes(term) || String(f.properties?.leaid).startsWith(term)) {
        out.unshift({ dataset: 'district', id: String(f.properties?.leaid), name: nm, sub: `School district · ${f.properties?.leaid}`, lon: 0, lat: 0 })
      }
    }
    let np = 0
    for (const c of app.private?.schools ?? []) {
      if (c.name.toLowerCase().includes(term) || c.id.toLowerCase().startsWith(term)) {
        out.push({ dataset: 'private', id: c.id, name: c.name, sub: `Private school · ${c.city ?? ''} · ${c.id}`, lon: c.lon, lat: c.lat })
        if (++np >= 6) break
      }
    }
    let n = 0
    for (const c of app.college?.institutions ?? []) {
      if (c.name.toLowerCase().includes(term) || c.id.startsWith(term)) {
        out.push({ dataset: 'college', id: c.id, name: c.name, sub: `College · ${c.city ?? ''} · ${c.id}`, lon: c.lon, lat: c.lat })
        if (++n >= 6) break
      }
    }
    return out
  })

  function choose(i: number) {
    const s = results[i]
    if (!s) return
    onPick(s.dataset, s.id, s.lon, s.lat)
    q = ''
    open = false
  }

  function key(e: KeyboardEvent) {
    if (e.key === 'ArrowDown') {
      active = Math.min(active + 1, results.length - 1)
      e.preventDefault()
    } else if (e.key === 'ArrowUp') {
      active = Math.max(active - 1, 0)
      e.preventDefault()
    } else if (e.key === 'Enter') choose(active)
    else if (e.key === 'Escape') open = false
  }
</script>

<svelte:window onkeydown={(e) => { if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); input?.focus(); input?.select() } }} />

<div class="search">
  <span class="ico"><Icon name="search" size={15} /></span>
  <label class="sr-only" for="school-search">Search schools by name, district or ID</label>
  <input
    id="school-search"
    bind:this={input}
    type="search"
    placeholder="Search schools, districts, colleges"
    autocomplete="off"
    role="combobox"
    aria-expanded={open && results.length > 0}
    aria-controls="search-results"
    bind:value={q}
    onfocus={() => (open = true)}
    oninput={() => ((open = true), (active = 0))}
    onkeydown={key}
    onblur={() => setTimeout(() => (open = false), 150)}
  />
  <kbd class="hint" aria-hidden="true">Ctrl K</kbd>
  {#if open && results.length}
    <ul id="search-results" role="listbox">
      {#each results as s, i}
        <li role="option" aria-selected={i === active} class:active={i === active}>
          <button type="button" onmousedown={(e) => (e.preventDefault(), choose(i))}>
            <strong>{s.name}</strong>
            <span>{s.sub}</span>
          </button>
        </li>
      {/each}
    </ul>
  {/if}
</div>

<style>
  .search {
    position: relative;
    flex: 1 1 260px;
    max-width: 420px;
  }
  input {
    width: 100%;
    height: 34px;
    padding: 0 58px 0 32px;
    border: 1px solid var(--border);
    border-radius: 10px;
    background: var(--surface-2);
  }
  input::placeholder {
    color: var(--muted);
  }
  input:focus {
    background: var(--surface);
  }
  .ico {
    position: absolute;
    left: 10px;
    top: 50%;
    transform: translateY(-50%);
    color: var(--muted);
    display: inline-flex;
    pointer-events: none;
  }
  .hint {
    position: absolute;
    right: 8px;
    top: 50%;
    transform: translateY(-50%);
    font: 11px var(--f-data);
    color: var(--muted);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 0 5px;
    background: var(--surface);
    pointer-events: none;
  }
  .search:focus-within .hint {
    display: none;
  }
  ul {
    position: absolute;
    z-index: 30;
    left: 0;
    right: 0;
    top: calc(100% + 4px);
    list-style: none;
    margin: 0;
    padding: 4px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    box-shadow: var(--shadow);
    max-height: 60vh;
    overflow: auto;
  }
  li button {
    width: 100%;
    text-align: left;
    background: none;
    border: 0;
    padding: 6px 8px;
    border-radius: 6px;
    display: flex;
    flex-direction: column;
  }
  li.active button,
  li button:hover {
    background: var(--surface-2);
  }
  span {
    color: var(--muted);
    font-size: 12px;
  }
</style>
