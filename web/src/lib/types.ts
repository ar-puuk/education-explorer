export interface PublicSchool {
  id: string
  name: string
  leaid: string
  lea: string
  lat: number
  lon: number
  years: number[]
  /** index into PointsFile.statuses, aligned with years */
  status: number[]
  /** total enrollment aligned with years (null when unknown) */
  enroll: (number | null)[]
  level: string | null
  charter: string | null
  type: string | null
  gradeLow: string | null
  gradeHigh: string | null
  locale: string | null
  county: string | null
  coordSource: string | null
}

export interface PointsFile {
  dataset: 'public' | 'private' | 'college'
  years: number[]
  statuses: string[]
  schools: PublicSchool[]
}

export interface StateMeta {
  name: string
  abbrev: string
  fips: string
  bbox: [number, number, number, number]
  center: [number, number]
  zoom: number
  site_title: string
}

export interface YearsMeta {
  [dataset: string]: { [table: string]: { years: number[]; versions: { [year: string]: string | string[] | null } } }
}

export interface DictEntry {
  dataset: string
  table: string
  column: string
  label: string
  description: string
  unit: string
  first_year: number
  last_year: number
  caveat: string
}

export interface TrendPoint {
  year: number
  key: string
  value: number | null
}

export interface CollegeInstitution {
  id: string
  name: string
  city: string | null
  lat: number
  lon: number
  years: number[]
  /** 1 when the institution was active that year, aligned with years */
  active: number[]
  /** fall enrollment, all students, aligned with years */
  enroll: (number | null)[]
  sector: number | null
  control: number | null
  level: number | null
  locale: number | null
  hbcu: number | null
  web: string | null
}

export interface CollegePointsFile {
  dataset: 'college'
  years: number[]
  labels: { [field: string]: { [code: string]: string } }
  institutions: CollegeInstitution[]
}

export interface ValueLabel {
  table: string
  column: string
  code: string
  label: string
}
