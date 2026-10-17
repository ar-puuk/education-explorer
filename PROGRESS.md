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

## Phase 5: districts, compare, tables, methodology
- [x] F-33 finance (via config/ccd_extra_files.yml), district boundaries (TIGER UNSD 2010-11..2024-25), district detail panel, compare mode (up to 4, shareable), table explorer + CSV export, methodology page
- [x] Colour-by (charter/locale/level) for public school markers, survey-year pips on the slider

## Phase 6: quality and release
- [x] pytest 27, vitest 11, Playwright smoke + axe a11y (light and dark: clean) + mobile (no horizontal scroll) + perf; ruff clean; CONTRIBUTING, issue/PR templates
- [x] Deployed at https://ar-puuk.github.io/education-explorer/ (main:/docs)

## Colorado smoke run (not committed; output redirected with EE_DOCS_DATA)
- [x] CCD 2014+ , EDGE, IPEDS (all families), PSS, geocode, dictionary and points build for Colorado with no schema or type drift (maps use national types)
- [x] Found and fixed: TIGER .dbf encoding retry (`ISO-8859-1`; GDAL does not know `LATIN1`)
- [ ] Open: 11 IPEDS uniqueness failures (ca2dig 2001, csubbacip 1980, ff1af/ff1ag 2004-07, iccampuses 2021-22, icpccampuses 2023). Keys are derived from the first state's rows, so they are too narrow for states with multiple rows per entity (affiliated entities, campuses). Fix: derive keys from the national staged files, or re-run `bootstrap-maps --force` for the new state
- [ ] Not run: legacy CCD 1997-2013 (re-reads ~25 min of national SAS files), geometry/size/performance for a large state

## UI redesign ("Atlas", 2026-10-17)
- [x] New shell: top bar (search with Ctrl K, dataset chips with live counts, theme toggle), left rail (Layers, Filters, Basemap and appearance, Table, Compare, About) opening one foldable drawer at a time, timeline docked at the bottom with a stacked histogram of places per year and survey-year marks
- [x] Basemap and appearance moved out of Layers into their own rail item (swatch cards, Auto follows theme)
- [x] One Inspector for school, college, private school and district: header with tags, tabs (Overview, Trends, Details, Data; districts add Schools), headline figures, cards, and an Expand button for a two-column workspace; bottom sheet on phones
- [x] Self-hosted fonts (Latin subsets): Bricolage Grotesque, Instrument Sans, IBM Plex Mono; dark theme gets its own data colours
- [x] e2e updated (smoke, a11y with extra scans for drawers and the expanded inspector, mobile); all pass on dev and the built preview
- [ ] Not done from the plan: pipeline additions (year summary JSON, per-entity profile files, derived metrics table, state median reference lines, search index). The timeline counts and headline figures are computed in the browser from the existing files, and no measured slowdown justified new files yet.
- [ ] Not done: compare tray inside the inspector (compare still opens as a dialog), phone bottom sheet has one snap height

## Next / unverified / known issues
- Known gaps: CCD 1986-87..1996-97 (fixed-width text) and the 1997-98 district file; IPEDS map layer and chart integration before 2000 (tables are in the explorer); curated finance, net-price and graduation charts
- Unverified: mobile only lightly tested (Chromium emulation); other browsers; other states beyond the Colorado smoke run
- Utah Parquet total ~62 MB in docs/data (IPEDS ~38, CCD ~12, PSS ~4, geo ~4)
- Commits are authored with the work email from git config
- Recommended next: fix IPEDS key derivation nationally, then run a full Colorado build including legacy
