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
- [x] Fixed: IPEDS uniqueness keys are now widened against the national files (`python -m nces_pipeline rekey-ipeds`). 11 families changed (ca2dig, csubbacip, efc, fc5, ff1af, ff1ag, gr, iccampuses, icmission, icpccampuses, pubfinancialaid). Utah data is byte-identical and validates; a Colorado IPEDS build has no uniqueness failures.
- [ ] Not run: legacy CCD 1997-2013 (re-reads ~25 min of national SAS files), geometry/size/performance for a large state

## UI redesign ("Atlas", 2026-10-17)
- [x] New shell: top bar (search with Ctrl K, dataset chips with live counts, theme toggle), left rail (Layers, Filters, Basemap and appearance, Table, Compare, About) opening one foldable drawer at a time, timeline docked at the bottom with a stacked histogram of places per year and survey-year marks
- [x] Basemap and appearance moved out of Layers into their own rail item (swatch cards, Auto follows theme)
- [x] One Inspector for school, college, private school and district: header with tags, tabs (Overview, Trends, Details, Data; districts add Schools), headline figures, cards, and an Expand button for a two-column workspace; bottom sheet on phones
- [x] Self-hosted fonts (Latin subsets): Bricolage Grotesque, Instrument Sans, IBM Plex Mono; dark theme gets its own data colours
- [x] e2e updated (smoke, a11y with extra scans for drawers and the expanded inspector, mobile); all pass on dev and the built preview
- [x] Pipeline additions from the plan (`python -m nces_pipeline derive`, also run by `update`): derived/school_metrics/<year>.parquet (students per teacher, lunch share), derived/school_profile.parquet (one row per school, series as arrays), meta/year_summary.json, meta/state_reference.json (median and quartiles of operating public schools, years with at least 10 schools), geo/districts_index.json. validate cross-checks them against the tables and points files.
- [x] App uses them: headline figures and Trends read the one-row school profile (no wait for the history tables), dashed state median with a middle-half band on the enrollment, students-per-teacher and lunch-share charts, timeline histogram from the year summary, district search from the index (all districts, not just those with a boundary in the selected year)
- [x] Compare tray: picked places stay visible as removable chips above the timeline (Compare/Open button, Clear); on phones it docks above the timeline and lifts the sheet
- [x] Phone bottom sheet has three snap points (peek, half, full): drag or tap the handle, arrow keys step, drag well below peek to dismiss (web/e2e/tray_sheet.mjs)
- [x] Search: stale blur timer no longer closes the results right after Ctrl K
- [x] Insight charts for every kind of place, drawn from tables that were already ingested (no pipeline change): TrendChart gained a stacked mode (counts or 100% share), plus BarList (one-year breakdown) and StatusStrip (yes/no history by year)
- [x] Colleges: tabs Overview, Students, Outcomes, Costs, Details, Data. Online-course load (online only / mix / in person only, by level, from IPEDS distance-education counts), race share, admissions and admit rate, residence of first-time students, 12-month headcount, student-faculty ratio, staff by occupation, retention, graduation rates, Outcome Measures 8-year awards, awards by level, tuition, total price, net price (by income band), aid shares and amounts, revenue sources and spending per FTE. Tables load per tab, on first open
- [x] Public schools: Students (race share, grades, sex share, lunch eligibility) and Programs (status/charter/virtual/Title I/magnet/shared-time/lunch-program history by year). Private schools: Students (race share, grades, sex share, student-teacher ratio). Districts: Students (race share, grades, sex share, English-learner and IDEA share) and Money (revenue and spending per student)
- [x] e2e/insights.mjs visits the new tabs for all four kinds in both themes; a11y scans the new school tabs
- [x] Second round of insight charts: colleges gain age mix, where first-time students come from (by state), instructional staff by rank, average faculty salary by rank, and revenue and expenses by purpose for every reporting year (public, nonprofit and for-profit forms combined); public schools and districts gain race within each grade; districts gain diplomas by credential, diploma recipients and dropouts by race and sex; private schools gain a profile-by-survey-year strip and prekindergarten counts; public schools' Programs strip adds grades offered, level and locale
- [x] Race and ethnicity categories keep one colour in every chart (lib/palette.ts); large dollar axes are abbreviated so they never clip; e2e/insights.mjs now runs axe on every new tab
- [x] Tooltips audited: every chart now shows a themed tooltip (Plot marks use Plot's tip; bar lists, grade bars, status strips, KPIs, the timeline histogram and field labels use the shared lib/tooltip.ts, which also works on touch and keyboard focus). e2e/tooltips.mjs hovers every chart in every tab for all four kinds of place and fails if one has no tooltip; it also checks that no card is left half-width in the expanded panel
- [x] Fixed: on charts with a legend the accessible image label was set on a legend swatch instead of the plot

## Next / unverified / known issues
- Not charted: PSS items that changed layout between survey years (school day, association memberships; the raw pss0xx columns are year-specific), college data before 1997 (finance) and the 2016-2020 salary files (outlays only), and CCD district graduation or dropout rates (the files hold counts, not cohorts). All remain in the Data tab.
- Known gaps: CCD 1986-87..1996-97 (fixed-width text) and the 1997-98 district file; IPEDS map layer and chart integration before 2000 (tables are in the explorer); curated finance, net-price and graduation charts
- Unverified: mobile only lightly tested (Chromium emulation); other browsers; other states beyond the Colorado smoke run
- Utah Parquet total ~62 MB in docs/data (IPEDS ~38, CCD ~12, PSS ~4, geo ~4)
- Commits are authored with the work email from git config
- Recommended next: run a full Colorado build including legacy CCD (IPEDS is verified), then check large-state size and load time
