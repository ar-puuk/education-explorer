<script lang="ts">
  import { app } from '../lib/app.svelte'
  import CollegeDetail from './CollegeDetail.svelte'
  import DistrictDetail from './DistrictDetail.svelte'
  import PrivateDetail from './PrivateDetail.svelte'
  import PublicDetail from './PublicDetail.svelte'

  let { onSelectSchool }: { onSelectSchool: (id: string, lon: number, lat: number) => void } = $props()
</script>

{#if app.selected?.dataset === 'public'}
  <PublicDetail />
{:else if app.selected?.dataset === 'district'}
  <DistrictDetail {onSelectSchool} />
{:else if app.selected?.dataset === 'private'}
  <PrivateDetail />
{:else if app.selected?.dataset === 'college'}
  <CollegeDetail />
{/if}
