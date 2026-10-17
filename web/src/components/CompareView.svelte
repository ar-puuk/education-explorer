<script lang="ts">
  import { app } from '../lib/app.svelte'
  import { districtRows } from '../lib/data'
  import { download, toCsv } from '../lib/explore'
  import { fmtInt } from '../lib/labels'
  import type { Selectable } from '../lib/icons'
  import type { TrendPoint } from '../lib/types'
  import TrendChart from './TrendChart.svelte'

  interface Item {
    dataset: Selectable
    id: string
    name: string
    kind: string
    points: { year: number; value: number | null }[]
  }

  let items = $state<Item[]>([])
  let loading = $state(false)
  let indexed = $state(false)
  const districtCache = new Map<string, { year: number; value: number | null }[]>()

  const KIND: Record<string, string> = { public: 'Public school', private: 'Private school (survey years)', college: 'College', district: 'School district' }

  async function resolve(c: { dataset: Selectable; id: string }): Promise<Item | null> {
    if (c.dataset === 'public') {
      const s = app.points?.schools.find((x) => x.id === c.id)
      return s ? { ...c, name: s.name, kind: KIND.public, points: s.years.map((y, i) => ({ year: y, value: s.enroll[i] })) } : null
    }
    if (c.dataset === 'private') {
      const s = app.private?.schools.find((x) => x.id === c.id)
      return s ? { ...c, name: s.name, kind: KIND.private, points: s.years.map((y, i) => ({ year: y, value: s.enroll[i] })) } : null
    }
    if (c.dataset === 'college') {
      const s = app.college?.institutions.find((x) => x.id === c.id)
      return s ? { ...c, name: s.name, kind: KIND.college, points: s.years.map((y, i) => ({ year: y, value: s.enroll[i] })) } : null
    }
    const f = app.districts?.features.find((x) => x.properties?.leaid === c.id)
    if (!districtCache.has(c.id)) {
      const rows = await districtRows('district_membership', c.id)
      districtCache.set(c.id, rows.filter((r) => r.total_indicator === 'Education Unit Total').map((r) => ({ year: r.year as number, value: typeof r.student_count === 'number' ? r.student_count : null })))
    }
    return { ...c, name: String(f?.properties?.name ?? c.id), kind: KIND.district, points: districtCache.get(c.id)! }
  }

  $effect(() => {
    const set = app.compare.map((c) => ({ ...c }))
    let cancelled = false
    loading = true
    Promise.all(set.map(resolve))
      .then((r) => {
        if (!cancelled) items = r.filter((x): x is Item => x !== null)
      })
      .finally(() => {
        if (!cancelled) loading = false
      })
    return () => {
      cancelled = true
    }
  })

  const series = $derived.by((): TrendPoint[] => {
    const out: TrendPoint[] = []
    for (const it of items) {
      const pts = it.points.filter((p) => p.value != null)
      const base = pts.find((p) => (p.value ?? 0) > 0)?.value ?? null
      for (const p of it.points) {
        const v = p.value
        out.push({ year: p.year, key: it.name, value: indexed ? (v != null && base ? (100 * v) / base : null) : v })
      }
    }
    return out.sort((a, b) => a.year - b.year)
  })

  function remove(i: number) {
    app.compare = app.compare.filter((_, j) => j !== i)
  }
  function open(c: { dataset: Selectable; id: string }) {
    app.selected = { dataset: c.dataset, id: c.id }
    if (c.dataset === 'district') app.showDistricts = true
    app.showCompare = false
  }
  function exportCsv() {
    download('compare.csv', toCsv(['place', 'type', 'id', 'year', indexed ? 'index (first year = 100)' : 'enrollment'],
      series.map((d) => { const it = items.find((x) => x.name === d.key); return [d.key, it?.kind ?? '', it?.id ?? '', d.year, d.value] })))
  }
  const latest = (it: Item) => [...it.points].reverse().find((p) => p.value != null)
</script>

{#if app.showCompare}
  <div class="backdrop" role="presentation" onclick={() => (app.showCompare = false)}></div>
  <div class="dialog" role="dialog" aria-modal="true" aria-label="Compare places">
    <div class="head">
      <h2>Compare enrollment</h2>
      <button class="close" onclick={() => (app.showCompare = false)} aria-label="Close compare">×</button>
    </div>
    {#if !app.compare.length}
      <p class="muted">Nothing selected yet. Open a school, district or college and press “+ Compare” (up to six).</p>
    {:else}
      <label class="opt"><input type="checkbox" bind:checked={indexed} /> Index to the first year with data (= 100), to compare places of different sizes</label>
      {#if loading}<p class="muted">Loading…</p>{/if}
      <TrendChart data={series} yLabel={indexed ? 'Index' : 'Students'} currentYear={app.year} height={280} alt="Enrollment over time for the selected places" />
      <p class="muted">Public schools, colleges and districts use annual counts (fall enrollment); private schools only have biennial survey years. Counts are not a measure of quality.</p>
      <table>
        <thead><tr><th scope="col">Place</th><th scope="col">Type</th><th scope="col">Latest</th><th scope="col"><span class="sr-only">Actions</span></th></tr></thead>
        <tbody>
          {#each items as it, i}
            <tr>
              <td><button class="link" onclick={() => open(it)}>{it.name}</button></td>
              <td>{it.kind}</td>
              <td>{latest(it) ? `${fmtInt(latest(it)!.value)} (${latest(it)!.year})` : '—'}</td>
              <td><button onclick={() => remove(i)} aria-label={`Remove ${it.name}`}>Remove</button></td>
            </tr>
          {/each}
        </tbody>
      </table>
      <div class="actions">
        <button onclick={exportCsv}>Download CSV</button>
        <button onclick={() => (app.compare = [])}>Clear all</button>
      </div>
    {/if}
  </div>
{/if}

<style>
  .backdrop {
    position: fixed;
    inset: 0;
    background: rgb(0 0 0 / 40%);
    z-index: 40;
  }
  .dialog {
    position: fixed;
    z-index: 41;
    top: 6vh;
    left: 50%;
    transform: translateX(-50%);
    width: min(760px, calc(100% - 24px));
    max-height: 88vh;
    overflow: auto;
    background: var(--surface);
    color: var(--text);
    border: 1px solid var(--border);
    border-radius: 12px;
    box-shadow: var(--shadow);
    padding: 14px 18px 18px;
  }
  .head {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  h2 {
    font-size: 17px;
    margin: 0;
  }
  .close {
    border: 1px solid var(--border);
    background: var(--surface-2);
    border-radius: 50%;
    width: 30px;
    height: 30px;
    font-size: 18px;
    line-height: 1;
  }
  .muted,
  .opt {
    color: var(--muted);
    font-size: 12.5px;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    margin: 8px 0;
    font-size: 13px;
  }
  th,
  td {
    text-align: left;
    padding: 4px 8px;
    border-bottom: 1px solid var(--border);
  }
  button {
    background: var(--surface-2);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 3px 10px;
  }
  .link {
    background: none;
    border: 0;
    color: var(--accent);
    text-decoration: underline;
    padding: 0;
  }
  .actions {
    display: flex;
    gap: 8px;
  }
</style>
