<script lang="ts">
  import { onDestroy } from 'svelte'
  import { allYears, app, surveyYearFor } from '../lib/app.svelte'
  import { schoolYearLabel } from '../lib/labels'
  import Icon from './Icon.svelte'

  const years = $derived(allYears())
  const idx = $derived(Math.max(0, years.indexOf(app.year)))
  const version = $derived.by(() => {
    const v = app.years?.ccd?.school_directory?.versions?.[String(app.year)]
    return Array.isArray(v) ? v.join('/') : (v ?? '')
  })
  const publicFrom = $derived(app.points?.years[0] ?? 0)
  const publicNote = $derived(app.layers.public && app.year < publicFrom ? `Public data start ${schoolYearLabel(publicFrom)}` : '')
  const survey = $derived(surveyYearFor(app.year))
  const privateNote = $derived.by(() => {
    if (!app.layers.private || !app.private) return ''
    if (survey == null) return `Private data start ${schoolYearLabel(app.private.years[0])}`
    return survey === app.year ? '' : `Private: ${schoolYearLabel(survey)} survey`
  })

  // places per year, per dataset, for the histogram (precomputed in meta/year_summary.json)
  const counts = $derived.by(() => {
    const sum = app.summary
    return years.map((y) => {
      const sv = surveyYearFor(y)
      return {
        y,
        pub: app.layers.public ? (sum?.public[String(y)]?.mapped ?? 0) : 0,
        col: app.layers.college ? (sum?.college[String(y)]?.mapped ?? 0) : 0,
        prv: app.layers.private && sv != null ? (sum?.private[String(sv)]?.mapped ?? 0) : 0,
      }
    })
  })
  const maxTotal = $derived(Math.max(1, ...counts.map((c) => c.pub + c.col + c.prv)))

  const H = 40
  const n = $derived(years.length)
  const bw = 100 // viewBox units per year

  let timer: ReturnType<typeof setInterval> | undefined
  function stop() {
    app.playing = false
    clearInterval(timer)
  }
  function play() {
    if (app.playing) return stop()
    app.playing = true
    if (idx >= years.length - 1) app.year = years[0]
    timer = setInterval(() => {
      const i = years.indexOf(app.year)
      if (i >= years.length - 1) return stop()
      app.year = years[i + 1]
    }, 900)
  }
  onDestroy(() => clearInterval(timer))

  let track: HTMLDivElement
  function fromPointer(e: PointerEvent) {
    const r = track.getBoundingClientRect()
    const i = Math.min(n - 1, Math.max(0, Math.floor(((e.clientX - r.left) / r.width) * n)))
    app.year = years[i]
  }
  function down(e: PointerEvent) {
    stop()
    track.setPointerCapture(e.pointerId)
    fromPointer(e)
  }
  function move(e: PointerEvent) {
    if (track.hasPointerCapture(e.pointerId)) fromPointer(e)
  }
  function key(e: KeyboardEvent) {
    const step = e.key === 'ArrowRight' || e.key === 'ArrowUp' ? 1 : e.key === 'ArrowLeft' || e.key === 'ArrowDown' ? -1 : 0
    if (step) {
      stop()
      app.year = years[Math.min(n - 1, Math.max(0, idx + step))]
    } else if (e.key === 'Home') app.year = years[0]
    else if (e.key === 'End') app.year = years[n - 1]
    else return
    e.preventDefault()
  }
</script>

<footer class="time" aria-label="Timeline">
  <button class="play" onclick={play} aria-label={app.playing ? 'Pause' : 'Play through years'}>
    <Icon name={app.playing ? 'pause' : 'play'} size={15} />
  </button>
  <div class="yr">
    <strong>{schoolYearLabel(app.year)}</strong>
    <span>
      {#if version && app.year >= publicFrom}<span class="badge {version}" title="Release status of the public school files for this year">{version}</span>{/if}
      {#if publicNote || privateNote}{[publicNote, privateNote].filter(Boolean).join(' · ')}{:else}fall {app.year}{/if}
    </span>
  </div>
  <div class="tl">
    <!-- svelte-ignore a11y_no_noninteractive_tabindex -->
    <div
      class="track"
      bind:this={track}
      role="slider"
      tabindex="0"
      aria-label="School year"
      aria-valuemin={years[0]}
      aria-valuemax={years[n - 1]}
      aria-valuenow={app.year}
      aria-valuetext={schoolYearLabel(app.year)}
      onpointerdown={down}
      onpointermove={move}
      onkeydown={key}
    >
      <svg viewBox={`0 0 ${n * bw} ${H + 8}`} preserveAspectRatio="none" aria-hidden="true">
        {#each counts as c, i}
          {@const hp = (c.pub / maxTotal) * H}
          {@const hv = (c.prv / maxTotal) * H}
          {@const hc = (c.col / maxTotal) * H}
          {@const sel = c.y === app.year}
          <g opacity={sel ? 1 : 0.45}>
            <rect x={i * bw + 12} y={H - hp} width={bw - 24} height={hp} fill="var(--c-public)" />
            <rect x={i * bw + 12} y={H - hp - hv} width={bw - 24} height={hv} fill="var(--c-private)" />
            <rect x={i * bw + 12} y={H - hp - hv - hc} width={bw - 24} height={hc} fill="var(--c-college)" />
          </g>
          {#if sel}<rect x={i * bw + 4} y={H + 3} width={bw - 8} height="4" rx="2" fill="var(--accent)" />{/if}
        {/each}
      </svg>
      <div class="ticks" aria-hidden="true">
        {#each years as y}<span class:on={y === app.year} class:survey={app.layers.private && app.private?.years.includes(y)}>{String(y).slice(2)}</span>{/each}
      </div>
    </div>
  </div>
  <ul class="key" aria-label="Timeline key">
    <li><i style="background: var(--c-public)"></i>public</li>
    {#if app.layers.private}<li><i style="background: var(--c-private)"></i>private <small>(underlined = survey year)</small></li>{/if}
    {#if app.layers.college}<li><i style="background: var(--c-college)"></i>college</li>{/if}
  </ul>
</footer>

<style>
  .time {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 8px 16px;
    background: var(--surface);
    border-top: 1px solid var(--border);
    position: relative;
    z-index: 8;
  }
  .play {
    width: 36px;
    height: 36px;
    border-radius: 50%;
    border: 0;
    background: var(--accent);
    color: var(--accent-text);
    display: grid;
    place-items: center;
    flex: none;
  }
  .yr {
    display: flex;
    flex-direction: column;
    min-width: 150px;
    max-width: 300px;
  }
  .yr strong {
    font: 500 24px/1.1 var(--f-data);
    letter-spacing: -0.03em;
  }
  .yr > span {
    font-size: 11.5px;
    color: var(--muted);
    line-height: 1.25;
  }
  .badge {
    border: 1px solid var(--border);
    border-radius: 999px;
    padding: 0 7px;
    margin-right: 4px;
  }
  .badge.preliminary {
    background: var(--warn-bg);
    color: var(--warn-text);
  }
  .tl {
    flex: 1;
    min-width: 0;
    overflow: hidden;
  }
  .track {
    cursor: pointer;
    touch-action: none;
    border-radius: 6px;
  }
  svg {
    display: block;
    width: 100%;
    height: 46px;
  }
  .ticks {
    display: grid;
    grid-auto-flow: column;
    grid-auto-columns: minmax(0, 1fr);
    text-align: center;
    font: 10px var(--f-data);
    color: var(--muted);
  }
  .ticks .on {
    color: var(--text);
    font-weight: 500;
  }
  .ticks .survey {
    text-decoration: underline dotted var(--c-private);
    text-underline-offset: 3px;
  }
  .key {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 2px;
    font-size: 11.5px;
    color: var(--muted);
    min-width: 96px;
  }
  .key li {
    display: flex;
    align-items: center;
    gap: 6px;
    white-space: nowrap;
  }
  .key i {
    width: 9px;
    height: 9px;
    border-radius: 2px;
  }
  .key small {
    display: none;
  }
  @media (max-width: 900px) {
    .key {
      display: none;
    }
  }
  @media (max-width: 720px) {
    .time {
      gap: 10px;
      padding: 6px 10px;
    }
    .yr {
      min-width: 0;
    }
    .yr strong {
      font-size: 17px;
    }
    .yr > span {
      display: none;
    }
    .ticks span:not(.on):not(:nth-child(5n + 1)) {
      visibility: hidden;
    }
  }
</style>
