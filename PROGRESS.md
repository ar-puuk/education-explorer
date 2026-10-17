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
- [ ] Phase 1b (deferred): CCD legacy years 1986-87..2013-14 directory + membership (schema maps for older layouts)
- [ ] F-33 finance, graduation/dropout: Phase 5

## Phase 2: App shell + public schools on the map
- [x] Vite + Svelte 5 + TS app in web/, MapLibre, DuckDB-WASM (self-hosted, gzipped engine), Observable Plot
- [x] Light/dark/system theme with tokens; OpenFreeMap basemap switcher (Positron, Dark, Liberty, Liberty 3D, Bright, Fiord); overlays survive basemap switches; explicit basemap choice survives theme change
- [x] Public school points (CCD + EDGE), year slider with play, filters (closed, charter, level), search, detail panel (facts, enrollment trends: total/race/sex/grade heatmap, dictionary-backed labels and caveats), shareable URL state
- [x] Deployed from main:/docs at https://ar-puuk.github.io/education-explorer/ ; browser smoke test (web/e2e/smoke.mjs) passes against dev, built preview and the live Pages site
- [ ] Known: methodology page is a placeholder until Phase 5; mobile layout only lightly checked

## Phase 3: IPEDS (in progress)
- [x] IPEDS catalog scraped from the Data Center page (1,213 files, 1980-2025); family naming; downloader
- [ ] stage/maps/build/dictionary/validation, college layer + detail panel (2000-2025; 1980-1999 deferred to 3b)

## Phase 4 .. 6
- [ ] not started
