<script module lang="ts">
  import { UI_ICONS } from '../lib/lucide'
  export type IconName = keyof typeof UI_ICONS
</script>

<script lang="ts">
  let { name, size = 16 }: { name: IconName; size?: number } = $props()
</script>

<svg
  width={size}
  height={size}
  viewBox="0 0 24 24"
  fill={name === 'play' ? 'currentColor' : 'none'}
  stroke="currentColor"
  stroke-width="2"
  stroke-linecap="round"
  stroke-linejoin="round"
  aria-hidden="true"
  focusable="false"
  style="flex: none"
>
  {#each UI_ICONS[name] as [tag, attrs]}
    <svelte:element this={tag} {...attrs} />
  {/each}
</svg>
