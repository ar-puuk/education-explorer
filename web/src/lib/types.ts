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
  [dataset: string]: {
    [table: string]: { years: number[]; versions?: { [year: string]: string | string[] | null }; title?: string; survey?: string }
  }
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
  coordSource?: string
  approx?: boolean
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

export interface PrivateSchool {
  id: string
  name: string
  address: string | null
  city: string | null
  zip: string | null
  lat: number
  lon: number
  /** 'pss' (provided by NCES) or 'geocode' (Census geocoder, see approx) */
  coordSource: string
  approx: boolean
  /** survey years in which the school appears (biennial), with aligned enrollment and teachers (FTE) */
  years: number[]
  enroll: (number | null)[]
  teachers: (number | null)[]
  level: number | null
  typology: number | null
  relig: number | null
  ulocale: string | null
}

export interface PrivatePointsFile {
  dataset: 'private'
  years: number[]
  labels: { level: { [c: string]: string }; typology: { [c: string]: string }; relig: { [c: string]: string } }
  schools: PrivateSchool[]
}

/** meta/year_summary.json: places per year per dataset (what the map can show). */
export interface YearSummary {
  public: Record<string, { mapped: number; operating: number; directory: number | null }>
  private: Record<string, { mapped: number }>
  college: Record<string, { mapped: number; active: number }>
  private_survey_years: number[]
}

/** meta/state_reference.json: quartiles of a metric across operating public schools, per year. */
export interface StateReference {
  scope: string
  min_n: number
  metrics: Record<string, { label: string; years: Record<string, { n: number; p25: number; median: number; p75: number }> }>
}

/** [leaid, name, boundary years] from geo/districts_index.json */
export type DistrictIndexItem = [string, string, number[]]

/** One school-year from derived/school_profile.parquet */
export interface ProfileRow {
  year: number
  enrollment: number | null
  teachers_fte: number | null
  students_per_teacher: number | null
  frl_share: number | null
}
