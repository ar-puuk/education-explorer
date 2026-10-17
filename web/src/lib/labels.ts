/** NCES urban-centric locale codes (published NCES classification). */
export const LOCALE: Record<string, string> = {
  '11': 'City, large',
  '12': 'City, midsize',
  '13': 'City, small',
  '21': 'Suburb, large',
  '22': 'Suburb, midsize',
  '23': 'Suburb, small',
  '31': 'Town, fringe',
  '32': 'Town, distant',
  '33': 'Town, remote',
  '41': 'Rural, fringe',
  '42': 'Rural, distant',
  '43': 'Rural, remote',
}

export const localeLabel = (code: string | null | undefined) => (code ? (LOCALE[code] ?? code) : '')

export const GRADE_ORDER = [
  'Pre-Kindergarten',
  'Kindergarten',
  'Grade 1',
  'Grade 2',
  'Grade 3',
  'Grade 4',
  'Grade 5',
  'Grade 6',
  'Grade 7',
  'Grade 8',
  'Grade 9',
  'Grade 10',
  'Grade 11',
  'Grade 12',
  'Grade 13',
  'Ungraded',
  'Adult Education',
  'Not Specified',
]

export const GRADE_LOW_HIGH: Record<string, string> = {
  PK: 'Pre-K', KG: 'K', UG: 'Ungraded', AE: 'Adult ed.', '13': '13',
}
export const gradeLabel = (g: string | null | undefined) => (g ? (GRADE_LOW_HIGH[g] ?? String(Number(g) || g)) : '')

export const fmtInt = (n: number | null | undefined) => (n == null ? '—' : n.toLocaleString('en-US'))

export const schoolYearLabel = (y: number) => `${y}-${String((y + 1) % 100).padStart(2, '0')}`

/** The source uses several spellings for "no value"; show them as one level. */
export function levelLabel(l: string | null | undefined): string {
  if (!l || /^(n|not reported|not applicable|missing)$/i.test(l.trim())) return 'Not reported'
  return l.trim()
}
