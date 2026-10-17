# HANDOFF: NCES Education Explorer (state-configurable, static, zero-cost)

> **How to use this file:** put it in the root of an empty project folder (rename to `CLAUDE.md` if you want Claude Code to auto-load it every session). Then start with the "First session prompt" at the bottom.
> Written 2026-10-16. Anything marked **[VERIFY]** was not confirmed when this was written. Claude Code must check it against the live source (download it, read it) before relying on it. Do not trust URL patterns or column names from memory.

---

## 1. Goal

A clean, map-first dashboard that lets anyone explore **all publicly available NCES data** for schools and colleges in **one state at a time**, for **every historical year available**. The data exists but is obscure; the product is making it digestible. **Utah is the target state and must work.** The code must not hardcode Utah, so another state can be built by changing one config file.

Three datasets, shown on one map with distinct icons/colors, stored as **three separate sets of tables**:

| Dataset | Source | Entity key |
|---|---|---|
| Public K-12 | NCES CCD (Common Core of Data) | `ncessch` (school), `leaid` (district) |
| Private K-12 | NCES PSS (Private School Universe Survey) | `ppin` / PIN |
| Postsecondary | NCES IPEDS | `unitid` |

## 2. Locked decisions (do not relitigate)

1. **No paid anything.** Static site on GitHub Pages from a **public repo (public from the first commit, so every commit is immediately visible)**, served from `main` branch `/docs` folder. **No GitHub Actions, no backend, no paid services.**
2. **Preprocessing runs locally**, on the maintainer's machine.
3. **Do not use the Urban Institute Education Data Portal / API** as a data source. Fetch from real NCES (and Census) files. It is fine to *learn from* Urban's conventions (see section 7).
4. **Raw files**: kept locally in `data-raw/` (gitignored by default). Commit only `data-raw/manifest.json` (source URL, release date, sha256, bytes). If a raw file is small (< ~5 MB) it may be committed; default is not to.
5. **Processed Parquet is committed** to the repo, under `docs/data/`. Single canonical location (no copying in the build).
6. **Frontend:** Vite + TypeScript + Svelte 5, MapLibre GL JS, DuckDB-WASM, Observable Plot.
7. **Basemap:** OpenFreeMap vector styles (5 options, see section 9). **Light and dark mode** required.
8. **Geocoding:** US Census Geocoder (free, no key). Results cached in a committed Parquet.
9. **Support all available data**, not a curated subset. Parquet is cheap.
10. **Scale target is Utah.** Do not build or test for large states. Other states can fork and self-host. Do not spend effort optimizing for California/Texas. Colorado is a nice-to-have smoke test only, never a blocker.

## 3. Known data landscape (as of 2026-10-16)

- **CCD:** 2024-25 universe files (membership by grade/race/sex, staff, lunch eligibility) released Dec 2025. 2025-26 *preliminary directory* released July 2026 (directory only; membership etc. follow later). Pipeline must tolerate a year that has only some components, and later fill in the rest. Preliminary vs final versions exist: tag rows.
- **PSS:** biennial. 2023-24 First Look report published May 2026. **[VERIFY]** whether 2023-24 public-use microdata files are posted; the latest confirmed public-use files are 2021-22 (released Dec 2023, SAS/SPSS/text formats). PIN is the cross-year merge key. Private school point locations from NCES lag (EDGE page listed 2021-22 as latest; 2023-24 forthcoming), so expect to geocode.
- **IPEDS:** per-survey, per-year bulk files with data dictionaries via the IPEDS Data Center, keyed on `UNITID`. **[VERIFY]** current URLs, release cadence, provisional vs final, and the full survey component list (HD, IC, EF*, E12, C*, GR, GR200, OM, ADM, SFA, F*, HR, AL, plus derived "DRV" files).
- Likely entry points (all **[VERIFY]**): `nces.ed.gov/ccd/files.asp`, `nces.ed.gov/surveys/pss/pssdata.asp`, `nces.ed.gov/ipeds/datacenter/DataFiles.aspx`, NCES EDGE (school locations, school district geographic relationship files), Census TIGER/Line unified school district boundaries (`www2.census.gov/geo/tiger/`).
- Federal data URLs and formats can change. That is why raw files are hashed in a manifest and kept locally.

## 4. Repository layout

```
.
├── HANDOFF.md / CLAUDE.md
├── README.md                      # human docs: quickstart, adding a state, updating data
├── config/
│   ├── states/utah.yml            # the ONLY place Utah appears
│   ├── sources.yml                # per source/topic: URL patterns, year ranges, file format
│   └── app.yml                    # UI defaults (basemap defaults, palette)
├── pipeline/                      # Python (uv-managed), DuckDB-first
│   ├── pyproject.toml
│   ├── nces_pipeline/
│   │   ├── cli.py                 # `python -m nces_pipeline ...`
│   │   ├── fetch.py               # download + sha256 + manifest
│   │   ├── schemas/               # per-source, per-year column maps (YAML)
│   │   │   ├── ccd/ pss/ ipeds/
│   │   ├── transform/             # DuckDB SQL + thin Python drivers
│   │   ├── geocode.py             # Census batch geocoder + cache
│   │   ├── boundaries.py          # TIGER district polygons -> simplified GeoJSON
│   │   ├── dictionary.py          # builds data dictionary tables from layout files
│   │   ├── validate.py
│   │   └── update.py              # fetch -> build -> geocode -> validate
│   └── tests/                     # pytest with tiny fixture files
├── data-raw/                      # gitignored (except manifest.json)
│   └── manifest.json
├── docs/                          # GitHub Pages root (served from main /docs)
│   ├── index.html, assets/        # built app output
│   └── data/
│       ├── meta/                  # state.json, years.json, dictionary.parquet, geocode_cache.parquet
│       ├── ccd/                   # one Parquet per table per year (see 6)
│       ├── pss/
│       ├── ipeds/
│       └── geo/                   # boundaries GeoJSON per vintage, points files
└── web/                           # app source (Vite + Svelte + TS)
    ├── vite.config.ts             # base from config; outDir ../docs; emptyOutDir false
    └── src/
```

Vite builds into `docs/` with `emptyOutDir: false` so it never deletes `docs/data/`. In dev, serve `docs/data/` at `/data/` (dev middleware or proxy).

## 5. State configuration contract

`config/states/<name>.yml` (example for Utah):

```yaml
name: Utah
abbrev: UT
fips: "49"
bbox: [-114.06, 36.99, -109.04, 42.01]   # [W, S, E, N] **[VERIFY]**
center: [-111.65, 39.32]
zoom: 6
site_title: "Utah Education Explorer"
overrides: {}        # optional state quirks, documented, kept minimal
```

Rules:
- Select state with `--state utah` (config file name). All source filtering uses `fips` / `abbrev` from config.
- **No state literal anywhere in code, SQL, or UI.** Grep for "Utah", "UT", "49" in code before finishing each phase.
- Frontend reads `docs/data/meta/state.json` (emitted by the pipeline from config) for title, bbox, center, zoom.
- Adding a state = create a yml, run the pipeline, build. Document this in README. Do not test other states beyond an optional smoke run.

## 6. Data model

General conventions (copied from lessons learned in widely used harmonized education datasets, implemented independently):

- Column names `snake_case`. IDs always `VARCHAR` (preserve leading zeros: `ncessch` is 12 chars, `leaid` 7, `unitid` as text too for consistency).
- `year` = INTEGER **fall year of the school year** (2024 means 2024-25). Also `school_year` text like `2024-25` in directory tables.
- Sentinel/missing codes (negative numbers, "M", "N", "‡", etc.) become `NULL`, **plus** a companion `<col>_flag` (or a single `flag` for fact tables) recording the reason: `missing`, `not_applicable`, `suppressed`, `unknown_other`. Never silently coerce to 0.
- Every table carries `data_version` (`preliminary` | `final` | `provisional`, as the source labels it) and `source_file` (filename, not path).
- Category columns store a normalized label and keep the original code (`race`, `race_code`). Harmonize across years once, in schema YAML; document category breaks (e.g., "two or more races" introduced in 2009-10).
- Parquet writing must be **deterministic**: explicit `ORDER BY` on keys, fixed compression (ZSTD), fixed row-group size, no timestamps in data. Re-running on unchanged inputs must produce byte-identical files so git history stays small.
- One Parquet file per table per year where sensible (`docs/data/ccd/membership/2024.parquet`). Keep every file well under 100 MB (GitHub Pages file limit); aim for a few MB.

### 6.1 CCD (public) tables

| Table | Grain | Notes |
|---|---|---|
| `ccd_school_directory` | school x year | name, address, lat/lon, status (open/closed/new...), type, charter, magnet, virtual, locale, grade span, district link, Title I flags, school characteristics |
| `ccd_district_directory` | LEA x year | name, address, type, status, counties, locale |
| `ccd_membership` | school x year x grade x race x sex | long format; includes totals/"no category" handling explicitly |
| `ccd_district_membership` | LEA x year x ... | only if the source files provide it separately |
| `ccd_staff` | school/LEA x year | FTE by category |
| `ccd_lunch` | school x year | free/reduced-price eligibility counts; note Community Eligibility Provision comparability caveat in dictionary |
| `ccd_district_finance` | LEA x year | F-33 revenues/expenditures **[VERIFY availability and linkage]** |
| `ccd_graduation` | LEA/state x year | ACGR etc. **[VERIFY]** |

Ingest **every column** in each file. Anything not in the column map must stop the build (see 7).

### 6.2 PSS (private) tables

| Table | Grain | Notes |
|---|---|---|
| `pss_schools` | school x survey year | all PSS public-use variables, harmonized names where the question persists across years |
| `pss_enrollment` | school x year x grade/race (as available) | long format derived from the wide file |
| `pss_teachers` | school x year | counts/FTE as available |

Only survey years are present (biennial). The UI must show this explicitly, not as missing data. Merge across years on PIN. Include lat/lon if provided; otherwise geocode (section 8).

### 6.3 IPEDS (colleges) tables

One table family per survey component, long where natural: `ipeds_directory` (HD), `ipeds_ic`, `ipeds_enrollment_fall` (EF A/B/C/D), `ipeds_enrollment_12mo` (E12), `ipeds_completions` (C A/B/C/D), `ipeds_graduation` (GR, GR200), `ipeds_outcomes` (OM), `ipeds_admissions` (ADM), `ipeds_student_aid` (SFA), `ipeds_finance` (F variants, harmonized with care), `ipeds_hr`, `ipeds_derived`. Final list = what the Data Center actually offers for the state's institutions **[VERIFY]**. Filter by state via the HD directory (`stabbr`/`fips`), then keep only those `unitid`s in other components.

IPEDS HD includes coordinates; geocode only the gaps.

### 6.4 Shared/meta tables (`docs/data/meta/`)

- `dictionary.parquet`: `dataset, table, column, label, description, unit, first_year, last_year, caveat` built from NCES layout/data-dictionary files. The UI uses it for human-readable labels, tooltips, and caveats. This is a core product feature.
- `years.json`: which dataset/table has which years and version.
- `geocode_cache.parquet`: `addr_key, input_address, matched, match_type, lat, lon, tiger_line_id, benchmark, geocoded_on`.
- `state.json`: from config.

## 7. Pipeline design

**Tools:** Python managed with `uv`, DuckDB (Python API + SQL files) for transforms, `requests`/`httpx` for downloads, `pytest`, `ruff`. SQL-first: put transformations in `.sql` files; Python only orchestrates.

**CLI (all take `--state <name>`):**
```
python -m nces_pipeline fetch      [--source ccd|pss|ipeds] [--year YYYY] [--check-only]
python -m nces_pipeline build      [--source ...] [--year ...]
python -m nces_pipeline geocode
python -m nces_pipeline boundaries
python -m nces_pipeline validate
python -m nces_pipeline update     # = fetch -> build -> geocode -> boundaries -> validate, prints a changelog
```

**Schema-drift guard (critical, this is what makes future releases easy):**
- Each source/topic/year has a YAML column map: source column -> canonical column, type, recode rule, or `ignore: true` with a reason.
- At build, compare the raw file's header to the map. **Any unmapped or missing column fails the build** with a clear message listing new/removed columns and the nearest known candidates. Maintainer then edits the YAML.
- New-year bootstrap: `build --scaffold-map <source> <year>` copies the previous year's map and marks differences, so a new release is usually a 5-minute edit.

**Fetching:**
- `config/sources.yml` holds URL patterns and year ranges per source/topic. `fetch --check-only` probes for new releases and reports; it must never download silently.
- NCES has no release API: detection = probing predictable URLs and/or reading release pages. Expect occasional manual fixes; make failures loud and informative.
- Record sha256, size, release date, and retrieval date in `data-raw/manifest.json`. Verify hashes when files are re-used.

**Validation (`validate.py`, must pass before commit):**
- ID uniqueness per table-year.
- CCD school-level membership sums reconcile with district/state totals in the same release (report tolerance and exceptions).
- Year-over-year enrollment swing outliers flagged (report, do not fail).
- Coordinates inside state bbox (expanded slightly).
- Row counts compared with previous build; large drops fail.
- Every Parquet file < 90 MB.
- Every column in every output table has a dictionary entry.
- No state literal leaked into outputs other than `state.json`.

**Longitudinal linking:** schools open, close, merge, move. Keep closed/inactive schools with status. Do not attempt to link public to private to college. Each dataset stands alone.

## 8. Geocoding (Census Geocoder)

- Use the Census Geocoder **batch** endpoint (CSV upload) **[VERIFY]** endpoint URL, benchmark/vintage parameter names, and the per-batch row limit (believed ~10,000).
- Geocode only rows lacking trustworthy source coordinates (private schools, old public years, any institution gaps). Prefer source-provided lat/lon (CCD/EDGE, IPEDS HD, PSS if present).
- Normalize addresses to an `addr_key`; check `geocode_cache.parquet` first so reruns never re-geocode. Be polite: batch, back off on errors, resume safely.
- Store `match_type` (exact/non-exact/tie/no-match) and expose a boolean `coord_approximate` in the points data; the UI marks approximate locations.
- Failures remain NULL coordinates and are listed in a `geocode_report.txt` (not committed).

## 9. Frontend spec

**Stack:** Vite, TypeScript, Svelte 5, MapLibre GL JS, `@duckdb/duckdb-wasm`, Observable Plot, vitest. Self-host the DuckDB-WASM binaries/workers through Vite asset imports (do not rely on a CDN at runtime).

**Loading strategy:**
1. First paint: load a small prebuilt "latest points" file per dataset (`docs/data/geo/points_*.json` or Parquet), render the map immediately.
2. In the background, initialize DuckDB-WASM and attach Parquet files over **HTTP range requests** (`registerFileURL(..., DuckDBDataProtocol.HTTP, ...)`). Queries then fetch only what they need.
3. **Spike first** (Phase 0) to confirm GitHub Pages serves range requests correctly for Parquet and that DuckDB-WASM can query them.

**Basemap (OpenFreeMap, no API key):** offer a basemap switcher with the five options:

| Option | Style URL |
|---|---|
| Liberty | `https://tiles.openfreemap.org/styles/liberty` |
| Bright | `https://tiles.openfreemap.org/styles/bright` |
| Positron | `https://tiles.openfreemap.org/styles/positron` |
| Dark | `https://tiles.openfreemap.org/styles/dark` **[VERIFY works]** |
| Fiord | `https://tiles.openfreemap.org/styles/fiord` **[VERIFY works]** |

- "Liberty 3D" is Liberty plus a client-side `fill-extrusion` building layer and camera pitch (treat as a sixth toggle on Liberty, not a separate style). **[VERIFY]** source/layer names against the live style.
- Dark and Fiord have been described by their maintainers as less complete than the others; check them visually and note any quirks in README.
- **Defaults:** light theme -> Positron; dark theme -> Dark. Remembered choice overrides defaults. Positron/Dark are chosen as defaults because their muted tones keep overlay data legible.
- Switching basemap must **not lose overlays**. Re-add sources/layers on `style.load` (or use `transformStyle` to preserve them). Test this explicitly.
- Keep the attribution control visible (OpenFreeMap / OpenMapTiles / OpenStreetMap) and add NCES + Census credit in the footer.

**Light/dark mode:**
- Design tokens as CSS variables on `:root`; dark values under `@media (prefers-color-scheme: dark)` guarded so a manual override works: `:root:not([data-theme="light"])` plus `:root[data-theme="dark"]`.
- Three-way control: System / Light / Dark. Persist in `localStorage` (this is our own site, so storage is fine), default System.
- Map overlays, charts (Plot), tables, tooltips, and icons all read tokens. Verify contrast in both modes (WCAG AA).
- Changing theme auto-switches basemap to that theme's default only if the user has not explicitly chosen a basemap.

**Map layers (three independent datasets):**
- Three point sources: public, private, college. Each with a distinct **hue and glyph shape**, so meaning never depends on color alone: e.g., public = circle/building glyph, private = square-ish/house glyph, college = diamond/cap glyph. Use a colorblind-safe palette. Icon = colored circle background + white glyph, generated at runtime with `map.addImage`.
- Per-dataset visibility toggles and a legend. Clustering at low zoom.
- Optional boundary layer: school district polygons for the selected year/vintage, togglable, with hover/selection highlight.
- Marker size/color encodings are user-selectable (e.g., size by enrollment, color by locale/charter/status) from dictionary-backed fields.
- Closed schools shown only if the selected year had them open; style closed/inactive distinctly when the "include closed" filter is on.

**Core interactions:**
- Year slider (per dataset: show which years exist; PSS biennial explicitly marked). Play/animate control.
- Filters: dataset-specific (grade span, charter/magnet/virtual, locale, district, sector/control & level for colleges, enrollment range, etc.), generated from dictionary metadata where possible.
- Search by name/address/ID.
- Detail panel on click: all available fields for that entity-year grouped by topic, with dictionary labels and caveats; trend charts across all years for enrollment (total + by race/sex/grade), staff, lunch, finance, IPEDS components.
- Compare mode (select several schools/districts/colleges, overlay trends).
- Table view of the current filter with column picker and **CSV export**.
- District rollups: aggregate schools by district for the selected year.
- Data/Methodology page: sources, release versions per dataset/year, caveats (CEP lunch comparability, race category changes, suppression, preliminary data, PSS biennial, geocode approximation), and links to NCES originals.
- **Shareable URL state** (year, filters, selection, basemap, layers, theme).
- Responsive (mobile: bottom-sheet detail panel). Keyboard-accessible controls.

**Must not:** rank schools, compute "quality" scores, or imply recommendations. Show data and caveats only. NCES public-use terms: statistical purposes only; no attempts to identify individuals.

## 10. Deployment (no Actions)

- GitHub Pages: Settings -> Pages -> Deploy from branch `main`, folder `/docs`.
- `npm run build` (in `web/`) writes to `docs/`. Add `docs/.nojekyll`.
- Vite `base` must be the repo path (`/<repo>/`) or relative (`./`); verify asset paths work under the project URL.
- Git hygiene: no Git LFS (Pages does not serve LFS content). Keep total repo comfortably under ~1 GB. Deterministic Parquet (section 6) keeps diffs small.

## 11. Use of DuckDB skills (development aid)

The `duckdb-skills` plugin (Claude Code) wraps the DuckDB CLI so the agent can inspect data with real queries instead of guessing. Recommended for this project:

```
/plugin install duckdb-skills@claude-plugins-official
```

Requires the DuckDB CLI installed. Use `read-file` to profile each raw NCES file (real column names/types), `convert-file` for quick CSV->Parquet prototypes, `spatial` for boundary/point work, and `duckdb-docs` for syntax. **Always inspect an actual raw file before writing or changing its column map.** The plugin is a dev tool only; it is not part of the shipped app.

## 12. Phased plan with acceptance criteria

**Phase 0: Spikes (runs entirely in this public repo; Pages can be enabled on it for the range-request spike)**
- Publish a throwaway `docs/` page on Pages serving a ~10 MB Parquet; confirm HTTP range requests work and DuckDB-WASM queries it quickly.
- Download one real file each: CCD directory (latest), CCD membership (latest), PSS (latest available), IPEDS HD and EF (latest). Profile with DuckDB. Record real URLs, formats, encodings, header names, sentinel codes.
- Test OpenFreeMap: load all five style URLs in MapLibre, confirm overlay survives `setStyle`.
- Test Census batch geocoder with ~50 private school addresses; record match rate.
- Measure realistic Utah Parquet size from one year of CCD membership; extrapolate.
- **Output:** `docs/SPIKE_REPORT.md` (or `SPIKES.md`) with findings and corrections to this document.

**Phase 1: Pipeline foundation + CCD**
- Config loader, fetch with manifest, schema-guard, dictionary builder, deterministic Parquet writer.
- CCD directories + membership for all available years; validation passing.
- Tests on fixtures. **Accept:** `update --state utah` is idempotent (second run produces no git diff).

**Phase 2: App shell + public schools on the map**
- Svelte app, theme system, OpenFreeMap switcher, public school points, year slider, detail panel with enrollment trends, URL state.
- **Accept:** works in light/dark; basemap switch keeps overlays; Pages deployment works from `/docs`.

**Phase 3: IPEDS**
- All components available for state institutions; college layer, detail panel, trends.

**Phase 4: PSS + geocoding**
- PSS tables, geocoder + cache, private layer with approximate-location markers.

**Phase 5: Remaining CCD topics + boundaries**
- Staff, lunch, finance, graduation, school characteristics; district boundaries and rollups; compare mode; table/CSV export; methodology page.

**Phase 6: Polish & open-source readiness**
- README (quickstart, adding a state, updating after a new NCES release), CONTRIBUTING, LICENSE (code: MIT or Apache-2.0, maintainer's choice; data is U.S. public data, add attribution notes), accessibility pass, performance pass, issue templates. Optional single Colorado smoke run; document results without promising support.

## 13. Working agreements for Claude Code

1. **Verify before trusting.** Anything marked [VERIFY] must be confirmed against the live source. Never invent column names, URLs, or release dates; if something can't be reached, say so and ask.
2. **Look at real data first.** Profile each raw file with DuckDB before writing its schema map.
3. **Ask before spending decisions are changed.** Do not add paid services, Actions workflows, external CDNs for runtime code, or backends. If you think one is warranted, explain and ask.
4. **No hardcoded state.** Run a grep check each phase.
5. **Small, reviewable commits** per phase; commit processed Parquet only after `validate` passes. Do not commit raw files unless small and explicitly allowed.
6. **Record decisions and deviations** in `docs/DECISIONS.md` (short entries: date, decision, why).
7. **Report assumptions** at the end of each phase, plus a list of anything unverified.
8. Keep the UI neutral and data-honest: surface caveats from the dictionary; no rankings or quality scoring.
9. Prefer boring, well-supported libraries; avoid framework churn.

## 14. Open questions to resolve during Phase 0

- Do GitHub Pages range requests behave for Parquet? (Everything depends on this.)
- Are PSS 2023-24 public-use files available, and in what format?
- Exact IPEDS file URLs/formats and which components have usable history for Utah's institutions.
- Which TIGER vintages to include for district boundaries; are boundaries needed per year or just a few snapshots?
- Do OpenFreeMap Dark and Fiord render adequately with our overlays?
- Final size of Utah's committed Parquet; do any tables need splitting by year or sorting changes?

---

## First session prompt (paste this to Claude Code)

> Read HANDOFF.md fully. Do not write app code yet. Start with Phase 0 (spikes): set up the project skeleton (uv, Vite+Svelte+TS), install the duckdb-skills plugin if available, download one real file each from CCD, PSS, and IPEDS for the state in `config/states/utah.yml` (create that config first), profile them with DuckDB, run the Pages range-request test and OpenFreeMap style test, then write `SPIKES.md` with real URLs, schemas, sentinel codes, sizes, and any corrections to HANDOFF.md. Stop and show me the findings before starting Phase 1.
