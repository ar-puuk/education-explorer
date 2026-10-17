# Progress

Legend: [x] done, [~] in progress, [ ] todo

## Setup
- [x] uv project, git, .gitignore, skeleton, config, LICENSE, README, attribution
- [x] GitHub repo created and pushed

## Phase 0: Spikes
- [x] Pages range-request + DuckDB-WASM spike
- [x] Real files: CCD directory, CCD membership, PSS, IPEDS HD + EF
- [x] OpenFreeMap styles + setStyle overlay survival
- [x] Census batch geocoder test
- [x] Utah Parquet size estimate
- [x] SPIKES.md and HANDOFF.md corrections

## Phase 1: Pipeline foundation + CCD
- [x] config loader, fetch with manifest (sha256), CCD catalog from NCES JSON API, staging, deterministic Parquet
- [x] schema-drift guard + per-year YAML maps (CCD 2014-2025: directories, characteristics, membership, lunch, staff, IDEA, EL; EDGE locations)
- [x] dictionary builder (from NCES companion workbooks + curated caveats), validate, update (idempotent), tests (pytest 9, ruff clean)
- [x] Utah CCD 2014-15..2025-26 Parquet committed (5 MB total) after validate passed
- [x] Phase 1b: CCD legacy 1997-98..2013-14 (directory, location, membership, lunch, staff; district directory/membership/staff; as-published wide files). Not done: 1986-87..1996-97 (fixed-width text only) and the 1997-98 district file
- [ ] F-33 finance, graduation/dropout: Phase 5

## Phase 2: App shell + public schools on the map
- [x] Vite + Svelte 5 + TS app in web/, MapLibre, DuckDB-WASM (self-hosted, gzipped engine), Observable Plot
- [x] Light/dark/system theme with tokens; OpenFreeMap basemap switcher (Positron, Dark, Liberty, Liberty 3D, Bright, Fiord); overlays survive basemap switches; explicit basemap choice survives theme change
- [x] Public school points (CCD + EDGE), year slider with play, filters (closed, charter, level), search, detail panel (facts, enrollment trends: total/race/sex/grade heatmap, dictionary-backed labels and caveats), shareable URL state
- [x] Deployed from main:/docs at https://ar-puuk.github.io/education-explorer/ ; browser smoke test (web/e2e/smoke.mjs) passes against dev, built preview and the live Pages site
- [ ] Known: methodology page is a placeholder until Phase 5; mobile layout only lightly checked

## Phase 3: IPEDS
- [x] Catalog (1,213 files 1980-2025), 857 files for 2000-2025 downloaded, 75 table families built for Utah (~30 MB Parquet), maps with drift + type guards, dictionary (9k rows) + value labels, validation incl. keys
- [x] College layer (diamond/cap markers), filters by control, search, detail panel with fall enrollment (total/level/attendance/gender/race), 12-month headcount, awards, admissions, institution facts, and a table explorer for every IPEDS table (labels, flags, CSV export)
- [x] Phase 3b: IPEDS 1980-1999 tables (150 families total); map layer starts in 2000. Not done: curated finance/net-price/graduation charts (data are in the explorer)

## Phase 4: PSS + geocoding
- [x] PSS 1989-90..2023-24 (18 surveys) -> schools (all columns, labels), enrollment and teachers long tables; ~4 MB
- [x] Census batch geocoder with committed cache (163 addresses: 146 matched); applied to CCD school locations and college points; private points (292 schools, PSS 2005-06+)
- [x] Private layer (square/house markers), affiliation filter, biennial-survey note on the slider, private detail panel (enrollment tabs, teachers, facts, table explorer for PSS tables), approximate-location outline

## Phase 5 .. 6
- [ ] Phase 5 not started: remaining CCD topics (finance F-33, graduation/dropout), boundaries + rollups, compare mode, table/CSV export, methodology page
