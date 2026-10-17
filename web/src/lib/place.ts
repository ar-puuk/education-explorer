import { app } from './app.svelte'
import type { Selectable } from './icons'

/** Display name for a selectable place, looked up from the already-loaded point files and boundaries. */
export function placeName(dataset: Selectable, id: string): string {
  if (dataset === 'public') return app.points?.schools.find((s) => s.id === id)?.name ?? id
  if (dataset === 'private') return app.private?.schools.find((s) => s.id === id)?.name ?? id
  if (dataset === 'college') return app.college?.institutions.find((s) => s.id === id)?.name ?? id
  return String(app.districts?.features.find((f) => f.properties?.leaid === id)?.properties?.name ?? id)
}

export const DATASET_COLOR: Record<Selectable, string> = {
  public: 'var(--c-public)',
  private: 'var(--c-private)',
  college: 'var(--c-college)',
  district: 'var(--muted)',
}
