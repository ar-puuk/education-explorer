<script lang="ts">
  import { onDestroy } from 'svelte'
  import { allYears, app, surveyYearFor } from '../lib/app.svelte'
  import { schoolYearLabel } from '../lib/labels'

  const years = $derived(allYears())
  const idx = $derived(years.indexOf(app.year))
  const version = $derived.by(() => {
    const v = app.years?.ccd?.school_directory?.versions?.[String(app.year)]
    return Array.isArray(v) ? v.join('/') : (v ?? '')
  })
  const publicFrom = $derived(app.points?.years[0] ?? 0)
  const publicNote = $derived(app.layers.public && app.year < publicFrom ? `Public school data start in ${schoolYearLabel(publicFrom)}.` : '')

  const survey = $derived(surveyYearFor(app.year))
  const privateNote = $derived.by(() => {
    if (!app.layers.private || !app.private) return ''
    if (survey == null) return `Private school data start with the ${schoolYearLabel(app.private.years[0])} survey.`
    return survey === app.year ? '' : `Private schools: ${schoolYearLabel(survey)} survey (surveys are biennial).`
  })

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
</script>

<div class="slider" role="group" aria-label="School year">
  <button class="play" onclick={play} aria-label={app.playing ? 'Pause' : 'Play through years'}>
    {app.playing ? '❚❚' : '▶'}
  </button>
  <div class="mid">
    <div class="label">
      <strong>{schoolYearLabel(app.year)}</strong>
      {#if version && app.year >= publicFrom}<span class="badge {version}" title="Release status of the public school files for this year">{version}</span>{/if}
      {#if publicNote}<span class="note">{publicNote}</span>{/if}
      {#if privateNote}<span class="note">{privateNote}</span>{/if}
    </div>
    <input
      type="range"
      min={years[0]}
      max={years[years.length - 1]}
      step="1"
      value={app.year}
      oninput={(e) => {
        stop()
        app.year = Number((e.currentTarget as HTMLInputElement).value)
      }}
      aria-label="School year (fall year)"
      aria-valuetext={schoolYearLabel(app.year)}
    />
    <div class="ticks" aria-hidden="true">
      {#each years as y}<span class:on={y === app.year} class:survey={app.layers.private && app.private?.years.includes(y)}>{String(y).slice(2)}</span>{/each}
    </div>
    {#if app.layers.private && app.private}
      <p class="key"><span class="pip"></span> private school survey year (biennial)</p>
    {/if}
  </div>
</div>

<style>
  .slider {
    position: absolute;
    z-index: 5;
    left: 50%;
    transform: translateX(-50%);
    bottom: 26px;
    display: flex;
    align-items: center;
    gap: 12px;
    width: min(560px, calc(100% - 24px));
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    box-shadow: var(--shadow);
    padding: 8px 14px;
  }
  .play {
    width: 36px;
    height: 36px;
    border-radius: 50%;
    border: 1px solid var(--border);
    background: var(--surface-2);
  }
  .mid {
    flex: 1;
  }
  input {
    width: 100%;
    accent-color: var(--accent);
  }
  .label {
    display: flex;
    align-items: baseline;
    gap: 8px;
  }
  .badge {
    font-size: 11px;
    border: 1px solid var(--border);
    border-radius: 999px;
    padding: 0 7px;
    color: var(--muted);
  }
  .badge.preliminary {
    background: var(--warn-bg);
    color: var(--warn-text);
  }
  .note {
    font-size: 11.5px;
    color: var(--muted);
  }
  .ticks {
    display: flex;
    justify-content: space-between;
    font-size: 10px;
    color: var(--muted);
  }
  @media (max-width: 720px) {
    .ticks span:not(.on):not(:nth-child(5n + 1)) {
      visibility: hidden;
    }
    .slider {
      bottom: 34px;
      padding: 6px 10px;
    }
  }
  .ticks .survey {
    text-decoration: underline;
    text-decoration-style: dotted;
    text-underline-offset: 3px;
    text-decoration-color: var(--c-private);
  }
  .key {
    margin: 2px 0 0;
    font-size: 11px;
    color: var(--muted);
  }
  .pip {
    display: inline-block;
    width: 8px;
    border-bottom: 2px dotted var(--c-private);
    vertical-align: middle;
  }
  .ticks .on {
    color: var(--text);
    font-weight: 700;
  }
</style>
