import { dataUrl, queryParquet, type Row } from './db'
import type { DictEntry, PointsFile, StateMeta, YearsMeta } from './types'

async function getJson<T>(rel: string): Promise<T> {
  const r = await fetch(dataUrl(rel))
  if (!r.ok) throw new Error(`${rel}: HTTP ${r.status}`)
  return r.json() as Promise<T>
}

export const loadState = () => getJson<StateMeta>('meta/state.json')
export const loadYears = () => getJson<YearsMeta>('meta/years.json')
export const loadPublicPoints = () => getJson<PointsFile>('geo/points_public.json')

let dictCache: Map<string, DictEntry> | null = null

/** Dictionary keyed by "table.column" (public CCD tables). */
export async function loadDictionary(): Promise<Map<string, DictEntry>> {
  if (dictCache) return dictCache
  const rows = await queryParquet(
    ['meta/dictionary.parquet'],
    'SELECT dataset, "table", "column", label, description, unit, first_year, last_year, caveat FROM {files}',
  )
  dictCache = new Map(rows.map((r) => [`${r.table}.${r.column}`, r as unknown as DictEntry]))
  return dictCache
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
