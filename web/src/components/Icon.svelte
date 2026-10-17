<script module lang="ts">
  export type IconName =
    | 'layers' | 'filter' | 'table' | 'compare' | 'info' | 'search' | 'chev' | 'x' | 'expand' | 'shrink' | 'play'
    | 'pause' | 'moon' | 'sun' | 'monitor' | 'plus' | 'download' | 'cap' | 'map' | 'check'
</script>

<script lang="ts">
  const PATHS: Record<IconName, string> = {
    layers: 'M12 3 3 8l9 5 9-5-9-5ZM3 13l9 5 9-5',
    filter: 'M4 6h16M7 12h10M10 18h4',
    table: 'M5 4h14a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2ZM3 10h18M9 4v16',
    compare: 'M8 4v16M16 4v16M3 9h5M16 15h5',
    info: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18ZM12 11v5M12 8h.01',
    search: 'M11 4.5a6.5 6.5 0 1 0 0 13 6.5 6.5 0 0 0 0-13ZM20 20l-4-4',
    chev: 'm9 6 6 6-6 6',
    x: 'M6 6l12 12M18 6 6 18',
    expand: 'M14 4h6v6M10 20H4v-6M20 4l-7 7M4 20l7-7',
    shrink: 'M20 10h-6V4M4 14h6v6M14 10l7-7M3 21l7-7',
    play: 'M8 5v14l11-7L8 5Z',
    pause: 'M8 5v14M16 5v14',
    moon: 'M20 14.5A8 8 0 0 1 9.5 4 8 8 0 1 0 20 14.5Z',
    sun: 'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8ZM12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5 19 19M5 19l1.5-1.5M17.5 6.5 19 5',
    monitor: 'M4 5h16a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1ZM8 21h8M12 17v4',
    plus: 'M12 5v14M5 12h14',
    download: 'M12 4v11m-4-4 4 4 4-4M5 20h14',
    cap: 'm2 9 10-5 10 5-10 5L2 9ZM6 11.5V16c3 2.5 9 2.5 12 0v-4.5',
    map: 'M9 4 3 6v14l6-2 6 2 6-2V4l-6 2-6-2ZM9 4v14M15 6v14',
    check: 'm5 12 5 5 9-10',
  }

  let { name, size = 16 }: { name: IconName; size?: number } = $props()
</script>

<svg
  width={size}
  height={size}
  viewBox="0 0 24 24"
  fill={name === 'play' ? 'currentColor' : 'none'}
  stroke="currentColor"
  stroke-width="1.8"
  stroke-linecap="round"
  stroke-linejoin="round"
  aria-hidden="true"
  focusable="false"
  style="flex: none"
>
  <path d={PATHS[name]} />
</svg>
