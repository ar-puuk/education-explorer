// Chart colours. Race and ethnicity categories keep the same colour in every chart (and across datasets, whose labels differ slightly);
// every other series takes the next colour in order.
const RACE_INDEX: [RegExp, number][] = [
  [/^white/i, 0],
  [/^hispanic/i, 1],
  [/^asian/i, 2],
  [/^black/i, 3],
  [/^american indian/i, 4],
  [/^native hawaiian/i, 5],
  [/^two or more/i, 6],
  [/^(not specified|race\/ethnicity unknown|unknown)/i, 7],
  [/nonresident/i, 8],
]

/** Index into the 8 chart tokens (8 and above are drawn as a softened repeat). */
export function colorIndex(key: string, fallback: number): number {
  for (const [re, i] of RACE_INDEX) if (re.test(key)) return i
  return fallback
}

/** CSS colour for a series. */
export function seriesColor(i: number, css: (v: string) => string): string {
  return i < 8 ? css(`--chart-${i + 1}`) : `color-mix(in srgb, ${css(`--chart-${(i % 8) + 1}`)} 55%, ${css('--surface')})`
}

/** Colours for the keys of one chart; race categories are fixed, the rest fill the unused tokens in order. */
export function paletteFor(keys: string[], css: (v: string) => string): string[] {
  const fixed = keys.map((k) => colorIndex(k, -1))
  const anyRace = fixed.some((i) => i >= 0)
  if (!anyRace) return keys.map((_, i) => seriesColor(i, css))
  const used = new Set(fixed.filter((i) => i >= 0))
  let next = 0
  return keys.map((_, i) => {
    if (fixed[i] >= 0) return seriesColor(fixed[i], css)
    while (used.has(next)) next++
    used.add(next)
    return seriesColor(next++, css)
  })
}
