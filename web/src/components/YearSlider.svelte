<script lang="ts">
  import { onDestroy } from 'svelte'
  import { app, publicYears } from '../lib/app.svelte'
  import { schoolYearLabel } from '../lib/labels'

  const years = $derived(publicYears())
  const idx = $derived(years.indexOf(app.year))
  const version = $derived.by(() => {
    const v = app.years?.ccd?.school_directory?.versions?.[String(app.year)]
    return Array.isArray(v) ? v.join('/') : (v ?? '')
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
      {#if version}<span class="badge {version}">{version}</span>{/if}
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
      {#each years as y}<span class:on={y === app.year}>{String(y).slice(2)}</span>{/each}
    </div>
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
  .ticks {
    display: flex;
    justify-content: space-between;
    font-size: 10px;
    color: var(--muted);
  }
  .ticks .on {
    color: var(--text);
    font-weight: 700;
  }
</style>
