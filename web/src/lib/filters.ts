import { app, isOperating, surveyYearFor } from './app.svelte'
import { levelLabel } from './labels'
import type { CollegeInstitution, PrivateSchool, PublicSchool } from './types'

/** What is currently shown for each dataset (year + filters). The map and the table view both use these. */

export interface PublicRow {
  s: PublicSchool
  i: number
  status: string
  operating: boolean
}

export function visiblePublic(): PublicRow[] {
  const p = app.points
  if (!p || !app.year) return []
  const out: PublicRow[] = []
  for (const s of p.schools) {
    const i = s.years.indexOf(app.year)
    if (i < 0) continue
    const status = p.statuses[s.status[i]] ?? ''
    const operating = isOperating(status)
    if (!operating && !app.includeClosed) continue
    if (app.charter === 'yes' && s.charter !== 'Yes') continue
    if (app.charter === 'no' && s.charter === 'Yes') continue
    if (app.levels.length && !app.levels.includes(levelLabel(s.level))) continue
    out.push({ s, i, status, operating })
  }
  return out
}

export interface PrivateRow {
  s: PrivateSchool
  i: number
  survey: number
}

export function visiblePrivate(): PrivateRow[] {
  const p = app.private
  const survey = surveyYearFor(app.year)
  if (!p || survey == null) return []
  const out: PrivateRow[] = []
  for (const s of p.schools) {
    const i = s.years.indexOf(survey)
    if (i < 0) continue
    if (app.privateAffil.length && !app.privateAffil.includes(s.relig ?? -9)) continue
    out.push({ s, i, survey })
  }
  return out
}

export interface CollegeRow {
  s: CollegeInstitution
  i: number
  operating: boolean
}

export function visibleColleges(): CollegeRow[] {
  const c = app.college
  if (!c || !app.year) return []
  const out: CollegeRow[] = []
  for (const s of c.institutions) {
    const i = s.years.indexOf(app.year)
    if (i < 0) continue
    const operating = s.active[i] === 1
    if (!operating && !app.includeClosed) continue
    if (app.collegeControls.length && !app.collegeControls.includes(s.control ?? -9)) continue
    out.push({ s, i, operating })
  }
  return out
}
