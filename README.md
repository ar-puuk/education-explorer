# Education Explorer

A static, zero-cost, map-first dashboard for exploring **publicly available NCES data** for one U.S. state at a time:

| Layer | Source | Years |
|---|---|---|
| Public schools and districts | NCES Common Core of Data (CCD) + EDGE locations | 1997-98 onward (annual; 1986-87 to 1996-97 only exist as fixed-width text and are not ingested) |
| Private schools | NCES Private School Universe Survey (PSS) | every survey 1989-90 to 2023-24 (biennial; mappable from 2005-06) |
| Colleges | NCES IPEDS (all complete data files) | 1980 onward in the data tables (annual); the map layer starts in 2000 |
| School district boundaries | Census TIGER/Line | 2010-11 onward |

Live site: <https://ar-puuk.github.io/education-explorer/> (GitHub Pages, served from `main` `/docs`).

It shows data and caveats only: it does not rank schools, compute quality scores, or recommend anything. The state shown is chosen by one config file, and **nothing in the code is specific to a state**.

## What you get

- Map with three dataset layers (distinct shape *and* colour), clustering, year slider with play, filters, search, school-district boundaries.
- Detail panels with enrollment trends (total, race/ethnicity, sex, grade), free/reduced-price lunch, staff, finance, graduates and dropouts, IPEDS enrollment/awards/admissions, a table explorer for every IPEDS and PSS table, dictionary labels and caveats, CSV export.
- Compare mode, table view with column picker and CSV export, shareable URLs (year, selection, filters, basemap, layers, theme).
- Light, dark and system themes; six OpenFreeMap basemaps (Positron, Dark, Liberty, Liberty 3D, Bright, Fiord); overlays survive basemap switches.
- A [Data and methods](https://ar-puuk.github.io/education-explorer/methodology.html) page with sources, release versions and caveats.

## How it works

```
NCES / Census files --(local pipeline: Python + DuckDB)--> deterministic Parquet in docs/data/ --(Pages)--> browser
                                                                                    DuckDB-WASM queries it over HTTP range requests
```

- No backend, no GitHub Actions, no paid or key-gated services, no third-party data API. Preprocessing runs on your machine; **processed Parquet is committed** (raw downloads are not: only `data-raw/manifest.json` with URLs and sha256 hashes).
- The first paint uses small JSON "points" files; DuckDB-WASM loads afterwards and reads only the Parquet byte ranges it needs. The DuckDB engine ships gzipped (GitHub Pages does not compress `.wasm`).
- Parquet output is deterministic (explicit ordering, single writer, fixed compression and row-group size), so re-running `update` on unchanged inputs leaves `git status` clean.
- A **schema-drift guard** fails the build, with the nearest known column names, when a release adds, drops or renames a column or a value no longer fits its mapped type.

Layout: `config/` (state, sources, caveats), `pipeline/` (Python, uv), `web/` (Vite + Svelte 5 + TypeScript + MapLibre + DuckDB-WASM + Observable Plot), `docs/` (Pages root: built app and `docs/data/`), `data-raw/` (local downloads, gitignored). Decisions are logged in [docs/DECISIONS.md](docs/DECISIONS.md), spike findings in [SPIKES.md](SPIKES.md), status in [PROGRESS.md](PROGRESS.md).

## Quickstart

Requirements: [uv](https://docs.astral.sh/uv/), Node 20+, the DuckDB CLI (optional, for poking at files). Python 3.13 is pinned.

```bash
# pipeline
cd pipeline
uv sync
uv run python -m nces_pipeline --help
uv run pytest -q && uv run ruff check .

# app
cd ../web
npm install
npm run dev            # http://localhost:5173 (serves docs/data/ at /data/ with range requests)
npm run build          # writes to ../docs (never touches docs/data)
npm run preview        # serve the built docs/
node e2e/smoke.mjs http://localhost:4173/ shots   # browser checks (needs: npx playwright install chromium)
```

The data already in `docs/data/` is for the state in `config/states/`, so the app runs without running the pipeline.

## Updating after a new NCES release

```bash
cd pipeline
uv run python -m nces_pipeline fetch --check-only   # lists what is new; downloads nothing
uv run python -m nces_pipeline update               # fetch -> build -> geocode -> boundaries -> dictionary -> points -> meta -> validate
```

`update` prints a changelog of row-count changes and runs `validate`, which must pass before you commit Parquet (row counts may not drop more than 20% from the committed baseline; identifiers must be unique; files stay under 90 MB; every column has a dictionary entry; coordinates and boundaries stay inside the state's bounding box; no state literal appears in outputs).

When NCES changes a layout, the build stops with a message such as `+ NEWCOL not in the map (nearest known: OLDCOL)`. Fix it by editing the YAML map (`pipeline/nces_pipeline/schemas/…`): CCD has one file per topic and year (`build --scaffold-map ccd <topic> <year>` copies the previous year), IPEDS and PSS keep one file per table with year ranges on each column. A new CCD file that the NCES file-listing API fails to list can be added to `config/ccd_extra_files.yml`.

Commit the app build (`npm run build`) together with the data so the deployed site and its data stay in step. After pushing, GitHub Pages may serve cached files for about ten minutes.

## Adding a state

1. Copy `config/states/utah.yml` to `config/states/<name>.yml` and set `name`, `abbrev`, `fips`, `bbox` `[W, S, E, N]`, `center`, `zoom` and `site_title`.
2. `cd pipeline && uv run python -m nces_pipeline --state <name> update`. (With several state configs present `--state` is required.)
3. `cd ../web && npm run build`.

Notes: the raw files are national, so a new state reuses the downloads; staging filters them to the state. The pipeline writes to a single canonical location (`docs/data/`), so keep one state per checkout or fork. Larger states than Utah are not a design target: they work in principle, but Parquet sizes, the first-paint points files and the DuckDB-WASM memory budget have only been tested for Utah (see the Colorado smoke run in [PROGRESS.md](PROGRESS.md)).

## Data attribution and license

Code is MIT licensed ([LICENSE](LICENSE)). The data are U.S. public data reprocessed by this project; see [DATA_ATTRIBUTION.md](DATA_ATTRIBUTION.md). NCES public-use data are for statistical purposes only; do not attempt to identify individuals. This project is not affiliated with or endorsed by NCES or the U.S. Census Bureau. See [CONTRIBUTING.md](CONTRIBUTING.md) to help.
