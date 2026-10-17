<script lang="ts">
  import { app } from '../lib/app.svelte'
  import CollegeDetail from './CollegeDetail.svelte'
  import PrivateDetail from './PrivateDetail.svelte'
  import PublicDetail from './PublicDetail.svelte'
</script>

{#if app.selected?.dataset === 'public'}
  <PublicDetail />
{:else if app.selected?.dataset === 'private'}
  <PrivateDetail />
{:else if app.selected?.dataset === 'college'}
  <CollegeDetail />
{/if}
