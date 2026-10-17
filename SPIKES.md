# Phase 0 spike findings (2026-10-16)

All findings below were observed against live sources on 2026-10-16.

## 1. GitHub Pages range requests: PASS
- `https://ar-puuk.github.io/education-explorer/spike/test.parquet` (8.5 MB, ZSTD): `HEAD` returns `Accept-Ranges: bytes`, `Content-Length`, `Access-Control-Allow-Origin: *`, `Cache-Control: max-age=600`.
- `Range: bytes=0-99` returns `206 Partial Content`; open-ended ranges also work.
- Native DuckDB `httpfs` queried it with a filter. DuckDB-WASM (`@duckdb/duckdb-wasm`, EH bundle, `registerFileURL(..., HTTP, false)`) queried it cross-origin from headless Chromium: 501 rows in ~0.7-1.1 s.
- Caveats: Pages sets `Cache-Control: max-age=600`, so freshly pushed Parquet can be stale for ~10 min. Content-Type is `application/octet-stream` (fine).
- Pages URL: https://ar-puuk.github.io/education-explorer/

## 2. OpenFreeMap: PASS
- All five style URLs (`liberty`, `bright`, `positron`, `dark`, `fiord`) return valid styles (111/119/55/47/48 layers), all with sources `ne2_shaded` + `openmaptiles`, shared glyphs/sprite.
- An overlay (GeoJSON source + circle layer) survives `map.setStyle()` when re-added on `style.load`; verified for all five, the feature rendered each time.
- Liberty already contains a `building-3d` `fill-extrusion` layer (source-layer `building`), so "Liberty 3D" = set pitch and keep that layer visible.
- maplibre-gl 6.x: `import * as maplibregl from 'maplibre-gl'` (no default export). In Vite dev the worker must be set explicitly: `setWorkerUrl(workerUrl)` with `import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url'`.
- Visual quirks of Dark/Fiord to be checked in Phase 2.

## 3. CCD (public schools)
- **No static file listing; the files page is rendered by JS from a JSON API:** `GET https://nces.ed.gov/ccd/datatables/api/Lookup/` (school years and ids) and `GET https://nces.ed.gov/ccd/datatables/api/File/0/0/<schoolYearId>/0/0/0` (all files for a year, with `fileURL`, size, component, version). The all-years call (`.../0/0/0/0/0/0`) returns 500, so query per year. 40 school years are listed (1986-87 to 2025-26). `fetch --check-only` will use this.
- Files are zips containing CSV + SAS7BDAT: `https://nces.ed.gov/ccd/Data/zip/ccd_<lea|sch|sea>_<topic>_<yyyy>_<l|w>_<ver>_<mmddyy>.zip` (`029` directory, `052` membership, `059` staff, `033` lunch, `129` school characteristics). Date suffix and version vary, so URLs cannot be guessed; use the API.
- 2024-25 (final, released Dec 2025): school directory, lunch, membership, school characteristics, staff; LEA directory/membership/staff; SEA directory/membership/staff. 2025-26: **directory only** (preliminary, `..._0a_050626.zip`, lower-case `data/` path), LEA + school.
- **School directory has NO lat/lon.** Coordinates come from NCES EDGE (below). HANDOFF assumed CCD had them.
- School directory 2024-25: UTF-8 CSV, header row, ~85 columns; `SY_STATUS_TEXT` in Open/New/Future/Closed/Changed Boundary/Agency; Utah 1,119 rows.
- Membership 2024-25: **national file is 2.3 GB CSV (212 MB zip)**; Utah 134,795 long rows. Columns: `SCHOOL_YEAR, FIPST, STATENAME, ST, SCH_NAME, STATE_AGENCY_NO, UNION, ST_LEAID, LEAID, ST_SCHID, NCESSCH, SCHID, GRADE, RACE_ETHNICITY, SEX, STUDENT_COUNT, TOTAL_INDICATOR, DMS_FLAG`. Labels are text (`Grade 7`, `No Category Codes`, `Not Specified`); `TOTAL_INDICATOR` separates category set vs subtotal vs "Education Unit Total"; `DMS_FLAG` in (`Reported`, `Manual adjustment`, `Derived`). No numeric sentinels in Utah 2024-25 membership; older years to be checked in Phase 1.
- State filter: `ST` (abbrev) or `FIPST` (text, zero padded).
- Documentation per file: companion `.xlsx` (layout/dictionary) at `https://nces.ed.gov/ccd/xls/...`; SPS program files. These feed the dictionary builder.
- Raw files are large: stream with DuckDB.

## 4. EDGE (school point locations)
- `https://nces.ed.gov/programs/edge/Geographic/SchoolLocations` lists `https://nces.ed.gov/programs/edge/data/EDGE_GEOCODE_{PUBLICSCH,PUBLICLEA,PRIVATESCH,POSTSECSCH}_<yyyy>.zip`: public schools 2015-16 to 2024-25 (2025-26 href is broken `~/data/`); private (PSS-based) 2015-16, 17-18, 19-20, 21-22, 23-24 (24-25 and 25-26 listed but 404 at probe time).
- Zip contains `.TXT` (pipe-delimited, **no header row**), `.sas7bdat`, `.xlsx` layout, shapefile zip. Column order (confirmed from shapefile DBF): `NCESSCH|LEAID|NAME|OPSTFIPS|STREET|CITY|STATE|ZIP|STFIP|CNTY|NMCNTY|LOCALE|LAT|LON|CBSA|NMCBSA|CBSATYPE|CSA|NMCSA|CD|SLDL|SLDU|SCHOOLYEAR`. Utah 2024-25: 1,120 schools.
- Public-school coordinates before 2015-16 must come from older CCD directory columns (check in Phase 1) or the geocoder.

## 5. PSS (private schools)
- **2023-24 public-use microdata IS available**: `https://nces.ed.gov/surveys/pss/zip/pss2324_pu_csv.zip` (also sas7bdat/sav/sas/sps), plus codebook/layout PDFs and a Frame File Data Dictionary. Every cycle back to 1989-90 is downloadable (`pss<yy><yy>_pu_csv.zip` for 2013-14 on; 2011-12 and earlier in SAS/SAV/TXT forms).
- 2023-24 CSV: 22,510 rows x 359 columns (88 replicate weights `REPW1..88`, `PFNLWT`, questionnaire items `P135..P660` with imputation flags `F_P*`), key `PPIN`, address `PADDRS/PCITY/PSTABB/PZIP`, **`LATITUDE24`/`LONGITUDE24` provided**, `PCNTY24`, `ULOCALE24`, `LEVEL`, `NUMSTUDS`, `NUMTEACH`, race percents `P_*`. Utah: 140 schools. Column names are year-suffixed and item numbering shifts between years, so per-year maps are required; codebook PDFs are the main dictionary source.
- ASCII, comma delimited, header row.

## 6. IPEDS
- **Correction:** canonical bulk path is now `https://nces.ed.gov/ipeds/complete-data-files/<NAME>.zip` (legacy `/ipeds/datacenter/data/` serves older files only). Dictionary: `<NAME>_Dict.zip` (xlsx). `datacenter/DataFiles.aspx` is an ASP.NET postback form that could not be scraped statelessly, so availability is determined by HEAD-probing predictable names. Confirmed present for 2024: `HD`, `IC`, `EF2024A/B/C/D`, `EF2024A_DIST`, `EFFY`, `EFIA`, `DRVEF`, `DRVEF12`, `ADM`, `SFA2324`, `SFAV2324`, `GR`, `GR200_24`, `OM`, `F2324_F1A`, `AL`, `C2024_A/B/C`, `DRVC`. Not found under guessed names: `E12`, `HR` (resolve in Phase 3). 2025: `HD2025`, `IC2025`, `EFFY2025`, `C2025_A/B/C`, `DRVC2025`, `DRVEF122025`, `EFIA2025`, `FLAGS2025`.
- `HD2025.csv`: UTF-8 **with BOM**, header, 5,985 institutions, Utah (`STABBR='UT'`) 61; has `LATITUDE`, `LONGITUD`, `COUNTYCD`, `CBSA`, `CNGDSTCD`.
- `EF2024A.csv`: 73 columns, long by `EFALEVEL`/`LINE`; each value column has an `X`-prefixed status flag (`R` reported, imputation codes).
- Year in file name = collection year (HD2025 = 2025-26).

## 7. Census geocoder
- Batch endpoint works: `POST https://geocoding.geo.census.gov/geocoder/locations/addressbatch` (multipart: `addressFile` CSV `id,street,city,state,zip` without header; `benchmark=Public_AR_Current`; `returntype=locations`). Output: `id, input, match(Match|No_Match|Tie), match_type(Exact|Non_Exact), matched_address, "lon,lat", tigerLineId, side`. Benchmarks: Public_AR_Current, Public_AR_ACS2026, Public_AR_Census2020.
- Test: 50 Utah private-school addresses -> 45 matched (90%): 34 exact, 11 non-exact, 5 no match (several PO boxes). Per-batch row limit (believed 10,000) not stress-tested.

## 8. Utah Parquet size
- One year of Utah CCD membership (134,795 rows, ZSTD, sorted): **130 KB**. With ~40 years that is a few MB. All Utah data likely totals well under 50 MB, so one file per table-year is fine and no splitting is needed.
