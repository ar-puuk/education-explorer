import { dataUrl, queryParquet, type Row } from './db'
import type { CollegePointsFile, DictEntry, PointsFile, PrivatePointsFile, StateMeta, ValueLabel, YearsMeta } from './types'

async function getJson<T>(rel: string): Promise<T> {
  const r = await fetch(dataUrl(rel))
  if (!r.ok) throw new Error(`${rel}: HTTP ${r.status}`)
  return r.json() as Promise<T>
}

export const loadState = () => getJson<StateMeta>('meta/state.json')
export const loadYears = () => getJson<YearsMeta>('meta/years.json')
export const loadPublicPoints = () => getJson<PointsFile>('geo/points_public.json')
export const loadCollegePoints = () => getJson<CollegePointsFile>('geo/points_college.json')
export const loadPrivatePoints = () => getJson<PrivatePointsFile>('geo/points_private.json')

let dictCache: Map<string, DictEntry> | null = null

/** Dictionary keyed by "dataset.table.column". */
export async function loadDictionary(): Promise<Map<string, DictEntry>> {
  if (dictCache) return dictCache
  const rows = await queryParquet(
    ['meta/dictionary.parquet'],
    'SELECT dataset, "table", "column", label, description, unit, first_year, last_year, caveat FROM {files}',
  )
  dictCache = new Map(rows.map((r) => [`${r.dataset}.${r.table}.${r.column}`, r as unknown as DictEntry]))
  return dictCache
}

let labelCache: Map<string, string> | null = null

/** Code labels keyed by "dataset.table.column|code" (IPEDS code columns). */
export async function loadValueLabels(): Promise<Map<string, string>> {
  if (labelCache) return labelCache
  const rows = (await queryParquet(['meta/value_labels.parquet'], 'SELECT dataset, "table", "column", code, label FROM {files}')) as unknown as (ValueLabel & { dataset: string })[]
  labelCache = new Map(rows.map((r) => [`${r.dataset}.${r.table}.${r.column}|${r.code}`, r.label]))
  return labelCache
}

let available: YearsMeta | null = null
export function setAvailable(y: YearsMeta) {
  available = y
}

/** Parquet paths for a table, limited to years the table actually has (years.json). */
const files = (table: string, years: number[]) => {
  const have = available?.ccd?.[table]?.years
  return years.filter((y) => !have || have.includes(y)).map((y) => `ccd/${table}/${y}.parquet`)
}

export async function schoolDirectoryHistory(years: number[], ncessch: string): Promise<Row[]> {
  return queryParquet(
    files('school_directory', years),
    'SELECT * FROM {files} WHERE ncessch = ? ORDER BY year',
    [ncessch],
  )
}

export async function schoolLocationHistory(years: number[], ncessch: string): Promise<Row[]> {
  return queryParquet(files('school_location', years), 'SELECT * FROM {files} WHERE ncessch = ? ORDER BY year', [ncessch])
}

export async function schoolCharacteristics(years: number[], ncessch: string): Promise<Row[]> {
  return queryParquet(files('school_characteristics', years), 'SELECT * FROM {files} WHERE ncessch = ? ORDER BY year', [ncessch])
}

export interface MembershipRow {
  year: number
  grade: string
  race: string
  sex: string
  total_indicator: string
  student_count: number | null
  value_flag: string | null
}

export async function membershipHistory(years: number[], ncessch: string): Promise<MembershipRow[]> {
  const rows = await queryParquet(
    files('membership', years),
    'SELECT year, grade, race, sex, total_indicator, student_count, value_flag FROM {files} WHERE ncessch = ? ORDER BY year',
    [ncessch],
  )
  return rows as unknown as MembershipRow[]
}


// ---------------------------------------------------------------------- IPEDS
const ipedsFiles = (table: string, years?: number[]) => {
  const have = available?.ipeds?.[table]?.years ?? []
  return (years ? have.filter((y) => years.includes(y)) : have).map((y) => `ipeds/${table}/${y}.parquet`)
}

export const ipedsTables = () => available?.ipeds ?? {}

/** All rows of an IPEDS table for one institution (every year the table has), newest last. */
export async function ipedsRows(table: string, unitid: string, years?: number[]): Promise<Row[]> {
  return queryParquet(ipedsFiles(table, years), 'SELECT * FROM {files} WHERE unitid = ? ORDER BY year', [unitid])
}


// ---------------------------------------------------------------------- PSS
/** Rows of a PSS table (schools, enrollment, teachers) for one school (by PPIN), every survey year. */
export async function pssRows(table: string, ppin: string): Promise<Row[]> {
  const have = available?.pss?.[table]?.years ?? []
  return queryParquet(have.map((y) => `pss/${table}/${y}.parquet`), 'SELECT * FROM {files} WHERE ppin = ? ORDER BY year', [ppin])
}
